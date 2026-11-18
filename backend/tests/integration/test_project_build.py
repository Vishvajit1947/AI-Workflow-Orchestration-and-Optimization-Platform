"""
The build / repair loop: honest statuses, bounded repairs, validated fixes, cancellation.

A fake sandbox decides each step's outcome from the real workspace files on disk, so a
correct fix really changes the next run. The repair LLM is scripted.
"""
import asyncio
import uuid
from pathlib import Path

import pytest

from backend.app.models import Workflow
from backend.app.services.project_builder.repair import build_prompt, parse_fix
from backend.app.services.project_builder.sandbox import RunnerSandbox, SandboxUnavailable, StepResult
from backend.app.services.project_builder.service import ProjectBuildService, summarize
from backend.app.services.project_builder.workspace import ProjectWorkspaceService
from backend.app.services.workspace.local_server_adapter import LocalServerWorkspaceAdapter

FENCE = "```"
FASTAPI_PROJECT = [
    {"path": "README.md", "content": "# API\n"},
    {"path": ".gitignore", "content": "__pycache__/\n"},
    {"path": "requirements.txt", "content": "uvicorn\n"},  # fastapi missing
    {"path": "main.py", "content": "from fastapi import FastAPI\napp = FastAPI()\n"},
]


class FakeSandbox:
    """Behaves like the runner, judging steps from the workspace contents."""

    def __init__(self, root: Path, fail_kinds: dict | None = None, unavailable: bool = False, delay: float = 0):
        self.root, self.fail_kinds, self.unavailable, self.delay = root, fail_kinds or {}, unavailable, delay
        self.opened, self.closed, self.calls = 0, 0, []

    async def open(self, runtime, workspace):
        if self.unavailable:
            raise SandboxUnavailable("Docker is not available to the runner")
        self.opened += 1
        sandbox, path = self, self.root / workspace

        class Session:
            async def run_step(self, kind, cwd, module=None):
                sandbox.calls.append(kind)
                if sandbox.delay:
                    await asyncio.sleep(sandbox.delay)
                if kind in sandbox.fail_kinds:
                    return sandbox.fail_kinds[kind]
                if kind == "py_import":
                    requirements = (path / cwd / "requirements.txt").read_text()
                    if "fastapi" not in requirements:
                        return StepResult(1, "Traceback ...\nModuleNotFoundError: No module named 'fastapi'", 40)
                return StepResult(0, f"{kind} ok", 10)

            async def close(self):
                sandbox.closed += 1

        return Session()


def scripted_llm(*answers):
    calls = []

    async def llm(prompt, system):
        calls.append(prompt)
        answer = answers[min(len(calls), len(answers)) - 1]
        return answer, "fake-model"

    llm.calls = calls
    return llm


GOOD_FIX = (f"DIAGNOSIS: The FastAPI dependency is missing from requirements.txt.\n"
            f"{FENCE}text path=requirements.txt\nfastapi==0.115.6\nuvicorn\n{FENCE}")
USELESS_FIX = f"DIAGNOSIS: Try reformatting.\n{FENCE}python path=main.py\nfrom fastapi import FastAPI\napp = FastAPI()  # x\n{FENCE}"


@pytest.fixture
def root(tmp_path):
    return tmp_path / "projects"


@pytest.fixture
async def project_ctx(db_session, test_user, root):
    workflow = Workflow(name="API project")
    db_session.add(workflow)
    await db_session.flush()
    ws = ProjectWorkspaceService(db_session, test_user.id, LocalServerWorkspaceAdapter(root))
    project = await ws.project_for_workflow(workflow.id, "API project")
    return ws, project


async def build(ws, project, sandbox, llm, files=FASTAPI_PROJECT, **kw):
    service = ProjectBuildService(ws, sandbox, llm, **kw)
    return await service.build(project, files, execution_id=uuid.uuid4())


async def test_successful_project_is_marked_succeeded_only_after_every_step_passes(project_ctx, root):
    ws, project = project_ctx
    files = [*FASTAPI_PROJECT[:2], {"path": "requirements.txt", "content": "fastapi\nuvicorn\n"}, FASTAPI_PROJECT[3]]
    sandbox = FakeSandbox(root)
    run = await build(ws, project, sandbox, scripted_llm(GOOD_FIX), files=files)
    assert run.status == project.status == "succeeded"
    assert [s["kind"] for s in run.steps] == ["pip_install", "py_compile", "py_import"]
    assert all(s["status"] == "passed" for s in run.steps) and run.repairs == []
    assert run.project_type == "fastapi" and sandbox.closed == sandbox.opened == 1


async def test_missing_dependency_is_diagnosed_fixed_and_rerun(project_ctx, root):
    ws, project = project_ctx
    llm = scripted_llm(GOOD_FIX)
    run = await build(ws, project, FakeSandbox(root), llm)

    assert run.status == "succeeded"
    (repair,) = run.repairs
    assert "FastAPI dependency is missing" in repair["diagnosis"] and repair["model"] == "fake-model"
    (changed,) = repair["files"]
    assert changed["path"] == "requirements.txt" and changed["action"] == "modified"
    assert changed["previous_content"] == "uvicorn\n"  # previous version preserved
    assert await ws.read_file(project, "requirements.txt") == "fastapi==0.115.6\nuvicorn\n"
    failed = [s for s in run.steps if s["status"] == "failed"]
    assert [(s["attempt"], s["kind"]) for s in failed] == [(0, "py_import")]
    assert [s["kind"] for s in run.steps if s["attempt"] == 1] == ["pip_install", "py_compile", "py_import"]
    assert "No module named 'fastapi'" in llm.calls[0] and "requirements.txt" in llm.calls[0]


async def test_repairs_stop_at_the_limit_and_report_the_remaining_error(project_ctx, root):
    ws, project = project_ctx
    run = await build(ws, project, FakeSandbox(root), scripted_llm(USELESS_FIX), max_repairs=3)
    assert run.status == project.status == "failed"
    assert [r["attempt"] for r in run.repairs] == [1, 2, 3]
    assert sorted({s["attempt"] for s in run.steps}) == [0, 1, 2, 3]
    assert "after 3 automatic repair attempt(s)" in run.error_summary
    assert "No module named 'fastapi'" in run.error_summary


async def test_no_fix_proposed_ends_the_build_as_failed(project_ctx, root):
    ws, project = project_ctx
    run = await build(ws, project, FakeSandbox(root), scripted_llm("DIAGNOSIS: I cannot fix this."))
    assert run.status == "failed" and len(run.repairs) == 1
    assert run.repairs[0]["files"] == [] and "could not propose a fix" in run.error_summary


async def test_unsafe_fix_paths_are_rejected_and_nothing_is_written_outside(project_ctx, root):
    ws, project = project_ctx
    evil = (f"DIAGNOSIS: x\n{FENCE}text path=../../outside.txt\npwned\n{FENCE}\n"
            f"{FENCE}text path=node_modules/x/index.js\npwned\n{FENCE}")
    run = await build(ws, project, FakeSandbox(root), scripted_llm(evil), max_repairs=1)
    assert run.status == "failed"
    assert not any(root.rglob("outside.txt")) and not (root.parent / "outside.txt").exists()
    assert not any(f["path"].startswith("node_modules") for r in run.repairs for f in r["files"])


async def test_sandbox_unavailable_is_reported_never_as_success(project_ctx, root):
    ws, project = project_ctx
    run = await build(ws, project, FakeSandbox(root, unavailable=True), scripted_llm(GOOD_FIX))
    assert run.status == project.status == "unavailable"
    assert "could not be executed" in run.error_summary and run.steps == []


async def test_timeout_and_nonzero_exit_are_recorded(project_ctx, root):
    ws, project = project_ctx
    sandbox = FakeSandbox(root, fail_kinds={"py_compile": StepResult(None, "[timed out after 120s]", 120000, timed_out=True)})
    run = await build(ws, project, sandbox, scripted_llm("DIAGNOSIS: infinite loop at import time."), max_repairs=1)
    failed = run.steps[-1]
    assert failed["timed_out"] is True and failed["status"] == "failed" and run.status == "failed"


async def test_no_runnable_component_fails_honestly(project_ctx, root):
    ws, project = project_ctx
    sandbox = FakeSandbox(root)
    run = await build(ws, project, sandbox, scripted_llm(GOOD_FIX), files=[{"path": "notes.md", "content": "# hi"}])
    assert run.status == "failed" and "No runnable component" in run.error_summary and sandbox.opened == 0


async def test_cancel_flag_stops_the_build_as_cancelled(project_ctx, root):
    ws, project = project_ctx
    state = {"cancel": False}
    sandbox = FakeSandbox(root)
    original = sandbox.open

    async def open_then_cancel(runtime, workspace):
        session = await original(runtime, workspace)
        state["cancel"] = True  # user presses Cancel while the sandbox is starting
        return session

    sandbox.open = open_then_cancel
    run = await build(ws, project, sandbox, scripted_llm(GOOD_FIX), is_cancelled=lambda: state["cancel"])
    assert run.status == project.status == "cancelled" and run.status != "succeeded"
    assert sandbox.closed == 1


async def test_task_cancellation_closes_the_sandbox_and_records_cancelled(project_ctx, root):
    ws, project = project_ctx
    sandbox = FakeSandbox(root, delay=5)
    service = ProjectBuildService(ws, sandbox, scripted_llm(GOOD_FIX))
    task = asyncio.create_task(service.build(project, FASTAPI_PROJECT))
    while not sandbox.calls:
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sandbox.closed == 1  # the container is removed, stopping the running step
    assert project.status == "cancelled"


async def test_runner_without_url_is_unavailable():
    with pytest.raises(SandboxUnavailable, match="No sandbox runner is configured"):
        await RunnerSandbox(base_url="", token="").open("python", "a/b")


async def test_runner_that_is_down_is_unavailable():
    with pytest.raises(SandboxUnavailable, match="not reachable"):
        await RunnerSandbox(base_url="http://127.0.0.1:9", token="t").open("python", "a/b")


def test_repair_prompt_and_answer_parsing():
    files = {"main.py": "import fastapi\n", "requirements.txt": "uvicorn\n", "docs/notes.md": "x"}
    step = {"label": "Import the application", "command": "python -c 'import main'", "cwd": "",
            "component": "(root)", "exit_code": 1, "timed_out": False,
            "output": "File \"main.py\", line 1\nModuleNotFoundError: No module named 'fastapi'"}
    prompt = build_prompt(files, step, [])
    assert "EXIT CODE: 1" in prompt and "No module named 'fastapi'" in prompt
    assert prompt.index("path=main.py") < prompt.index("path=docs/notes.md")  # mentioned files first

    fix = parse_fix(GOOD_FIX)
    assert fix.diagnosis.startswith("The FastAPI dependency") and list(fix.files) == ["requirements.txt"]
    # Heading-labelled files (as real models often write them) are accepted too
    heading = (f"DIAGNOSIS: httpx is required by TestClient but missing.\n\n### `requirements.txt`\n"
               f"{FENCE}txt\nfastapi\nhttpx\n{FENCE}\n")
    fix = parse_fix(heading)
    assert fix.diagnosis == "httpx is required by TestClient but missing."
    assert fix.files == {"requirements.txt": "fastapi\nhttpx\n"} and fix.rejected == []
    too_many = "DIAGNOSIS: x\n" + "".join(f"{FENCE}text path=f{i}.py\n{i}\n{FENCE}\n" for i in range(7))
    fix = parse_fix(too_many)
    assert len(fix.files) == 5 and len(fix.rejected) == 2


async def test_summary_reflects_the_real_outcome(project_ctx, root):
    ws, project = project_ctx
    run = await build(ws, project, FakeSandbox(root), scripted_llm(USELESS_FIX), max_repairs=1)
    text = summarize(run, project)
    assert "Project build failed." in text and "FAIL Import the application" in text
    assert "verified" not in text
