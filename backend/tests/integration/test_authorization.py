"""
Authentication and user isolation (BOLA/IDOR) tests.

User A is the default `client` (fixture `test_user`); user B is created with
`make_user_client`. B's resources are inserted directly with B as owner, then A tries
to reach them by ID through every endpoint. Each denial has a positive control (B can
reach the same resource) so a 404 can't come from a broken fixture.

Policy under test: anonymous -> 401; another user's resource -> the same 404 as a
resource that does not exist.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.testclient import TestClient

from backend.app.database import get_session_factory
from backend.app.main import app
from backend.app.models import CacheEntry, ExecutionRecord, RoutingDecision, Stage, StageDependency, Workflow
from backend.app.services.cache.semantic_cache import SemanticCacheService
from backend.app.services.execution.tracker import tracker
from backend.tests.conftest import TEST_DATABASE_URL, text_hash_embedding

FENCE = "```"
PROJECT_A = f"{FENCE}python path=app/main.py\nprint('b secret')\n{FENCE}"
PROJECT_B = f"{FENCE}text path=README.md\nB private notes\n{FENCE}"
NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures: user B and a full tree of B-owned resources
# ---------------------------------------------------------------------------

@pytest.fixture
async def user_b(make_user_client):
    return await make_user_client(f"b-{uuid.uuid4().hex[:8]}@example.com")


@pytest.fixture
async def b_tree(db_session, user_b):
    """B's workflow with two project-output stages, a dependency, a finished execution
    (records with generated files), a cache entry, a routing decision and a live run."""
    b, _ = user_b
    wf = Workflow(name="B private workflow", objective="B secret objective", user_id=b.id)
    db_session.add(wf)
    await db_session.flush()
    s1 = Stage(workflow_id=wf.id, name="B backend", instruction="b", stage_order=0, stage_type="generation",
               config={"output_mode": "project"})
    s2 = Stage(workflow_id=wf.id, name="B docs", instruction="b", stage_order=1, stage_type="documentation",
               config={"output_mode": "project"})
    db_session.add_all([s1, s2])
    await db_session.flush()
    dep = StageDependency(stage_id=s2.id, depends_on_stage_id=s1.id)
    db_session.add(dep)
    execution_id = uuid.uuid4()
    for stage, result in ((s1, PROJECT_A), (s2, PROJECT_B)):
        db_session.add(ExecutionRecord(
            workflow_id=wf.id, stage_id=stage.id, execution_id=execution_id, status="completed",
            result=result, started_at=NOW, completed_at=NOW + timedelta(seconds=1),
            model_used="m", provider="fake", input_tokens=1, output_tokens=1,
        ))
    entry = CacheEntry(workflow_id=wf.id, stage_id=s1.id, stage_type="generation",
                       input_text="B secret prompt", input_embedding=text_hash_embedding("B secret prompt"),
                       result="B secret cached answer")
    db_session.add(entry)
    decision = RoutingDecision(execution_id=execution_id, stage_id=s1.id, stage_type="generation",
                               selected_provider="fake", selected_model_name="b-model")
    db_session.add(decision)
    await db_session.commit()

    live_id = uuid.uuid4()
    tracker.register(live_id, wf.id, wf.name).status = "running"
    return dict(workflow=wf, s1=s1, s2=s2, dep=dep, execution_id=execution_id, entry=entry, live_id=live_id)


@pytest.fixture
async def a_workflow(client):
    """A workflow user A creates through the API (owned via the session, not the request body)."""
    wf = (await client.post("/api/workflows", json={"name": "A workflow"})).json()
    stage = (await client.post("/api/stages", json={
        "workflow_id": wf["id"], "name": "A stage", "instruction": "a", "stage_order": 0,
    })).json()
    return dict(id=wf["id"], stage_id=stage["id"])


# ---------------------------------------------------------------------------
# 1. Authentication: every protected endpoint rejects anonymous callers
# ---------------------------------------------------------------------------

X = str(uuid.uuid4())
PROTECTED = [
    ("GET", "/api/workflows"), ("POST", "/api/workflows"), ("GET", f"/api/workflows/{X}"),
    ("PATCH", f"/api/workflows/{X}"), ("DELETE", f"/api/workflows/{X}"), ("POST", f"/api/workflows/{X}/validate"),
    ("POST", "/api/stages"), ("GET", f"/api/stages/workflow/{X}"), ("GET", f"/api/stages/{X}"),
    ("PATCH", f"/api/stages/{X}"), ("DELETE", f"/api/stages/{X}"), ("PUT", f"/api/stages/workflow/{X}/reorder"),
    ("POST", f"/api/stages/{X}/dependencies"), ("DELETE", f"/api/stages/dependencies/{X}"),
    ("POST", f"/api/workflows/{X}/execute"), ("GET", "/api/executions"), ("GET", f"/api/executions/{X}"),
    ("GET", f"/api/workflows/{X}/executions/latest"), ("GET", f"/api/workflows/{X}/executions/live"),
    ("GET", f"/api/executions/{X}/status"), ("POST", f"/api/executions/{X}/pause"),
    ("POST", f"/api/executions/{X}/resume"), ("POST", f"/api/executions/{X}/cancel"), ("GET", f"/api/workflows/{X}/dag"),
    ("GET", f"/api/executions/{X}/stages/{X}/document"), ("GET", f"/api/executions/{X}/stages/{X}/artifact.zip"),
    ("GET", f"/api/executions/{X}/artifact.zip"),
    ("GET", "/api/cache/entries"), ("GET", "/api/cache/stats"), ("DELETE", f"/api/cache/entries/{X}"),
    ("POST", "/api/cache/clear"), ("POST", "/api/cache/cleanup-expired"), ("POST", f"/api/cache/warm?workflow_id={X}"),
    ("POST", f"/api/cache/refresh/{X}"), ("GET", f"/api/cache/hit-rate/{X}"),
    ("GET", "/api/analytics/overview"), ("GET", f"/api/analytics/workflows/{X}"), ("GET", "/api/analytics/stage-types"),
    ("GET", "/api/analytics/cache"), ("GET", "/api/analytics/models"), ("GET", "/api/analytics/latency"),
    ("GET", "/api/analytics/costs"), ("GET", "/api/analytics/tokens"), ("GET", "/api/analytics/routing"),
    ("GET", f"/api/analytics/timeline/{X}"), ("GET", "/api/analytics/export"),
    ("GET", "/api/routing/rules"), ("GET", "/api/routing/rules/analysis"), ("POST", "/api/routing/rules"),
    ("PUT", "/api/routing/rules/analysis"), ("DELETE", "/api/routing/rules/analysis"),
    ("GET", "/api/routing/decisions"), ("GET", f"/api/routing/preview/{X}"),
    ("GET", "/api/models"), ("GET", "/api/models/compare"), ("GET", "/api/models/groq/x"), ("PATCH", "/api/models/groq/x"),
    ("POST", "/api/planner/analyze"), ("POST", "/api/planner/generate"),
    ("GET", "/api/auth/me"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_anonymous_requests_are_rejected(anon_client, method, path):
    response = await anon_client.request(method, path, json={})
    assert response.status_code == 401, (method, path, response.status_code)
    assert response.json() == {"detail": "Not authenticated"}  # nothing about the resource leaks


async def test_invalid_session_token_is_rejected(anon_client):
    anon_client.cookies.set("session_token", "forged-or-expired-token")
    assert (await anon_client.get("/api/workflows")).status_code == 401


async def test_every_api_route_is_covered_by_authentication():
    """Guards against a new router being mounted without the auth dependency."""
    from fastapi.routing import APIRoute

    public = {"/health", "/", "/api/auth/register", "/api/auth/login", "/api/auth/logout",
              "/api/auth/forgot-password", "/api/auth/reset-password"}

    def names(dep):
        found = {getattr(dep.call, "__name__", "")}
        for d in dep.dependencies:
            found |= names(d)
        return found

    unprotected = {r.path for r in app.routes
                   if isinstance(r, APIRoute) and "get_current_active_user" not in names(r.dependant)}
    assert unprotected <= public, unprotected - public


async def test_public_endpoints_stay_public(anon_client):
    assert (await anon_client.get("/health")).status_code == 200


# ---------------------------------------------------------------------------
# 2. Workflow isolation
# ---------------------------------------------------------------------------

async def test_each_user_lists_only_their_own_workflows(client, user_b, a_workflow, b_tree):
    _, b_client = user_b
    a_list = (await client.get("/api/workflows")).json()
    b_list = (await b_client.get("/api/workflows")).json()
    assert [w["id"] for w in a_list["items"]] == [a_workflow["id"]] and a_list["total"] == 1
    assert [w["id"] for w in b_list["items"]] == [str(b_tree["workflow"].id)] and b_list["total"] == 1


async def test_owner_comes_from_session_not_request_body(client, db_session, user_b):
    b, _ = user_b
    created = (await client.post("/api/workflows", json={"name": "spoof", "user_id": str(b.id)})).json()
    owner = await db_session.scalar(select(Workflow.user_id).where(Workflow.id == uuid.UUID(created["id"])))
    assert owner != b.id


async def test_cannot_read_modify_or_delete_another_users_workflow(client, user_b, b_tree, db_session):
    _, b_client = user_b
    wid = b_tree["workflow"].id
    for method, path, body in [
        ("GET", f"/api/workflows/{wid}", None), ("PATCH", f"/api/workflows/{wid}", {"name": "pwned"}),
        ("DELETE", f"/api/workflows/{wid}", None), ("POST", f"/api/workflows/{wid}/validate", None),
        ("GET", f"/api/workflows/{wid}/dag", None), ("GET", f"/api/stages/workflow/{wid}", None),
        ("PUT", f"/api/stages/workflow/{wid}/reorder", {"stage_ids": [str(b_tree["s2"].id), str(b_tree["s1"].id)]}),
        ("POST", f"/api/workflows/{wid}/execute", {"default_provider": "fake"}),
        ("GET", f"/api/workflows/{wid}/executions/latest", None), ("GET", f"/api/workflows/{wid}/executions/live", None),
    ]:
        response = await client.request(method, path, json=body)
        assert response.status_code == 404, (method, path, response.status_code)

    # Nothing changed, and B still has full access (positive control)
    workflow = (await b_client.get(f"/api/workflows/{wid}")).json()
    assert workflow["name"] == "B private workflow"
    assert [s["stage_order"] for s in workflow["stages"]] == [0, 1]
    assert (await b_client.get(f"/api/workflows/{wid}/dag")).status_code == 200


async def test_foreign_and_nonexistent_ids_are_indistinguishable(client, b_tree):
    foreign = await client.get(f"/api/workflows/{b_tree['workflow'].id}")
    missing = await client.get(f"/api/workflows/{uuid.uuid4()}")
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


async def test_unowned_legacy_workflows_are_hidden_from_everyone(client, user_b, db_session):
    _, b_client = user_b
    legacy = Workflow(name="pre-ownership workflow")
    legacy._test_unowned = True  # bypass the test helper that assigns the default owner
    db_session.add(legacy)
    await db_session.commit()
    assert legacy.user_id is None
    for c in (client, b_client):
        assert (await c.get(f"/api/workflows/{legacy.id}")).status_code == 404
        assert all(w["id"] != str(legacy.id) for w in (await c.get("/api/workflows")).json()["items"])


# ---------------------------------------------------------------------------
# 3. Stages and dependencies (parent-child relationships)
# ---------------------------------------------------------------------------

async def test_cannot_touch_another_users_stages(client, user_b, b_tree):
    _, b_client = user_b
    sid = b_tree["s1"].id
    for method, path, body in [
        ("GET", f"/api/stages/{sid}", None), ("PATCH", f"/api/stages/{sid}", {"name": "pwned"}),
        ("DELETE", f"/api/stages/{sid}", None),
        ("POST", "/api/stages", {"workflow_id": str(b_tree["workflow"].id), "name": "x", "instruction": "x", "stage_order": 5}),
        ("DELETE", f"/api/stages/dependencies/{b_tree['dep'].id}", None),
        ("POST", f"/api/stages/{sid}/dependencies", {"depends_on_stage_id": str(b_tree["s2"].id)}),
    ]:
        response = await client.request(method, path, json=body)
        assert response.status_code == 404, (method, path, response.status_code)
    assert (await b_client.get(f"/api/stages/{sid}")).json()["name"] == "B backend"
    assert len((await b_client.get(f"/api/stages/workflow/{b_tree['workflow'].id}")).json()) == 2


async def test_cannot_link_own_stage_to_another_users_stage(client, a_workflow, b_tree):
    response = await client.post(f"/api/stages/{a_workflow['stage_id']}/dependencies",
                                 json={"depends_on_stage_id": str(b_tree["s1"].id)})
    assert response.status_code == 404


async def test_dependencies_must_stay_within_one_workflow(client):
    wf1 = (await client.post("/api/workflows", json={"name": "one"})).json()
    wf2 = (await client.post("/api/workflows", json={"name": "two"})).json()
    s1 = (await client.post("/api/stages", json={"workflow_id": wf1["id"], "name": "a", "instruction": "a", "stage_order": 0})).json()
    s2 = (await client.post("/api/stages", json={"workflow_id": wf2["id"], "name": "b", "instruction": "b", "stage_order": 0})).json()
    response = await client.post(f"/api/stages/{s1['id']}/dependencies", json={"depends_on_stage_id": s2["id"]})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# 4. Executions, live control, artifacts and downloads
# ---------------------------------------------------------------------------

async def test_cannot_access_another_users_execution(client, user_b, b_tree):
    _, b_client = user_b
    eid, live = b_tree["execution_id"], b_tree["live_id"]
    for method, path in [
        ("GET", f"/api/executions/{eid}"), ("GET", f"/api/analytics/timeline/{eid}"),
        ("GET", f"/api/executions/{live}/status"), ("POST", f"/api/executions/{live}/pause"),
        ("POST", f"/api/executions/{live}/resume"), ("POST", f"/api/executions/{live}/cancel"),
    ]:
        response = await client.request(method, path)
        assert response.status_code == 404, (method, path, response.status_code)
    assert tracker.get(live).status == "running"  # A's cancel/pause did nothing

    assert (await b_client.get(f"/api/executions/{eid}")).status_code == 200
    assert (await b_client.get(f"/api/executions/{live}/status")).status_code == 200
    assert (await client.get("/api/executions")).json() == []
    assert [e["execution_id"] for e in (await b_client.get("/api/executions")).json()] == [str(eid)]


async def test_cannot_download_another_users_artifacts(client, user_b, b_tree):
    _, b_client = user_b
    eid, sid = b_tree["execution_id"], b_tree["s1"].id
    paths = [
        f"/api/executions/{eid}/stages/{sid}/document?format=txt",
        f"/api/executions/{eid}/stages/{sid}/artifact.zip",
        f"/api/executions/{eid}/artifact.zip",
    ]
    for path in paths:
        assert (await client.get(path)).status_code == 404, path
    for path in paths:  # the owner can download all three
        response = await b_client.get(path)
        assert response.status_code == 200, (path, response.text)
    assert b"b secret" in (await b_client.get(paths[0])).content


async def test_mismatched_execution_and_stage_ids_are_rejected(client, a_workflow, user_b, b_tree):
    _, b_client = user_b
    # B's execution with A's stage, and B's execution with a stage it never ran
    assert (await client.get(f"/api/executions/{b_tree['execution_id']}/stages/{a_workflow['stage_id']}/artifact.zip")).status_code == 404
    assert (await b_client.get(f"/api/executions/{b_tree['execution_id']}/stages/{uuid.uuid4()}/document")).status_code == 404


async def test_end_to_end_execution_is_private_to_its_owner(client, user_b, fake_provider, mock_embeddings):
    """Regression: a real execution still works for its owner and stays invisible to others."""
    _, b_client = user_b
    wf = (await client.post("/api/workflows", json={"name": "Runs"})).json()
    await client.post("/api/stages", json={"workflow_id": wf["id"], "name": "Only", "instruction": "Say hi", "stage_order": 0})
    started = await client.post(f"/api/workflows/{wf['id']}/execute",
                                json={"default_provider": "fake", "use_routing": False, "use_cache": False})
    assert started.status_code == 200, started.text
    eid = started.json()["execution_id"]

    details = await client.get(f"/api/executions/{eid}")
    assert details.status_code == 200 and details.json()["stages"][0]["status"] == "completed"
    assert (await client.get(f"/api/workflows/{wf['id']}/executions/latest")).status_code == 200
    assert (await b_client.get(f"/api/executions/{eid}")).status_code == 404
    assert (await b_client.get(f"/api/workflows/{wf['id']}/executions/latest")).status_code == 404


# ---------------------------------------------------------------------------
# 5. Cache, analytics and routing data
# ---------------------------------------------------------------------------

async def test_cache_endpoints_only_see_own_entries(client, user_b, b_tree, db_session):
    _, b_client = user_b
    entry_id = b_tree["entry"].id
    assert (await client.get("/api/cache/entries")).json() == []
    assert (await client.get("/api/cache/stats")).json()["total_entries"] == 0
    assert (await client.delete(f"/api/cache/entries/{entry_id}")).status_code == 404
    assert (await client.get(f"/api/cache/hit-rate/{b_tree['workflow'].id}")).status_code == 404
    assert (await client.post(f"/api/cache/clear?workflow_id={b_tree['workflow'].id}")).status_code == 404
    assert (await client.post("/api/cache/clear")).json()["entries_invalidated"] == 0  # "clear all" = all of A's

    await db_session.refresh(b_tree["entry"])
    assert b_tree["entry"].is_valid is True
    assert [e["id"] for e in (await b_client.get("/api/cache/entries")).json()] == [str(entry_id)]


async def test_semantic_cache_never_serves_another_users_output(db_session, user_b, b_tree, test_user, mock_embeddings):
    """The data-leak path: an identical prompt from A must not return B's cached result."""
    a_wf = Workflow(name="A", user_id=test_user.id)
    b_other = Workflow(name="B second", user_id=b_tree["workflow"].user_id)
    db_session.add_all([a_wf, b_other])
    await db_session.commit()
    cache = SemanticCacheService(db_session)

    as_a = await cache.lookup("B secret prompt", stage_type="generation", scope_workflow_id=a_wf.id)
    as_b = await cache.lookup("B secret prompt", stage_type="generation", scope_workflow_id=b_other.id)
    assert as_a.cache_hit is False
    assert as_b.cache_hit is True and as_b.entry.result == "B secret cached answer"


async def test_analytics_only_count_own_executions(client, user_b, b_tree):
    _, b_client = user_b
    assert (await client.get("/api/analytics/overview")).json()["total_executions"] == 0
    assert (await b_client.get("/api/analytics/overview")).json()["total_executions"] == 1
    assert (await client.get(f"/api/analytics/workflows/{b_tree['workflow'].id}")).json()["total_executions"] == 0
    assert (await client.get("/api/analytics/routing")).json()["total_decisions"] == 0
    export = await client.get("/api/analytics/export?format=json&dataset=stage_runs")
    assert str(b_tree["execution_id"]) not in export.text


async def test_routing_decisions_and_preview_are_private(client, user_b, b_tree):
    _, b_client = user_b
    assert (await client.get("/api/routing/decisions")).json() == []
    assert len((await b_client.get("/api/routing/decisions")).json()) == 1
    assert (await client.get(f"/api/routing/preview/{b_tree['workflow'].id}")).status_code == 404


# ---------------------------------------------------------------------------
# 6. WebSocket
# ---------------------------------------------------------------------------

@pytest.fixture
def ws_app():
    def factory():
        return async_sessionmaker(create_async_engine(TEST_DATABASE_URL, poolclass=NullPool), expire_on_commit=False)
    app.dependency_overrides[get_session_factory] = factory
    yield
    app.dependency_overrides.pop(get_session_factory, None)


def ws_close_code(execution_id, token=None) -> int:
    """Connect and return the close code the server refused the handshake with."""
    from starlette.websockets import WebSocketDisconnect
    headers = {"cookie": f"session_token={token}"} if token else {}
    try:
        with TestClient(app).websocket_connect(f"/ws/executions/{execution_id}", headers=headers) as ws:
            ws.receive_json()
    except WebSocketDisconnect as e:
        return e.code
    return 1000  # connected and received data


async def test_websocket_requires_authentication(ws_app, b_tree):
    assert ws_close_code(b_tree["live_id"]) == 4401
    assert ws_close_code(b_tree["live_id"], "forged-token") == 4401


async def test_websocket_rejects_another_users_execution(ws_app, test_user, user_b, b_tree):
    b, b_client = user_b
    assert ws_close_code(b_tree["live_id"], test_user.session_token) == 4404
    assert ws_close_code(b_tree["execution_id"], test_user.session_token) == 4404
    assert ws_close_code(uuid.uuid4(), test_user.session_token) == 4404
    assert ws_close_code("not-a-uuid", test_user.session_token) == 4404
    # Positive control: B watches its own live execution
    assert ws_close_code(b_tree["live_id"], b_client.cookies.get("session_token")) == 1000
