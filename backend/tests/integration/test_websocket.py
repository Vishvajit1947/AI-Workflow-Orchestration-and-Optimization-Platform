"""
WebSocket live status tests: the /ws/executions/{id} endpoint, the connection
manager, and the event stream an execution publishes.
"""
import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.testclient import TestClient

from backend.app.database import get_session_factory
from backend.app.main import app
from backend.app.models import ExecutionRecord, Workflow
from backend.tests.conftest import TEST_DATABASE_URL
from backend.app.services.execution import ExecutionEngine
from backend.app.services.execution.tracker import tracker
from backend.app.services.websocket.execution_ws import ConnectionManager, manager
from backend.tests.integration.test_phase5_integration import make_workflow, run_options, scripted  # noqa: F401 (fixture)


class FakeSocket:
    """Stands in for a connected client: records what it's sent."""

    def __init__(self, fail: bool = False):
        self.sent: list[dict] = []
        self.fail = fail

    async def accept(self):
        pass

    async def send_json(self, message: dict):
        if self.fail:
            raise RuntimeError("connection closed")
        self.sent.append(message)


# ---------- endpoint (real WebSocket transport, authenticated against the test DB) ----------

@pytest.fixture
def ws_app():
    """
    The endpoint authenticates through get_session_factory. TestClient runs the app in its
    own event loop, so the override builds an engine there (asyncpg connections are loop-bound).
    """
    def factory():
        return async_sessionmaker(create_async_engine(TEST_DATABASE_URL, poolclass=NullPool), expire_on_commit=False)

    app.dependency_overrides[get_session_factory] = factory
    yield app
    app.dependency_overrides.pop(get_session_factory, None)


def ws_connect(execution_id, token: str | None):
    headers = {"cookie": f"session_token={token}"} if token else {}
    return TestClient(app).websocket_connect(f"/ws/executions/{execution_id}", headers=headers)


async def test_owned_finished_execution_and_heartbeat(ws_app, db_session, test_user):
    # An execution of the user's workflow that this server no longer holds in memory
    workflow = Workflow(name="WS")
    db_session.add(workflow)
    await db_session.flush()
    execution_id = uuid.uuid4()
    db_session.add(ExecutionRecord(workflow_id=workflow.id, execution_id=execution_id, status="completed"))
    await db_session.commit()

    with ws_connect(execution_id, test_user.session_token) as ws:
        assert ws.receive_json()["type"] == "unknown_execution"
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}


async def test_snapshot_sent_on_connect(ws_app, db_session, test_user):
    workflow = Workflow(name="WS live")
    db_session.add(workflow)
    await db_session.commit()
    execution_id = uuid.uuid4()
    live = tracker.register(execution_id, workflow.id, "WF")
    live.status = "running"
    live.stages = {"s1": {"stage_id": str(uuid.uuid4()), "name": "A", "stage_order": 0, "stage_type": None,
                          "level": 0, "status": "running", "provider": "openai", "model": "gpt-4o-mini",
                          "cache_hit": False, "error": None, "started_at": None, "completed_at": None}}

    with ws_connect(execution_id, test_user.session_token) as ws:
        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot"
        assert snapshot["status"] == "running"
        assert snapshot["stages"][0]["name"] == "A"
        assert manager.connection_count(str(execution_id)) == 1
    assert manager.connection_count(str(execution_id)) == 0  # cleaned up on disconnect


# ---------- connection manager ----------

async def test_broadcast_reaches_all_clients_and_drops_dead_ones():
    mgr = ConnectionManager()
    good1, good2, dead = FakeSocket(), FakeSocket(), FakeSocket(fail=True)
    for ws in (good1, good2, dead):
        await mgr.connect(ws, "exec-1")
    other = FakeSocket()
    await mgr.connect(other, "exec-2")

    await mgr.broadcast("exec-1", {"type": "stage_update"})

    assert good1.sent == good2.sent == [{"type": "stage_update"}]
    assert other.sent == []
    assert mgr.connection_count("exec-1") == 2  # the failing client was dropped


# ---------- event stream from a real execution ----------

async def test_execution_publishes_live_events(db_session, scripted):  # noqa: F811
    scripted(openai=dict(delay=0.05))
    workflow = await make_workflow(db_session, ("Start", 0), ("B1", 1), ("B2", 1))
    execution_id = uuid.uuid4()
    client = FakeSocket()
    await manager.connect(client, str(execution_id))
    try:
        await ExecutionEngine(db_session).execute_workflow(workflow.id, execution_id=execution_id, **run_options())
    finally:
        manager.disconnect(client, str(execution_id))

    types = [m["type"] for m in client.sent]
    assert types[0] == "snapshot" and types[-1] == "execution_status"
    assert client.sent[-1]["status"] == "completed" and client.sent[-1]["progress"] == 1.0

    updates = [m["stage"] for m in client.sent if m["type"] == "stage_update"]
    for name in ("Start", "B1", "B2"):
        sequence = [u["status"] for u in updates if u["name"] == name]
        assert sequence[0] == "running" and sequence[-1] == "completed"
    # Progress only ever grows
    progress = [m["progress"] for m in client.sent if "progress" in m]
    assert progress == sorted(progress)
    # Start completes before either branch starts
    first_branch_start = min(i for i, u in enumerate(updates) if u["name"] in ("B1", "B2"))
    start_done = next(i for i, u in enumerate(updates) if u["name"] == "Start" and u["status"] == "completed")
    assert start_done < first_branch_start
