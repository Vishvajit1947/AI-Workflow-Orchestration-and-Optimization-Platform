"""
Cache Integration Tests.

Covers the semantic cache inside the execution engine and the /api/cache endpoints.
Uses the conftest `fake_provider` (registered LLM provider, no API keys needed) and
`mock_embeddings` (deterministic text-hash embeddings: identical inputs give identical
vectors, different inputs give near-orthogonal ones).
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.cache import CacheEntry
from backend.app.models.execution import ExecutionRecord
from backend.app.models.workflow import Workflow
from backend.app.services.execution import ExecutionEngine

# ---------------------------------------------------------------------------
# Helpers (fake_provider / mock_embeddings fixtures live in conftest.py)
# ---------------------------------------------------------------------------

async def _records(db: AsyncSession, execution_id: uuid.UUID) -> list[ExecutionRecord]:
    result = await db.execute(
        select(ExecutionRecord)
        .where(ExecutionRecord.execution_id == execution_id)
        .order_by(ExecutionRecord.created_at)
    )
    return list(result.scalars().all())


async def _run(db: AsyncSession, workflow: Workflow, **kwargs) -> uuid.UUID:
    engine = ExecutionEngine(db)
    execution_id = await engine.execute_workflow(workflow.id, default_provider="fake", **kwargs)
    await db.commit()
    return execution_id


# ---------------------------------------------------------------------------
# Execution engine integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execution_uses_cache_on_second_run(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow,
    fake_provider, mock_embeddings,
):
    """First run calls the LLM for every stage and fills the cache; second run is fully cached."""
    exec1 = await _run(db_session, sample_workflow_with_stages)
    assert fake_provider.calls == 3

    records1 = await _records(db_session, exec1)
    assert [r.cache_hit for r in records1] == [False, False, False]
    assert all(r.provider == "fake" for r in records1)

    entries = (await db_session.execute(select(CacheEntry))).scalars().all()
    assert len(entries) == 3
    assert all(e.dependency_hash and e.expires_at for e in entries)

    fake_provider.calls = 0
    exec2 = await _run(db_session, sample_workflow_with_stages)
    assert fake_provider.calls == 0
    assert exec1 != exec2

    records2 = await _records(db_session, exec2)
    assert len(records2) == 3
    for r1, r2 in zip(records1, records2):
        assert r2.cache_hit is True
        assert r2.provider == "cache"
        assert r2.status == "completed"
        assert r2.result == r1.result
        assert r2.latency_ms == 0 and float(r2.estimated_cost) == 0
        assert r2.input_tokens == 0 and r2.output_tokens == 0
        assert r2.metadata_["similarity_score"] >= 0.99
        assert r2.metadata_["tokens_saved"] == 150

    await db_session.refresh(sample_workflow_with_stages)
    assert sample_workflow_with_stages.status == "completed"


@pytest.mark.asyncio
async def test_use_cache_false_forces_llm_calls(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow,
    fake_provider, mock_embeddings,
):
    await _run(db_session, sample_workflow_with_stages)
    fake_provider.calls = 0

    exec2 = await _run(db_session, sample_workflow_with_stages, use_cache=False)
    assert fake_provider.calls == 3
    assert not any(r.cache_hit for r in await _records(db_session, exec2))


@pytest.mark.asyncio
async def test_upstream_change_causes_downstream_misses(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow,
    fake_provider, mock_embeddings,
):
    """When stage 1 is re-run and produces new output, stages 2 and 3 can't reuse their cache."""
    await _run(db_session, sample_workflow_with_stages)

    stage1 = min(sample_workflow_with_stages.stages, key=lambda s: s.stage_order)
    engine = ExecutionEngine(db_session)
    await engine.cache_service.invalidate(stage_id=stage1.id)
    await db_session.commit()

    fake_provider.calls = 0
    fake_provider.version = 2  # stage 1 now produces different output
    exec2 = await _run(db_session, sample_workflow_with_stages)

    assert fake_provider.calls == 3
    assert [r.cache_hit for r in await _records(db_session, exec2)] == [False, False, False]


@pytest.mark.asyncio
async def test_cache_failure_does_not_fail_execution(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow,
    fake_provider, mock_embeddings,
):
    """If embeddings are unavailable, stages still run via the LLM."""
    mock_embeddings.generate_embedding.side_effect = RuntimeError("embedding API down")

    exec1 = await _run(db_session, sample_workflow_with_stages)

    records = await _records(db_session, exec1)
    assert fake_provider.calls == 3
    assert all(r.status == "completed" and not r.cache_hit for r in records)
    assert (await db_session.execute(select(CacheEntry))).scalars().all() == []


# ---------------------------------------------------------------------------
# /api/cache endpoints
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def cached_workflow(db_session, sample_workflow_with_stages, fake_provider, mock_embeddings):
    """Workflow executed twice: 3 cache entries, 3 hits."""
    await _run(db_session, sample_workflow_with_stages)
    await _run(db_session, sample_workflow_with_stages)
    return sample_workflow_with_stages


@pytest.mark.asyncio
async def test_list_entries(client, cached_workflow):
    resp = await client.get("/api/cache/entries", params={"workflow_id": str(cached_workflow.id)})
    assert resp.status_code == 200, resp.text
    entries = resp.json()
    assert len(entries) == 3
    assert all(e["hit_count"] == 1 and e["is_valid"] for e in entries)
    assert all(e["workflow_id"] == str(cached_workflow.id) for e in entries)

    resp = await client.get("/api/cache/entries", params={"stage_type": "design"})
    assert len(resp.json()) == 1

    resp = await client.get("/api/cache/entries", params={"limit": 2})
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_stats(client, cached_workflow):
    resp = await client.get("/api/cache/stats")
    assert resp.status_code == 200, resp.text
    stats = resp.json()
    assert stats["total_entries"] == 3
    assert stats["total_hits"] == 3
    assert stats["hit_rate"] == pytest.approx(0.5)
    assert stats["total_tokens_saved"] == 450
    assert float(stats["total_cost_saved"]) == pytest.approx(0.00045)
    assert stats["avg_similarity_score"] >= 0.99


@pytest.mark.asyncio
async def test_stats_empty(client):
    resp = await client.get("/api/cache/stats")
    assert resp.status_code == 200, resp.text
    stats = resp.json()
    assert stats["total_entries"] == 0
    assert stats["hit_rate"] == 0.0
    assert stats["avg_similarity_score"] == 0.0


@pytest.mark.asyncio
async def test_hit_rate(client, cached_workflow):
    resp = await client.get(f"/api/cache/hit-rate/{cached_workflow.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_cache_entries"] == 3
    assert body["total_cache_hits"] == 3
    assert body["hit_rate_percentage"] == "50.00%"


@pytest.mark.asyncio
async def test_clear_and_miss_afterwards(client, cached_workflow, fake_provider):
    resp = await client.post("/api/cache/clear", params={"stage_type": "analysis"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["entries_invalidated"] == 1

    resp = await client.post("/api/cache/clear", params={"workflow_id": str(cached_workflow.id)})
    assert resp.json()["entries_invalidated"] == 2

    resp = await client.get("/api/cache/entries", params={"is_valid": True})
    assert resp.json() == []

    fake_provider.calls = 0
    resp = await client.post(
        f"/api/workflows/{cached_workflow.id}/execute", json={"default_provider": "fake"}
    )
    assert resp.status_code == 200, resp.text
    assert fake_provider.calls == 3


@pytest.mark.asyncio
async def test_delete_entry(client, cached_workflow):
    entries = (await client.get("/api/cache/entries")).json()
    entry_id = entries[0]["id"]

    resp = await client.delete(f"/api/cache/entries/{entry_id}")
    assert resp.status_code == 200, resp.text
    assert len((await client.get("/api/cache/entries")).json()) == 2

    resp = await client.delete(f"/api/cache/entries/{entry_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cleanup_expired(client, db_session, cached_workflow):
    entry = (await db_session.execute(select(CacheEntry).limit(1))).scalar_one()
    entry.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    resp = await client.post("/api/cache/cleanup-expired")
    assert resp.status_code == 200, resp.text
    assert resp.json()["entries_cleaned"] == 1


@pytest.mark.asyncio
async def test_warm_cache(client, sample_workflow_with_stages, fake_provider, mock_embeddings):
    wf_id = str(sample_workflow_with_stages.id)

    resp = await client.post("/api/cache/warm", params={"workflow_id": wf_id},
                             json={"default_provider": "fake"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stages_cached_now"] == 3
    assert body["stages_already_cached"] == 0

    resp = await client.post("/api/cache/warm", params={"workflow_id": wf_id},
                             json={"default_provider": "fake"})
    body = resp.json()
    assert body["stages_cached_now"] == 0
    assert body["stages_already_cached"] == 3


@pytest.mark.asyncio
async def test_warm_unknown_workflow(client):
    resp = await client.post("/api/cache/warm", params={"workflow_id": str(uuid.uuid4())})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_refresh_cache(client, cached_workflow, fake_provider):
    fake_provider.calls = 0
    resp = await client.post(f"/api/cache/refresh/{cached_workflow.id}",
                             json={"default_provider": "fake"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["entries_invalidated"] == 3
    assert body["stages_cached_now"] == 3
    assert fake_provider.calls == 3

    valid = (await client.get("/api/cache/entries", params={"is_valid": True})).json()
    assert len(valid) == 3
    assert all(e["hit_count"] == 0 for e in valid)


@pytest.mark.asyncio
async def test_execution_details_report_cache_hit(client, sample_workflow_with_stages,
                                                  fake_provider, mock_embeddings):
    wf_id = sample_workflow_with_stages.id
    for _ in range(2):
        resp = await client.post(f"/api/workflows/{wf_id}/execute", json={"default_provider": "fake"})
        assert resp.status_code == 200, resp.text
    execution_id = resp.json()["execution_id"]

    resp = await client.get(f"/api/executions/{execution_id}")
    assert resp.status_code == 200, resp.text
    stages = resp.json()["stages"]
    assert len(stages) == 3
    assert all(s["cache_hit"] and s["provider"] == "cache" for s in stages)
    assert all(s["tokens_saved"] == 150 and s["cache_similarity"] >= 0.99 for s in stages)
    assert all(float(s["cost_saved"]) > 0 for s in stages)
