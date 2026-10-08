"""
Analytics tests: aggregator math on a hand-built dataset, the API endpoints, export,
and an end-to-end check against a real (stubbed-LLM) parallel execution.
"""
import csv
import io
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.models import ExecutionRecord, RoutingDecision, Stage, Workflow
from backend.app.services.analytics.aggregator import AnalyticsAggregator, AnalyticsFilter
from backend.app.services.execution import ExecutionEngine

pytestmark = pytest.mark.integration

NOW = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
YESTERDAY = NOW - timedelta(days=1)
LAST_MONTH = NOW - timedelta(days=40)


def record(workflow, stage, execution_id, *, status="completed", provider="openai", model="gpt-4o-mini",
           latency=500, cost="0.001", tokens=(100, 50), cache_hit=False, created=NOW, started_offset=0,
           metadata=None) -> ExecutionRecord:
    started = created + timedelta(milliseconds=started_offset)
    return ExecutionRecord(
        workflow_id=workflow.id, stage_id=stage.id, execution_id=execution_id,
        status=status, cache_hit=cache_hit,
        provider=None if status == "failed" else ("cache" if cache_hit else provider),
        model_used=None if status == "failed" else model,
        input_tokens=None if status == "failed" else (0 if cache_hit else tokens[0]),
        output_tokens=None if status == "failed" else (0 if cache_hit else tokens[1]),
        latency_ms=None if status == "failed" else (0 if cache_hit else latency),
        estimated_cost=None if status == "failed" else Decimal("0" if cache_hit else cost),
        started_at=started, completed_at=started + timedelta(milliseconds=latency or 0),
        created_at=created, metadata_=metadata or {},
    )


@pytest.fixture
async def dataset(db_session):
    """
    Two workflows, four executions:
      exec A (wf1, today):     analysis ok (openai, 400ms, $0.001), generation ok (anthropic, 1200ms, $0.010)
      exec B (wf1, today):     analysis cache hit (saved 150 tokens / $0.001), generation FAILED
      exec C (wf1, yesterday): analysis ok (openai, 600ms, $0.002)
      exec D (wf2, 40d ago):   custom-less stage ok (groq, 200ms, $0.0005)
    """
    wf1 = Workflow(name="Analytics WF1")
    wf2 = Workflow(name="Analytics WF2")
    db_session.add_all([wf1, wf2])
    await db_session.flush()
    analysis = Stage(workflow_id=wf1.id, name="Analyze", instruction="a", stage_order=0, stage_type="analysis")
    generation = Stage(workflow_id=wf1.id, name="Generate", instruction="g", stage_order=1, stage_type="generation")
    untyped = Stage(workflow_id=wf2.id, name="Misc", instruction="m", stage_order=0, stage_type=None)
    db_session.add_all([analysis, generation, untyped])
    await db_session.flush()

    a, b, c, d = (uuid.uuid4() for _ in range(4))
    db_session.add_all([
        record(wf1, analysis, a, latency=400, cost="0.001"),
        record(wf1, generation, a, provider="anthropic", model="claude-sonnet-4-20250514", latency=1200,
               cost="0.010", tokens=(300, 200), started_offset=400),
        record(wf1, analysis, b, cache_hit=True, model="gpt-4o-mini",
               metadata={"tokens_saved": 150, "cost_saved": 0.001, "similarity_score": 0.99}),
        record(wf1, generation, b, status="failed"),
        record(wf1, analysis, c, latency=600, cost="0.002", created=YESTERDAY),
        record(wf2, untyped, d, provider="groq", model="llama-3.3-70b-versatile", latency=200, cost="0.0005",
               created=LAST_MONTH),
    ])
    db_session.add_all([
        RoutingDecision(execution_id=a, stage_id=analysis.id, stage_type="analysis", selected_provider="openai",
                        selected_model_name="gpt-4o-mini", priority_factor="balanced", created_at=NOW),
        RoutingDecision(execution_id=a, stage_id=generation.id, stage_type="generation", selected_provider="anthropic",
                        selected_model_name="claude-sonnet-4-20250514", priority_factor="quality", created_at=NOW),
        RoutingDecision(execution_id=c, stage_id=analysis.id, stage_type="analysis", selected_provider="openai",
                        selected_model_name="gpt-4o-mini", was_user_override=True, created_at=YESTERDAY),
        RoutingDecision(execution_id=b, stage_id=generation.id, stage_type="generation", selected_provider="openai",
                        selected_model_name="gpt-4o-mini", was_fallback=True, priority_factor="quality", created_at=NOW),
    ])
    await db_session.commit()
    return {"wf1": wf1, "wf2": wf2, "a": a, "b": b, "c": c, "d": d}


# ============================================================================
# Aggregator
# ============================================================================

async def test_overview_metrics(db_session, dataset):
    m = await AnalyticsAggregator(db_session).get_workflow_metrics()
    assert m["total_executions"] == 4
    assert m["successful_executions"] == 3          # B had a failed stage
    assert m["execution_success_rate"] == 75.0
    assert m["total_stages"] == 6
    assert (m["completed_stages"], m["failed_stages"]) == (5, 1)
    assert m["success_rate"] == pytest.approx(83.33)
    assert (m["llm_calls"], m["cache_hits"]) == (4, 1)
    assert m["total_tokens"] == 150 + 500 + 150 + 150
    assert m["total_cost"] == pytest.approx(0.0135)
    assert m["avg_latency_ms"] == pytest.approx((400 + 1200 + 600 + 200) / 4)  # LLM calls only
    assert m["avg_execution_duration_ms"] > 0


async def test_filters_by_date_and_workflow(db_session, dataset):
    agg = AnalyticsAggregator(db_session)
    recent = await agg.get_workflow_metrics(AnalyticsFilter(start_date=NOW - timedelta(days=7)))
    assert recent["total_executions"] == 3  # D is 40 days old

    today = await agg.get_workflow_metrics(AnalyticsFilter(start_date=NOW - timedelta(hours=1)))
    assert today["total_executions"] == 2

    wf2 = await agg.get_workflow_metrics(AnalyticsFilter(workflow_id=dataset["wf2"].id))
    assert (wf2["total_executions"], wf2["total_cost"]) == (1, pytest.approx(0.0005))

    empty = await agg.get_workflow_metrics(AnalyticsFilter(workflow_id=uuid.uuid4()))
    assert empty["total_executions"] == 0 and empty["success_rate"] == 0.0


async def test_stage_type_metrics(db_session, dataset):
    rows = {r["stage_type"]: r for r in await AnalyticsAggregator(db_session).get_stage_type_metrics()}
    assert set(rows) == {"analysis", "generation", "untyped"}
    assert rows["analysis"]["runs"] == 3 and rows["analysis"]["cache_hits"] == 1
    assert rows["analysis"]["cache_hit_rate"] == pytest.approx(33.33)
    assert rows["analysis"]["avg_latency_ms"] == 500.0  # (400 + 600) / 2, cache hit excluded
    assert (rows["generation"]["completed"], rows["generation"]["failed"]) == (1, 1)


async def test_model_utilization_excludes_cache_hits(db_session, dataset):
    models = await AnalyticsAggregator(db_session).get_model_utilization()
    assert [m["model"] for m in models][0] == "gpt-4o-mini"
    by_model = {m["model"]: m for m in models}
    assert by_model["gpt-4o-mini"]["usage_count"] == 2  # the cache hit isn't a model call
    assert by_model["gpt-4o-mini"]["share"] == 50.0
    assert by_model["claude-sonnet-4-20250514"]["total_cost"] == pytest.approx(0.010)
    assert all(m["provider"] != "cache" for m in models)


async def test_cache_metrics(db_session, dataset):
    cache = await AnalyticsAggregator(db_session).get_cache_metrics()
    assert (cache["total_hits"], cache["total_misses"]) == (1, 4)
    assert cache["hit_rate"] == 20.0
    assert cache["total_tokens_saved"] == 150
    assert cache["total_cost_saved"] == pytest.approx(0.001)


async def test_latency_percentiles(db_session, dataset):
    lat = await AnalyticsAggregator(db_session).get_latency_metrics()
    assert lat["sample_count"] == 4
    assert (lat["min_ms"], lat["max_ms"]) == (200, 1200)
    # percentile_cont over [200, 400, 600, 1200]
    assert lat["p50"] == 500.0
    assert lat["p75"] == 750.0
    assert lat["p99"] == pytest.approx(1182.0)


async def test_daily_trends_fill_idle_days(db_session, dataset):
    agg = AnalyticsAggregator(db_session)
    costs = await agg.get_cost_trend(days=7)
    assert len(costs) == 7
    assert costs[-1]["date"] == NOW.date().isoformat()
    assert costs[-1]["cost"] == pytest.approx(0.011) and costs[-1]["executions"] == 2
    assert costs[-2]["cost"] == pytest.approx(0.002)
    assert all(p["cost"] == 0 for p in costs[:-2])  # idle days present as zeros

    tokens = await agg.get_token_usage_trend(days=2)
    assert tokens[-1] == {"date": NOW.date().isoformat(), "input_tokens": 400, "output_tokens": 250, "total_tokens": 650}

    wf2 = await agg.get_cost_trend(AnalyticsFilter(workflow_id=dataset["wf2"].id, start_date=LAST_MONTH))
    assert sum(p["cost"] for p in wf2) == pytest.approx(0.0005)


async def test_routing_effectiveness(db_session, dataset):
    agg = AnalyticsAggregator(db_session)
    r = await agg.get_routing_effectiveness()
    assert r["total_decisions"] == 4
    assert (r["override_count"], r["override_rate"]) == (1, 25.0)
    assert (r["fallback_count"], r["fallback_rate"]) == (1, 25.0)
    assert r["priority_distribution"] == {"quality": 2, "balanced": 1}
    assert r["top_models"][0] == {"model": "gpt-4o-mini", "decisions": 3}

    wf2 = await agg.get_routing_effectiveness(AnalyticsFilter(workflow_id=dataset["wf2"].id))
    assert wf2["total_decisions"] == 0


async def test_execution_timeline(db_session, dataset):
    t = await AnalyticsAggregator(db_session).get_execution_timeline(dataset["a"])
    assert [s["stage_name"] for s in t["stages"]] == ["Analyze", "Generate"]
    assert [(s["start_offset_ms"], s["end_offset_ms"]) for s in t["stages"]] == [(0, 400), (400, 1600)]
    assert t["total_duration_ms"] == 1600
    assert t["parallelism"] == 1.0  # sequential: stages don't overlap
    assert await AnalyticsAggregator(db_session).get_execution_timeline(uuid.uuid4()) is None


# ============================================================================
# API
# ============================================================================

async def test_analytics_endpoints(client, dataset):
    overview = (await client.get("/api/analytics/overview")).json()
    assert overview["total_executions"] == 4

    since = (NOW - timedelta(days=7)).isoformat()
    assert (await client.get("/api/analytics/overview", params={"start_date": since})).json()["total_executions"] == 3
    wf = dataset["wf1"].id
    assert (await client.get(f"/api/analytics/workflows/{wf}")).json()["total_executions"] == 3

    assert (await client.get("/api/analytics/cache")).json()["hit_rate"] == 20.0
    assert len((await client.get("/api/analytics/models")).json()) == 3
    assert (await client.get("/api/analytics/latency")).json()["p50"] == 500.0
    assert len((await client.get("/api/analytics/costs", params={"days": 14})).json()) == 14
    assert len((await client.get("/api/analytics/tokens")).json()) == 30
    assert (await client.get("/api/analytics/routing")).json()["total_decisions"] == 4
    assert len((await client.get("/api/analytics/stage-types")).json()) == 3

    timeline = await client.get(f"/api/analytics/timeline/{dataset['a']}")
    assert timeline.status_code == 200 and len(timeline.json()["stages"]) == 2
    assert (await client.get(f"/api/analytics/timeline/{uuid.uuid4()}")).status_code == 404


async def test_analytics_validation(client):
    bad_range = await client.get("/api/analytics/overview",
                                 params={"start_date": NOW.isoformat(), "end_date": YESTERDAY.isoformat()})
    assert bad_range.status_code == 422
    assert (await client.get("/api/analytics/costs", params={"days": 0})).status_code == 422
    # Empty database: zeros, not errors
    empty = (await client.get("/api/analytics/overview")).json()
    assert empty["total_executions"] == 0
    assert (await client.get("/api/analytics/latency")).json()["sample_count"] == 0


async def test_export_json_and_csv(client, dataset):
    response = await client.get("/api/analytics/export", params={"format": "json"})
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    data = json.loads(response.text)
    assert data["overview"]["total_executions"] == 4
    assert {"cache", "latency", "routing", "models", "stage_types", "cost_trend", "token_trend"} <= set(data)

    text = (await client.get("/api/analytics/export", params={"format": "csv"})).text
    assert "# overview" in text and "# models" in text and "gpt-4o-mini" in text
    assert response.headers["content-type"].startswith("application/json")

    runs = (await client.get("/api/analytics/export", params={"format": "csv", "dataset": "stage_runs"})).text
    rows = list(csv.DictReader(io.StringIO(runs)))
    assert len(rows) == 6
    assert {r["status"] for r in rows} == {"completed", "failed"}

    wf2_runs = json.loads((await client.get("/api/analytics/export", params={
        "format": "json", "dataset": "stage_runs", "workflow_id": str(dataset["wf2"].id)})).text)
    assert len(wf2_runs["stage_runs"]) == 1


# ============================================================================
# End to end: analytics of a real parallel execution
# ============================================================================

async def test_analytics_of_real_parallel_execution(db_session, providers, mock_embeddings):
    """Two parallel stages overlap in time, so the timeline reports parallelism > 1."""
    from backend.tests.integration.test_phase5_integration import ScriptedProvider, make_workflow
    from backend.app.services.llm import registry
    providers()
    registry.register(ScriptedProvider("openai", delay=0.2))
    workflow = await make_workflow(db_session, ("P1", 0), ("P2", 0))

    execution_id = await ExecutionEngine(db_session).execute_workflow(
        workflow.id, default_provider="openai", use_cache=False, use_routing=False)
    await db_session.commit()

    agg = AnalyticsAggregator(db_session)
    timeline = await agg.get_execution_timeline(execution_id)
    assert timeline["parallelism"] > 1.5
    overview = await agg.get_workflow_metrics(AnalyticsFilter(workflow_id=workflow.id))
    assert (overview["total_executions"], overview["llm_calls"]) == (1, 2)
