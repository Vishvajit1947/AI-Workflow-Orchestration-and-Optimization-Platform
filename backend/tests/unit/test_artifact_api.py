"""
Artifact fields on GET /executions/{id} and the download endpoints.

The database is replaced by an in-memory fake session (get_db override), so these run
without PostgreSQL while exercising the real route handlers, schemas and exporters.
"""
import io
import uuid
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api import artifacts as artifacts_api
from backend.app.artifacts.document import ExportError
from backend.app.database import get_db
from backend.app.main import app

FENCE = "```"
EXECUTION_ID = uuid.uuid4()
WORKFLOW = SimpleNamespace(id=uuid.uuid4(), name="FastAPI CRUD", status="completed")


def record(name: str, order: int, result, mode=None, status="completed"):
    now = datetime.now(timezone.utc)
    stage = SimpleNamespace(id=uuid.uuid4(), name=name, stage_order=order,
                            config={"output_mode": mode} if mode else {})
    return SimpleNamespace(
        id=uuid.uuid4(), stage_id=stage.id, stage=stage, workflow=WORKFLOW, execution_id=EXECUTION_ID,
        model_used="m", provider="groq", input_tokens=10, output_tokens=20, total_tokens=30, latency_ms=5,
        estimated_cost=Decimal("0.001"), status=status, result=result, error_message=None,
        started_at=now, completed_at=now, duration_ms=5, cache_hit=False, metadata_={},
    )


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    """Answers every query with the configured records (handlers filter by id in SQL only)."""

    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _query):
        return FakeResult(self.rows)


@pytest.fixture
def use_records():
    def configure(*rows):
        session = FakeSession(list(rows))

        async def fake_db():
            yield session
        app.dependency_overrides[get_db] = fake_db
        return list(rows)
    yield configure
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


EXPLANATION = "# Binary Trees\n\nA **tree** with `nodes`.\n\n| a | b |\n|---|---|\n| 1 | 2 |"
BACKEND = f"Backend:\n\n{FENCE}python path=backend/main.py\napp = 1\n{FENCE}\n{FENCE}text path=README.md\nv1\n{FENCE}"
TESTS = f"{FENCE}python path=tests/test_main.py\ndef test(): ...\n{FENCE}\n{FENCE}markdown path=README.md\nv2\n{FENCE}"


class TestExecutionDetails:
    async def test_stages_without_output_mode_are_unchanged(self, client, use_records):
        rows = use_records(record("Explain", 0, EXPLANATION))
        body = (await client.get(f"/api/executions/{EXECUTION_ID}")).json()
        stage = body["stages"][0]
        assert stage["result"] == EXPLANATION and stage["artifact"] is None
        assert body["artifact"] is None
        assert stage["model_used"] == "m" and stage["total_tokens"] == 30  # existing fields intact
        assert rows[0].result == EXPLANATION

    async def test_file_stages_get_artifacts_and_a_combined_project(self, client, use_records):
        use_records(record("Requirements", 0, "Plain text", "explanation"),
                    record("Backend", 1, BACKEND, "project"),
                    record("Tests", 2, TESTS, "project"))
        body = (await client.get(f"/api/executions/{EXECUTION_ID}")).json()
        stages = {s["stage_name"]: s for s in body["stages"]}
        assert stages["Requirements"]["artifact"]["artifact_type"] == "explanation"
        assert [f["path"] for f in stages["Backend"]["artifact"]["files"]] == ["backend/main.py", "README.md"]
        assert stages["Backend"]["result"] == BACKEND  # raw output preserved alongside the artifact
        combined = body["artifact"]
        assert [f["path"] for f in combined["files"]] == ["backend/main.py", "README.md", "tests/test_main.py"]
        assert combined["conflicts"] == [{"path": "README.md", "kept_from": "Tests", "overridden_from": "Backend"}]

    async def test_invalid_artifact_falls_back_to_text(self, client, use_records):
        bad = f"{FENCE}python path=../../etc/evil.py\nx\n{FENCE}"
        use_records(record("Backend", 0, bad, "project"))
        stage = (await client.get(f"/api/executions/{EXECUTION_ID}")).json()["stages"][0]
        assert stage["artifact"] is None and stage["result"] == bad

    async def test_failed_stage_has_no_artifact(self, client, use_records):
        use_records(record("Backend", 0, None, "project", status="failed"))
        stage = (await client.get(f"/api/executions/{EXECUTION_ID}")).json()["stages"][0]
        assert stage["artifact"] is None


class TestDocumentDownload:
    async def test_pdf(self, client, use_records):
        (r,) = use_records(record("Binary Trees", 0, EXPLANATION))
        resp = await client.get(f"/api/executions/{EXECUTION_ID}/stages/{r.stage_id}/document?format=pdf")
        assert resp.status_code == 200 and resp.headers["content-type"] == "application/pdf"
        assert resp.content.startswith(b"%PDF-")
        assert 'filename="binary-trees.pdf"' in resp.headers["content-disposition"]

    async def test_txt(self, client, use_records):
        (r,) = use_records(record("Binary Trees", 0, EXPLANATION + "\n\nCafé ✓"))
        resp = await client.get(f"/api/executions/{EXECUTION_ID}/stages/{r.stage_id}/document?format=txt")
        assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/plain")
        text = resp.content.decode("utf-8")
        assert text.startswith("============\nBinary Trees\n============") and "Café ✓" in text
        assert "**" not in text and "`" not in text

    async def test_unicode_stage_name_gets_safe_headers(self, client, use_records):
        (r,) = use_records(record('Résumé "draft"', 0, "text"))
        resp = await client.get(f"/api/executions/{EXECUTION_ID}/stages/{r.stage_id}/document?format=txt")
        disposition = resp.headers["content-disposition"]
        assert resp.status_code == 200 and disposition.isascii() and "filename*=UTF-8''" in disposition

    @pytest.mark.parametrize("result, status", [(None, "failed"), ("   ", "completed"), ("x", "running")])
    async def test_no_output_is_404(self, client, use_records, result, status):
        (r,) = use_records(record("S", 0, result, status=status))
        resp = await client.get(f"/api/executions/{EXECUTION_ID}/stages/{r.stage_id}/document")
        assert resp.status_code == 404

    async def test_unknown_stage_is_404_and_bad_format_is_422(self, client, use_records):
        use_records()
        assert (await client.get(f"/api/executions/{EXECUTION_ID}/stages/{uuid.uuid4()}/document")).status_code == 404
        (r,) = use_records(record("S", 0, "x"))
        assert (await client.get(f"/api/executions/{EXECUTION_ID}/stages/{r.stage_id}/document?format=docx")).status_code == 422

    async def test_export_failure_is_a_controlled_error(self, client, use_records, monkeypatch):
        def broken(*_args):
            raise ExportError("layout exploded")
        monkeypatch.setattr(artifacts_api, "render_pdf", broken)
        (r,) = use_records(record("S", 0, EXPLANATION))
        resp = await client.get(f"/api/executions/{EXECUTION_ID}/stages/{r.stage_id}/document?format=pdf")
        assert resp.status_code == 422 and "layout exploded" in resp.json()["detail"]
        assert r.result == EXPLANATION and r.status == "completed"


class TestZipDownload:
    async def test_stage_zip_keeps_structure(self, client, use_records):
        (r,) = use_records(record("Backend", 0, BACKEND, "project"))
        resp = await client.get(f"/api/executions/{EXECUTION_ID}/stages/{r.stage_id}/artifact.zip")
        assert resp.status_code == 200 and resp.headers["content-type"] == "application/zip"
        assert 'filename="backend.zip"' in resp.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            assert z.namelist() == ["backend/backend/main.py", "backend/README.md"]
            assert z.read("backend/backend/main.py") == b"app = 1\n"

    async def test_stage_without_files_is_404(self, client, use_records):
        (r,) = use_records(record("Explain", 0, EXPLANATION))
        assert (await client.get(f"/api/executions/{EXECUTION_ID}/stages/{r.stage_id}/artifact.zip")).status_code == 404

    async def test_execution_zip_combines_stages(self, client, use_records):
        use_records(record("Backend", 0, BACKEND, "project"), record("Tests", 1, TESTS, "project"))
        resp = await client.get(f"/api/executions/{EXECUTION_ID}/artifact.zip")
        assert resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            assert z.namelist() == ["fastapi-crud/backend/main.py", "fastapi-crud/README.md", "fastapi-crud/tests/test_main.py"]
            assert z.read("fastapi-crud/README.md") == b"v2\n"

    async def test_execution_without_combined_project_is_404(self, client, use_records):
        use_records(record("Backend", 0, BACKEND, "project"))
        assert (await client.get(f"/api/executions/{EXECUTION_ID}/artifact.zip")).status_code == 404


class TestPlannerOutputMode:
    def test_output_mode_is_optional_and_tolerant(self):
        from backend.app.schemas.planner import StagePlan
        base = dict(id="impl", name="Impl", description="Implement the thing.", instruction="Write the code now.",
                    stage_type="generation", expected_output="Working code files.")
        assert StagePlan(**base).output_mode is None
        assert StagePlan(**base, output_mode="Project").output_mode == "project"
        assert StagePlan(**base, output_mode="binary").output_mode is None  # unknown values never fail the plan
        assert StagePlan(**base, output_mode=5).output_mode is None
