"""
Phase 5 Integration Tests — parallel execution, error handling, live status and control.

LLM calls go to ScriptedProviders registered under real provider names; they can
delay, fail per model, or block on a gate so tests can pause/cancel mid-flight.
"""
import asyncio
import time
import uuid
from typing import Optional

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.config import settings
from backend.app.database import get_session_factory
from backend.app.main import app
from backend.app.models import ExecutionRecord, RoutingDecision, Stage, StageDependency, Workflow, WorkflowContext
from backend.app.services.execution import ExecutionEngine
from backend.app.services.execution.error_handler import circuit_breaker
from backend.app.services.execution.tracker import tracker
from backend.app.services.llm import registry
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse
from backend.app.services.router.model_registry import ModelRegistry
from backend.app.services.router.routing_rules import RoutingRulesManager

pytestmark = pytest.mark.integration


class HTTPError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class ScriptedProvider(BaseLLMProvider):
    def __init__(self, name: str, delay: float = 0.0, fail_models: Optional[dict] = None,
                 gate: Optional[asyncio.Event] = None):
        self.provider_name = name
        self.delay = delay
        self.fail_models = fail_models or {}  # model -> exception raised on every call
        self.gate = gate                      # calls wait for this event when set
        self.calls: list[tuple[str, float]] = []
        self.prompts: list[str] = []
        self.in_flight = 0

    async def generate(self, prompt, model=None, temperature=0.7, max_tokens=4096, system_prompt=None):
        self.calls.append((model, time.perf_counter()))
        self.prompts.append(prompt)
        self.in_flight += 1
        try:
            if self.gate is not None:
                await self.gate.wait()
            if self.delay:
                await asyncio.sleep(self.delay)
            if model in self.fail_models:
                raise self.fail_models[model]
            stage_name = prompt.rsplit("[Current Task: ", 1)[-1].split("]", 1)[0]
            return LLMResponse(content=f"output of {stage_name}", model=model, provider=self.provider_name,
                               input_tokens=100, output_tokens=50, total_tokens=150,
                               latency_ms=int(self.delay * 1000), estimated_cost=0.0001)
        finally:
            self.in_flight -= 1

    def get_available_models(self):
        return []

    def get_default_model(self):
        return f"{self.provider_name}-default"


@pytest.fixture
def scripted(providers, mock_embeddings):
    """Register ScriptedProviders: scripted(openai=dict(delay=0.2), ...) -> {name: provider}."""
    providers()  # empty the registry

    def register(**specs) -> dict[str, ScriptedProvider]:
        made = {name: ScriptedProvider(name, **spec) for name, spec in specs.items()}
        for p in made.values():
            registry.register(p)
        return made
    return register


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(settings, "RETRY_BACKOFF_INITIAL_SECONDS", 0.01)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKOFF_SECONDS", 0.01)


async def make_workflow(db, *stages: tuple[str, int], objective: str = "Test") -> Workflow:
    """Workflow with (name, stage_order) stages; equal orders run in parallel."""
    workflow = Workflow(name="Phase 5 Test", objective=objective)
    db.add(workflow)
    await db.flush()
    for name, order in stages:
        db.add(Stage(workflow_id=workflow.id, name=name, instruction=f"Do {name}",
                     stage_order=order, stage_type="analysis"))
    await db.commit()
    return workflow


async def stage_map(db, workflow: Workflow) -> dict[str, Stage]:
    result = await db.execute(select(Stage).where(Stage.workflow_id == workflow.id))
    return {s.name: s for s in result.scalars().all()}


async def records_by_stage(db, execution_id) -> dict[str, ExecutionRecord]:
    result = await db.execute(select(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id))
    records = result.scalars().all()
    names = {s.id: s.name for s in (await db.execute(select(Stage))).scalars().all()}
    return {names[r.stage_id]: r for r in records}


async def wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.perf_counter() + timeout
    while not condition():
        if time.perf_counter() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


def run_options(**overrides) -> dict:
    return dict(default_provider="openai", use_cache=False, use_routing=False, **overrides)


# ============================================================================
# Parallel execution
# ============================================================================

async def test_parallel_stages_run_concurrently_and_faster(db_session, scripted):
    delay = 0.5
    [openai] = scripted(openai=dict(delay=delay)).values()
    workflow = await make_workflow(db_session, ("A", 0), ("B", 0), ("C", 0), ("D", 0))

    start = time.perf_counter()
    execution_id = await ExecutionEngine(db_session).execute_workflow(workflow.id, **run_options(parallel=True))
    parallel_time = time.perf_counter() - start
    await db_session.commit()

    start = time.perf_counter()
    await ExecutionEngine(db_session).execute_workflow(workflow.id, **run_options(parallel=False))
    sequential_time = time.perf_counter() - start

    records = await records_by_stage(db_session, execution_id)
    assert {r.status for r in records.values()} == {"completed"}
    first_four = sorted(t for _, t in openai.calls[:4])
    assert first_four[-1] - first_four[0] < 0.1  # all four started together
    # Both runs pay the same database overhead; parallel saves the LLM waiting time
    # of 3 of the 4 stages (1.5s ideal)
    assert sequential_time >= 4 * delay
    assert sequential_time - parallel_time > 2 * delay
    print(f"\nparallel {parallel_time:.2f}s vs sequential {sequential_time:.2f}s "
          f"({sequential_time / parallel_time:.1f}x speedup)")


async def test_max_parallel_stages_is_respected(db_session, scripted, monkeypatch):
    monkeypatch.setattr(settings, "MAX_PARALLEL_STAGES", 2)
    [openai] = scripted(openai=dict(delay=0.1)).values()
    peak = 0

    original = openai.generate

    async def tracking_generate(*args, **kwargs):
        nonlocal peak
        task = asyncio.ensure_future(original(*args, **kwargs))
        await asyncio.sleep(0)
        peak = max(peak, openai.in_flight)
        return await task
    openai.generate = tracking_generate

    workflow = await make_workflow(db_session, *[(f"S{i}", 0) for i in range(5)])
    await ExecutionEngine(db_session).execute_workflow(workflow.id, **run_options())
    assert peak == 2


async def test_diamond_merge_receives_both_branch_outputs(db_session, scripted):
    [openai] = scripted(openai=dict(delay=0.05)).values()
    workflow = await make_workflow(db_session, ("Start", 0), ("Left", 1), ("Right", 1), ("Merge", 2))

    execution_id = await ExecutionEngine(db_session).execute_workflow(workflow.id, **run_options())
    await db_session.commit()

    merge_prompt = next(p for p in openai.prompts if "[Current Task: Merge]" in p)
    assert "output of Left" in merge_prompt and "output of Right" in merge_prompt
    assert "output of Start" not in merge_prompt  # only direct dependencies feed a stage
    records = await records_by_stage(db_session, execution_id)
    assert records["Merge"].started_at >= max(records["Left"].completed_at, records["Right"].completed_at)


async def test_explicit_dependencies_drive_scheduling(db_session, scripted):
    scripted(openai=dict(delay=0.05))
    workflow = await make_workflow(db_session, ("A", 0), ("Slow chain", 1), ("Needs A only", 2))
    stages = await stage_map(db_session, workflow)
    db_session.add(StageDependency(stage_id=stages["Needs A only"].id, depends_on_stage_id=stages["A"].id))
    await db_session.commit()
    workflow_id = workflow.id
    db_session.expire_all()  # drop cached stages so the engine sees the new dependency

    execution_id = await ExecutionEngine(db_session).execute_workflow(workflow_id, **run_options())
    live = tracker.get(execution_id)
    levels = {s["name"]: s["level"] for s in live.snapshot()["stages"]}
    assert levels == {"A": 0, "Slow chain": 1, "Needs A only": 1}


async def test_failure_skips_descendants_but_independent_branch_finishes(db_session, scripted):
    """Branch X fails -> its child is skipped; branch Y and its child still complete."""
    scripted(openai=dict(fail_models={"bad-model": HTTPError(400)}))
    workflow = await make_workflow(db_session, ("Root", 0), ("X", 1), ("Y", 1))
    stages = await stage_map(db_session, workflow)
    stages["X"].model_preference = "bad-model"
    x_child = Stage(workflow_id=workflow.id, name="X child", instruction="Do X child", stage_order=2)
    y_child = Stage(workflow_id=workflow.id, name="Y child", instruction="Do Y child", stage_order=2)
    db_session.add_all([x_child, y_child])
    await db_session.flush()
    db_session.add_all([
        StageDependency(stage_id=x_child.id, depends_on_stage_id=stages["X"].id),
        StageDependency(stage_id=y_child.id, depends_on_stage_id=stages["Y"].id),
    ])
    await db_session.commit()
    workflow_id = workflow.id
    db_session.expire_all()

    execution_id = await ExecutionEngine(db_session).execute_workflow(workflow_id, **run_options())
    await db_session.commit()

    records = await records_by_stage(db_session, execution_id)
    assert records["X"].status == "failed"
    assert "X child" not in records  # never ran
    assert records["Y"].status == "completed" and records["Y child"].status == "completed"
    statuses = {s["name"]: s["status"] for s in tracker.get(execution_id).snapshot()["stages"]}
    assert statuses["X child"] == "skipped"
    assert tracker.get(execution_id).status == "failed"
    await db_session.refresh(workflow)
    assert workflow.status == "failed"


async def test_sequential_mode_stops_chain_on_failure(db_session, scripted):
    scripted(openai=dict(fail_models={"openai-default": HTTPError(500)}))
    workflow = await make_workflow(db_session, ("A", 0), ("B", 1))
    execution_id = await ExecutionEngine(db_session).execute_workflow(workflow.id, **run_options(parallel=False))
    await db_session.commit()

    records = await records_by_stage(db_session, execution_id)
    assert list(records) == ["A"]
    assert records["A"].status == "failed"
    assert len(records["A"].metadata_["attempts"]) == settings.MAX_RETRIES


# ============================================================================
# Error handling in execution
# ============================================================================

async def test_transient_failures_are_retried_within_a_stage(db_session, scripted):
    [openai] = scripted(openai={}).values()
    errors = [HTTPError(503), HTTPError(503)]
    original = openai.generate

    async def flaky(*args, **kwargs):
        if errors:
            raise errors.pop(0)
        return await original(*args, **kwargs)
    openai.generate = flaky

    workflow = await make_workflow(db_session, ("A", 0))
    execution_id = await ExecutionEngine(db_session).execute_workflow(workflow.id, **run_options())
    await db_session.commit()

    record = (await records_by_stage(db_session, execution_id))["A"]
    assert record.status == "completed"
    assert [a["error_type"] for a in record.metadata_["attempts"]] == ["transient", "transient"]


async def test_model_fallback_after_primary_fails(db_session, seeded_routing_rules, scripted):
    """Routed model keeps failing -> the rule's fallback model answers the stage."""
    db = seeded_routing_rules
    scripted(anthropic=dict(fail_models={"claude-sonnet-4-20250514": HTTPError(500)}), openai={})
    workflow = await make_workflow(db, ("Code", 0))
    stage = (await stage_map(db, workflow))["Code"]
    stage.stage_type = "generation"  # quality rule -> Claude Sonnet; fallback gpt-4o-mini
    await db.commit()

    execution_id = await ExecutionEngine(db).execute_workflow(
        workflow.id, default_provider="openai", use_cache=False
    )
    await db.commit()

    record = (await records_by_stage(db, execution_id))["Code"]
    assert record.status == "completed"
    assert record.model_used == "gpt-4o-mini"
    assert record.metadata_["routing"]["fallback_from"] == "anthropic/claude-sonnet-4-20250514"
    assert len(record.metadata_["attempts"]) == settings.MAX_RETRIES

    decisions = (await db.execute(
        select(RoutingDecision).where(RoutingDecision.execution_id == execution_id).order_by(RoutingDecision.created_at)
    )).scalars().all()
    assert [d.selected_model_name for d in decisions] == ["claude-sonnet-4-20250514", "gpt-4o-mini"]
    assert decisions[1].was_fallback and "Fallback after failure" in decisions[1].selection_reason


async def test_open_circuit_routes_around_unhealthy_provider(db_session, seeded_routing_rules, scripted):
    db = seeded_routing_rules
    [anthropic, openai] = scripted(anthropic={}, openai={}).values()
    for _ in range(settings.CIRCUIT_BREAKER_THRESHOLD):
        circuit_breaker.record_failure("anthropic")

    workflow = await make_workflow(db, ("Code", 0))
    (await stage_map(db, workflow))["Code"].stage_type = "generation"
    await db.commit()
    execution_id = await ExecutionEngine(db).execute_workflow(workflow.id, use_cache=False)
    await db.commit()

    assert anthropic.calls == []  # never tried while its circuit is open
    assert (await records_by_stage(db, execution_id))["Code"].model_used == "gpt-4o"


async def test_stage_fails_when_fallback_also_fails(db_session, seeded_routing_rules, scripted):
    db = seeded_routing_rules
    scripted(openai=dict(fail_models={"gpt-4o": HTTPError(401), "gpt-4o-mini": HTTPError(401)}))
    workflow = await make_workflow(db, ("Code", 0))
    (await stage_map(db, workflow))["Code"].stage_type = "generation"
    await db.commit()

    execution_id = await ExecutionEngine(db).execute_workflow(workflow.id, use_cache=False)
    await db.commit()

    record = (await records_by_stage(db, execution_id))["Code"]
    assert record.status == "failed"
    assert "fallback also failed" in record.error_message
    assert len(record.metadata_["attempts"]) == 2  # permanent errors: one attempt per model


# ============================================================================
# Pause / resume / cancel
# ============================================================================

async def test_pause_holds_new_stages_and_resume_continues(db_session, scripted):
    gate = asyncio.Event()
    [openai] = scripted(openai=dict(gate=gate)).values()
    workflow = await make_workflow(db_session, ("First", 0), ("Second", 1))
    execution_id = uuid.uuid4()

    task = asyncio.create_task(ExecutionEngine(db_session).execute_workflow(
        workflow.id, execution_id=execution_id, **run_options()))
    await wait_until(lambda: openai.in_flight == 1)

    await tracker.pause(execution_id)
    gate.set()  # First finishes while paused
    live = tracker.get(execution_id)
    await wait_until(lambda: {s["name"]: s["status"] for s in live.snapshot()["stages"]}["First"] == "completed")
    await asyncio.sleep(0.1)
    assert len(openai.calls) == 1  # Second not started
    assert live.status == "paused" and workflow.status == "paused"

    await tracker.resume(execution_id)
    await asyncio.wait_for(task, 5)
    assert len(openai.calls) == 2
    assert live.status == "completed" and live.progress == 1.0


async def test_cancel_stops_in_flight_calls_and_skips_the_rest(db_session, scripted):
    [openai] = scripted(openai=dict(gate=asyncio.Event())).values()  # calls block until cancelled
    workflow = await make_workflow(db_session, ("P1", 0), ("P2", 0), ("After", 1))
    execution_id = uuid.uuid4()

    task = asyncio.create_task(ExecutionEngine(db_session).execute_workflow(
        workflow.id, execution_id=execution_id, **run_options()))
    await wait_until(lambda: openai.in_flight == 2)

    await tracker.cancel(execution_id)
    await asyncio.wait_for(task, 5)
    await db_session.commit()

    records = await records_by_stage(db_session, execution_id)
    assert {records["P1"].status, records["P2"].status} == {"cancelled"}
    assert "After" not in records
    statuses = {s["name"]: s["status"] for s in tracker.get(execution_id).snapshot()["stages"]}
    assert statuses == {"P1": "cancelled", "P2": "cancelled", "After": "skipped"}
    await db_session.refresh(workflow)
    assert workflow.status == "cancelled"


async def test_control_of_unknown_or_finished_execution(db_session, scripted):
    scripted(openai={})
    workflow = await make_workflow(db_session, ("A", 0))
    execution_id = await ExecutionEngine(db_session).execute_workflow(workflow.id, **run_options())
    with pytest.raises(RuntimeError, match="already completed"):
        await tracker.pause(execution_id)
    with pytest.raises(KeyError):
        await tracker.cancel(uuid.uuid4())


# ============================================================================
# API: background execution, status, control, DAG
# ============================================================================

@pytest.fixture
def background_sessions(engine):
    """Background executions open their own sessions on the test database."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app.dependency_overrides[get_session_factory] = lambda: factory
    yield factory
    app.dependency_overrides.pop(get_session_factory, None)


async def test_background_execution_via_api(client, db_session, scripted, background_sessions):
    scripted(openai=dict(delay=0.1))
    workflow = await make_workflow(db_session, ("Start", 0), ("B1", 1), ("B2", 1), ("End", 2))

    response = await client.post(f"/api/workflows/{workflow.id}/execute",
                                 json={"background": True, "use_cache": False, "use_routing": False})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "running"
    execution_id = uuid.UUID(body["execution_id"])

    # A second start while running is refused
    again = await client.post(f"/api/workflows/{workflow.id}/execute", json={"background": True})
    assert again.status_code == 409

    await asyncio.wait_for(tracker.get(execution_id).task, 10)

    status = (await client.get(f"/api/executions/{execution_id}/status")).json()
    assert status["status"] == "completed" and status["progress"] == 1.0
    assert [s["level"] for s in status["stages"]] == [0, 1, 1, 2]

    details = (await client.get(f"/api/executions/{execution_id}")).json()
    assert details["summary"]["completed_stages"] == 4
    async with background_sessions() as fresh:
        assert (await fresh.get(Workflow, workflow.id)).status == "completed"


async def test_control_endpoints(client, db_session, scripted, background_sessions):
    gate = asyncio.Event()
    [openai] = scripted(openai=dict(gate=gate)).values()
    workflow = await make_workflow(db_session, ("A", 0), ("B", 1))

    execution_id = (await client.post(f"/api/workflows/{workflow.id}/execute",
                                      json={"background": True, "use_cache": False, "use_routing": False})).json()["execution_id"]
    await wait_until(lambda: openai.in_flight == 1)

    paused = await client.post(f"/api/executions/{execution_id}/pause")
    assert paused.status_code == 200 and paused.json()["status"] == "paused"
    assert (await client.post(f"/api/executions/{execution_id}/resume")).json()["status"] == "running"
    assert (await client.post(f"/api/executions/{execution_id}/cancel")).status_code == 200

    await asyncio.wait_for(tracker.get(uuid.UUID(execution_id)).task, 10)
    assert (await client.get(f"/api/executions/{execution_id}/status")).json()["status"] == "cancelled"
    assert (await client.post(f"/api/executions/{execution_id}/resume")).status_code == 409
    assert (await client.post(f"/api/executions/{uuid.uuid4()}/pause")).status_code == 404
    assert (await client.get(f"/api/executions/{uuid.uuid4()}/status")).status_code == 404


async def test_sync_execute_reports_final_status(client, db_session, scripted):
    scripted(openai=dict(fail_models={"openai-default": HTTPError(400)}))
    workflow = await make_workflow(db_session, ("A", 0))
    response = await client.post(f"/api/workflows/{workflow.id}/execute",
                                 json={"use_cache": False, "use_routing": False})
    assert response.status_code == 200
    assert response.json()["status"] == "failed"


async def test_dag_endpoint_and_cycle_rejection(client, db_session, scripted):
    workflow = await make_workflow(db_session, ("Start", 0), ("B1", 1), ("B2", 1), ("End", 2))
    workflow_id = workflow.id
    dag = (await client.get(f"/api/workflows/{workflow_id}/dag")).json()
    assert [len(level) for level in dag["levels"]] == [1, 2, 1]
    assert dag["max_width"] == 2 and dag["parallelism_factor"] == 1.33
    assert "Critical Path" in dag["ascii"]

    stages = await stage_map(db_session, workflow)
    db_session.add_all([
        StageDependency(stage_id=stages["B1"].id, depends_on_stage_id=stages["End"].id),
    ])
    await db_session.commit()
    db_session.expire_all()
    assert (await client.get(f"/api/workflows/{workflow_id}/dag")).status_code == 422
    response = await client.post(f"/api/workflows/{workflow_id}/execute", json={})
    assert response.status_code == 422 and "Cycle" in response.json()["detail"]


async def test_live_execution_lookup_by_workflow(client, db_session, scripted, background_sessions):
    gate = asyncio.Event()
    [openai] = scripted(openai=dict(gate=gate)).values()
    workflow = await make_workflow(db_session, ("A", 0))
    workflow_id = workflow.id
    assert (await client.get(f"/api/workflows/{workflow_id}/executions/live")).status_code == 404

    execution_id = (await client.post(f"/api/workflows/{workflow_id}/execute",
                                      json={"background": True, "use_cache": False, "use_routing": False})).json()["execution_id"]
    await wait_until(lambda: openai.in_flight == 1)
    live = (await client.get(f"/api/workflows/{workflow_id}/executions/live")).json()
    assert live["execution_id"] == execution_id and live["status"] == "running"

    gate.set()
    await asyncio.wait_for(tracker.get(uuid.UUID(execution_id)).task, 10)
    assert (await client.get(f"/api/workflows/{workflow_id}/executions/live")).status_code == 404
