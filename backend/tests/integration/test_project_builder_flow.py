"""
End-to-end Project Builder flow through the real API and ExecutionEngine:

  plan (project mode) -> generate workflow (adds the build stage) -> execute
  -> generation stage writes files -> build stage: sandbox run fails on a missing
  dependency -> AI repair -> rebuild passes -> project persisted, files/ZIP downloadable,
  invisible to other users.

The LLM is a scripted provider and the sandbox is the realistic fake from
test_project_build (it judges steps from the real workspace files). The real sandbox is
exercised separately against Docker.
"""
import io
import uuid
import zipfile
from typing import Optional

import pytest
from sqlalchemy import select

from backend.app.models import Stage, StageDependency
from backend.app.schemas.planner import ObjectiveAnalysisResponse, StagePlan
from backend.app.services.execution import execution_engine
from backend.app.services.llm import registry
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse
from backend.app.services.project_builder import workspace as workspace_module
from backend.app.services.workflow_planner import ensure_project_output
from backend.app.services.workspace.local_server_adapter import LocalServerWorkspaceAdapter
from backend.tests.integration.test_project_build import FakeSandbox

FENCE = "```"
GENERATED = (
    "Here is the API.\n"
    f"{FENCE}text path=backend/requirements.txt\nuvicorn\n{FENCE}\n"
    f"{FENCE}python path=backend/main.py\nfrom fastapi import FastAPI\napp = FastAPI()\n{FENCE}\n"
    f"{FENCE}markdown path=README.md\n# Students API\nRun: uvicorn main:app\n{FENCE}\n"
    f"{FENCE}text path=.gitignore\n__pycache__/\n{FENCE}\n"
)
REPAIR = (f"DIAGNOSIS: fastapi is imported but missing from backend/requirements.txt.\n"
          f"{FENCE}text path=backend/requirements.txt\nfastapi==0.115.6\nuvicorn\n{FENCE}")


class ScriptedProvider(BaseLLMProvider):
    provider_name = "scripted"

    def __init__(self):
        self.prompts: list[tuple[str, Optional[str]]] = []

    async def generate(self, prompt, model=None, temperature=0.7, max_tokens=4096, system_prompt=None):
        self.prompts.append((prompt, system_prompt))
        if system_prompt and "fixing a generated software project" in system_prompt:
            content = REPAIR
        elif "path=" in (system_prompt or ""):  # file-writing stage (artifact format instructions)
            content = GENERATED
        else:
            content = "Requirements: list, create and delete students."
        return LLMResponse(content=content, model="scripted-model", provider="scripted", input_tokens=10,
                           output_tokens=20, total_tokens=30, latency_ms=5, estimated_cost=0.0001)

    def get_available_models(self):
        return [{"name": "scripted-model"}]

    def get_default_model(self):
        return "scripted-model"


@pytest.fixture
def provider():
    p = ScriptedProvider()
    registry.register(p)
    yield p
    registry._providers.pop(p.provider_name, None)


@pytest.fixture
def sandbox_root(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    adapter = LocalServerWorkspaceAdapter(root)
    monkeypatch.setattr(workspace_module, "_default_adapter", adapter)
    sandbox = FakeSandbox(adapter.workspace_root)
    monkeypatch.setattr(execution_engine, "default_sandbox", lambda: sandbox)
    return sandbox


PLAN = ObjectiveAnalysisResponse(
    complexity="complex",
    reason="A small API project with requirements and implementation.",
    stages=[
        StagePlan(id="requirements", name="Requirements", description="Define the API features to build",
                  instruction="List the endpoints of the students API", stage_type="analysis",
                  dependencies=[], expected_output="Endpoint list", output_mode="explanation"),
        StagePlan(id="backend", name="Backend", description="Write the FastAPI backend project files",
                  instruction="Write the FastAPI backend with requirements.txt and README",
                  stage_type="generation", dependencies=["requirements"], expected_output="Project files",
                  output_mode="project"),
    ],
)


async def test_complete_project_flow(client, db_session, make_user_client, provider, sandbox_root, mock_embeddings):
    created = await client.post("/api/planner/generate", json={
        "objective": "Build a student management API with FastAPI", "plan": PLAN.model_dump(), "mode": "project"})
    assert created.status_code == 201, created.text
    workflow = created.json()
    stages = {s["name"]: s for s in workflow["stages"]}
    build_stage = stages["Build & verify project"]
    kind = await db_session.scalar(select(Stage.config["kind"].astext).where(Stage.id == uuid.UUID(build_stage["id"])))
    assert kind == "project_build"
    deps = (await db_session.execute(select(StageDependency.depends_on_stage_id)
                                     .where(StageDependency.stage_id == uuid.UUID(build_stage["id"])))).scalars().all()
    assert [str(d) for d in deps] == [stages["Backend"]["id"]]  # depends only on the file-writing stage

    started = await client.post(f"/api/workflows/{workflow['id']}/execute",
                                json={"default_provider": "scripted", "use_routing": False, "use_cache": False})
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "completed"

    # The build stage's result is an honest summary; the repair happened once
    details = (await client.get(f"/api/executions/{started.json()['execution_id']}")).json()
    build = next(s for s in details["stages"] if s["stage_name"] == "Build & verify project")
    assert build["status"] == "completed"
    assert "built and verified" in build["result"] and "Automatic repairs: 1" in build["result"]
    assert sandbox_root.calls.count("py_import") == 2  # failed, then passed after the fix

    # Persisted project: status, run history, repaired file, ZIP
    (project,) = (await client.get(f"/api/projects?workflow_id={workflow['id']}")).json()
    assert project["status"] == "succeeded" and project["project_type"] == "fastapi"
    run = project["latest_run"]
    assert run["status"] == "succeeded" and len(run["repairs"]) == 1
    assert run["repairs"][0]["files"][0]["previous_content"] == "uvicorn\n"
    files = {f["path"]: f["content"] for f in (await client.get(f"/api/projects/{project['id']}/files")).json()}
    assert set(files) == {".gitignore", "README.md", "backend/main.py", "backend/requirements.txt"}
    assert files["backend/requirements.txt"].startswith("fastapi==0.115.6")
    zipped = await client.get(f"/api/projects/{project['id']}/download")
    assert zipped.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(zipped.content)).namelist()
    assert any(n.endswith("backend/requirements.txt") for n in names)

    # The existing per-execution artifact ZIP still works alongside the project
    eid = started.json()["execution_id"]
    backend_stage = next(s for s in details["stages"] if s["stage_name"] == "Backend")
    assert (await client.get(f"/api/executions/{eid}/stages/{backend_stage['stage_id']}/artifact.zip")).status_code == 200

    # Another user sees nothing
    _, other = await make_user_client("other-builder@example.com")
    assert (await other.get("/api/projects")).json() == []
    for path in (f"/api/projects/{project['id']}", f"/api/projects/{project['id']}/files",
                 f"/api/projects/{project['id']}/download", f"/api/projects/{project['id']}/runs",
                 f"/api/projects/{project['id']}/files/content?path=README.md"):
        assert (await other.get(path)).status_code == 404, path


async def test_failed_build_fails_the_workflow_honestly(client, provider, sandbox_root, mock_embeddings, monkeypatch):
    # The repair model never fixes anything: the build must end failed, and so must the workflow
    monkeypatch.setattr("backend.tests.integration.test_project_builder_flow.REPAIR",
                        "DIAGNOSIS: Unclear.\n")
    workflow = (await client.post("/api/planner/generate", json={
        "objective": "Build a student management API with FastAPI", "plan": PLAN.model_dump(), "mode": "project"})).json()
    started = (await client.post(f"/api/workflows/{workflow['id']}/execute",
                                 json={"default_provider": "scripted", "use_routing": False, "use_cache": False})).json()
    assert started["status"] == "failed"
    (project,) = (await client.get(f"/api/projects?workflow_id={workflow['id']}")).json()
    assert project["status"] == "failed" and project["latest_run"]["status"] == "failed"
    assert "No module named 'fastapi'" in project["latest_run"]["error_summary"]
    # The generated files are still there to inspect and download
    assert (await client.get(f"/api/projects/{project['id']}/download")).status_code == 200


async def test_artifact_mode_is_unchanged(client, provider, sandbox_root, mock_embeddings):
    workflow = (await client.post("/api/planner/generate", json={
        "objective": "Build a student management API with FastAPI", "plan": PLAN.model_dump()})).json()
    assert [s["name"] for s in workflow["stages"]] == ["Requirements", "Backend"]  # no build stage
    started = (await client.post(f"/api/workflows/{workflow['id']}/execute",
                                 json={"default_provider": "scripted", "use_routing": False, "use_cache": False})).json()
    assert started["status"] == "completed"
    assert (await client.get(f"/api/projects?workflow_id={workflow['id']}")).json() == []
    assert sandbox_root.opened == 0


def test_project_mode_plan_always_has_a_file_writing_stage():
    plan = PLAN.model_copy(update={"stages": [s.model_copy(update={"output_mode": "explanation"}) for s in PLAN.stages]})
    fixed = ensure_project_output(plan)
    assert [s.output_mode for s in fixed.stages] == ["explanation", "project"]
