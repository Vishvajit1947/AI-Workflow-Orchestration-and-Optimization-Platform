"""
Phase 3 Integration Tests — Semantic Caching End-to-End.

Embeddings:
  * `semantic_embeddings` — REAL semantic vectors from the local sentence-transformers
    model (all-MiniLM-L6-v2), zero-padded 384 → 1536 dims to fit the vector(1536)
    column. Padding preserves cosine similarity exactly, so pgvector similarity equals
    the model's similarity.
  * OpenAI embedding tests run only when OPENAI_API_KEY is set.

LLM calls go through the conftest `fake_provider` (registered as "fake"), so no LLM
API keys are needed; the cache, context, validation and DB paths are all real.

Similarity values measured for the local model (used to pick thresholds):
  "Design a REST API for user authentication" vs
      "Create a RESTful API for authenticating users"   → 0.904
      "How to make pasta carbonara"                     → 0.042
  "Explain microservice architecture" vs
      "What is a microservices architecture?"           → 0.936
      "Explain REST API design"                         → 0.479
"""
import math
import time
import uuid

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models.cache import CacheEntry
from backend.app.models.execution import ExecutionRecord
from backend.app.models.stage import Stage
from backend.app.models.workflow import Workflow
from backend.app.services.cache.cache_validator import CacheValidator
from backend.app.services.cache.semantic_cache import SemanticCacheService
from backend.app.services.context_manager import ContextManager
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.execution import ExecutionEngine

pytestmark = pytest.mark.integration

requires_openai = pytest.mark.skipif(
    not settings.OPENAI_API_KEY, reason="OPENAI_API_KEY not set"
)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


async def _stages(db: AsyncSession, workflow: Workflow) -> list[Stage]:
    result = await db.execute(
        select(Stage).where(Stage.workflow_id == workflow.id).order_by(Stage.stage_order)
    )
    return list(result.scalars().all())


async def _records(db: AsyncSession, execution_id: uuid.UUID) -> list[ExecutionRecord]:
    result = await db.execute(
        select(ExecutionRecord)
        .where(ExecutionRecord.execution_id == execution_id)
        .order_by(ExecutionRecord.created_at)
    )
    return list(result.scalars().all())


async def _execute(db: AsyncSession, workflow_id: uuid.UUID, **kwargs) -> uuid.UUID:
    engine = ExecutionEngine(db)
    execution_id = await engine.execute_workflow(workflow_id, default_provider="fake", **kwargs)
    await db.commit()
    return execution_id


# ============================================================================
# Embedding Service
# ============================================================================

async def test_local_embedding_consistency(local_embedding_service):
    """Identical text produces identical embeddings."""
    text = "Test input for embedding consistency"
    emb1 = await local_embedding_service.generate_embedding(text)
    emb2 = await local_embedding_service.generate_embedding(text)

    assert len(emb1) == len(emb2) == local_embedding_service.get_dimension()
    assert cosine_similarity(emb1, emb2) == pytest.approx(1.0, abs=1e-6)


async def test_local_embedding_semantic_similarity(local_embedding_service):
    """Paraphrases score high, unrelated text scores low."""
    emb1 = await local_embedding_service.generate_embedding("Design a REST API for user authentication")
    emb2 = await local_embedding_service.generate_embedding("Create a RESTful API for authenticating users")
    emb3 = await local_embedding_service.generate_embedding("How to make pasta carbonara")

    sim_12 = cosine_similarity(emb1, emb2)
    sim_13 = cosine_similarity(emb1, emb3)

    assert sim_12 > 0.85   # measured 0.904
    assert sim_13 < 0.30   # measured 0.042
    assert sim_12 - sim_13 > 0.5


@requires_openai
@pytest.mark.requires_openai
async def test_openai_embedding_consistency():
    service = EmbeddingService(provider="openai")
    text = "Test input for embedding consistency"
    emb1 = await service.generate_embedding(text)
    emb2 = await service.generate_embedding(text)

    assert len(emb1) == len(emb2) == settings.EMBEDDING_DIMENSION
    assert cosine_similarity(emb1, emb2) > 0.999


@requires_openai
@pytest.mark.requires_openai
async def test_openai_embedding_semantic_similarity():
    service = EmbeddingService(provider="openai")
    emb1 = await service.generate_embedding("Design a REST API for user authentication")
    emb2 = await service.generate_embedding("Create a RESTful API for authenticating users")
    emb3 = await service.generate_embedding("How to make pasta carbonara")

    assert cosine_similarity(emb1, emb2) > cosine_similarity(emb1, emb3) + 0.3


# ============================================================================
# Semantic Cache (real embeddings through pgvector)
# ============================================================================

async def test_cache_stores_and_retrieves_exact_match(db_session: AsyncSession, semantic_embeddings):
    cache_service = SemanticCacheService(db_session)

    await cache_service.store(
        input_text="What are microservices?",
        result="Microservices are an architectural style...",
        stage_type="analysis",
        result_tokens=100,
        model_used="gpt-4o-mini",
    )
    await db_session.commit()

    result = await cache_service.lookup(input_text="What are microservices?", stage_type="analysis")

    assert result.cache_hit is True
    assert result.similarity_score >= 0.99
    assert "Microservices" in result.entry.result
    assert result.tokens_saved == 100


async def test_cache_semantic_similarity_match(db_session: AsyncSession, semantic_embeddings):
    """A paraphrased query hits an entry stored under different wording."""
    cache_service = SemanticCacheService(db_session)

    await cache_service.store(
        input_text="Explain microservice architecture",
        result="Microservice architecture involves decomposing...",
        stage_type="analysis",
    )
    await db_session.commit()

    result = await cache_service.lookup(
        input_text="What is a microservices architecture?",
        stage_type="analysis",
        similarity_threshold=0.85,
    )

    assert result.cache_hit is True
    assert 0.85 <= result.similarity_score < 0.99   # measured 0.936: similar, not identical


async def test_cache_picks_most_similar_entry(db_session: AsyncSession, semantic_embeddings):
    """With several candidates above threshold, the closest one wins."""
    cache_service = SemanticCacheService(db_session)
    await cache_service.store(input_text="Explain REST API design", result="REST answer", stage_type="analysis")
    await cache_service.store(input_text="Explain microservice architecture", result="Microservices answer",
                              stage_type="analysis")
    await db_session.commit()

    result = await cache_service.lookup(
        input_text="What is a microservices architecture?", stage_type="analysis",
        similarity_threshold=0.3,
    )
    assert result.cache_hit is True
    assert result.entry.result == "Microservices answer"


async def test_cache_miss_for_unrelated_text(db_session: AsyncSession, semantic_embeddings):
    cache_service = SemanticCacheService(db_session)
    await cache_service.store(
        input_text="Design a REST API for user authentication",
        result="POST /login, POST /register",
        stage_type="design",
    )
    await db_session.commit()

    result = await cache_service.lookup(input_text="How to make pasta carbonara", stage_type="design")
    assert result.cache_hit is False


async def test_cache_miss_for_different_stage_type(db_session: AsyncSession, semantic_embeddings):
    cache_service = SemanticCacheService(db_session)
    await cache_service.store(
        input_text="Explain REST API design", result="REST API design principles...", stage_type="analysis"
    )
    await db_session.commit()

    result = await cache_service.lookup(input_text="Explain REST API design", stage_type="design")
    assert result.cache_hit is False


async def test_default_threshold_is_respected(db_session: AsyncSession, semantic_embeddings):
    """At the default 0.92 threshold a 0.904 paraphrase misses; lowering the threshold hits."""
    assert settings.CACHE_SIMILARITY_THRESHOLD == pytest.approx(0.92)
    cache_service = SemanticCacheService(db_session)
    await cache_service.store(
        input_text="Design a REST API for user authentication", result="auth API", stage_type="design"
    )
    await db_session.commit()

    query = "Create a RESTful API for authenticating users"
    assert (await cache_service.lookup(input_text=query, stage_type="design")).cache_hit is False
    assert (await cache_service.lookup(input_text=query, stage_type="design",
                                       similarity_threshold=0.85)).cache_hit is True


async def test_cache_tracks_hit_count(db_session: AsyncSession, semantic_embeddings):
    cache_service = SemanticCacheService(db_session)
    entry = await cache_service.store(input_text="Test query", result="Test result", stage_type="analysis")
    await db_session.commit()
    initial_hits = entry.hit_count

    for _ in range(5):
        await cache_service.lookup(input_text="Test query", stage_type="analysis")
    await db_session.commit()

    await db_session.refresh(entry)
    assert entry.hit_count == initial_hits + 5


async def test_cache_hit_rate_calculation(db_session: AsyncSession, client, semantic_embeddings):
    """3 entries (3 misses) + 9 hits → 9 / 12 = 75%, via both SQL and the stats API."""
    cache_service = SemanticCacheService(db_session)
    queries = ["Summarise the user requirements", "Draw the system architecture", "Write unit tests for the API"]
    for i, q in enumerate(queries):
        await cache_service.store(input_text=q, result=f"Result {i}", stage_type="analysis", result_tokens=100)
    await db_session.commit()

    for q in queries:
        for _ in range(3):
            assert (await cache_service.lookup(input_text=q, stage_type="analysis")).cache_hit
    await db_session.commit()

    total_entries, total_hits = (await db_session.execute(
        select(func.count(CacheEntry.id), func.sum(CacheEntry.hit_count)).where(CacheEntry.is_valid == True)
    )).one()
    assert total_entries == 3
    assert total_hits == 9
    assert total_hits / (total_entries + total_hits) == pytest.approx(0.75)

    stats = (await client.get("/api/cache/stats")).json()
    assert stats["hit_rate"] == pytest.approx(0.75)
    assert stats["total_tokens_saved"] == 900


# ============================================================================
# Workflow-Aware Cache Validation
# ============================================================================

async def test_dependency_hash_invalidates_cache(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow, semantic_embeddings
):
    """Changing upstream output changes the dependency hash and makes the entry stale."""
    workflow = sample_workflow_with_stages
    stage1, stage2, _ = await _stages(db_session, workflow)
    cache_service = SemanticCacheService(db_session)
    validator = CacheValidator(db_session)
    ctx_mgr = ContextManager(db_session)

    exec1 = uuid.uuid4()
    await ctx_mgr.add_context(workflow.id, exec1, stage1.id, content="Stage 1 output: Requirements A, B, C")
    await db_session.commit()

    entry = await cache_service.store_with_dependencies(
        input_text="Design based on requirements", result="Design result",
        workflow_id=workflow.id, execution_id=exec1, current_stage=stage2,
    )
    await db_session.commit()
    hash1 = entry.dependency_hash

    exec2 = uuid.uuid4()
    await ctx_mgr.add_context(workflow.id, exec2, stage1.id, content="Stage 1 output: Requirements X, Y, Z")
    await db_session.commit()
    hash2 = await validator.compute_dependency_hash(workflow.id, exec2, stage2)

    assert hash1 != hash2
    assert await validator.is_cache_valid(entry, hash2) is False
    assert await validator.is_cache_valid(entry, hash1) is True

    # The workflow-aware lookup refuses the stale entry even though the text is identical
    stale = await cache_service.lookup_with_validation(
        input_text="Design based on requirements", workflow_id=workflow.id,
        execution_id=exec2, current_stage=stage2,
    )
    assert stale.cache_hit is False


async def test_downstream_cache_invalidation(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow, semantic_embeddings
):
    """Re-running stage 1 invalidates stages 2 and 3 but leaves stage 1's entry alone."""
    workflow = sample_workflow_with_stages
    stages = await _stages(db_session, workflow)
    cache_service = SemanticCacheService(db_session)

    entries = [
        await cache_service.store(
            input_text=f"{s.name} input", result=f"{s.name} result",
            workflow_id=workflow.id, stage_id=s.id, stage_type=s.stage_type,
        )
        for s in stages
    ]
    await db_session.commit()

    count = await CacheValidator(db_session).invalidate_downstream_cache(workflow.id, stages[0].id)
    await db_session.commit()

    assert count == 2
    for e in entries:
        await db_session.refresh(e)
    assert [e.is_valid for e in entries] == [True, False, False]


# ============================================================================
# Execution Engine Integration
# ============================================================================

async def test_execution_uses_cache_second_run(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow, fake_provider, semantic_embeddings
):
    workflow = sample_workflow_with_stages

    exec1 = await _execute(db_session, workflow.id)
    assert fake_provider.calls == 3

    fake_provider.calls = 0
    exec2 = await _execute(db_session, workflow.id)
    assert fake_provider.calls == 0

    records1 = await _records(db_session, exec1)
    records2 = await _records(db_session, exec2)
    assert len(records2) == 3
    assert all(r.provider == "cache" and r.cache_hit for r in records2)
    assert [r.result for r in records2] == [r.result for r in records1]


async def test_cache_reduces_execution_time(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow, fake_provider, semantic_embeddings
):
    """With 300ms simulated LLM latency per stage, the cached run skips all of it."""
    fake_provider.delay_s = 0.3
    workflow = sample_workflow_with_stages

    start = time.perf_counter()
    exec1 = await _execute(db_session, workflow.id)
    duration1 = time.perf_counter() - start

    start = time.perf_counter()
    exec2 = await _execute(db_session, workflow.id)
    duration2 = time.perf_counter() - start

    print(f"\n  uncached: {duration1:.3f}s  cached: {duration2:.3f}s  "
          f"speed-up: {duration1 / duration2:.1f}x")

    assert duration1 >= 0.9                    # 3 stages × 300ms of LLM latency
    assert duration2 < duration1 - 0.6         # cached run avoids (nearly) all of it
    assert sum(r.latency_ms or 0 for r in await _records(db_session, exec1)) == 900
    assert sum(r.latency_ms or 0 for r in await _records(db_session, exec2)) == 0


async def test_upstream_change_forces_downstream_reexecution(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow, fake_provider, semantic_embeddings
):
    """Invalidating stage 1 + a new stage 1 output → stages 2 and 3 miss via dependency hash."""
    workflow = sample_workflow_with_stages
    stages = await _stages(db_session, workflow)
    await _execute(db_session, workflow.id)

    await SemanticCacheService(db_session).invalidate(stage_id=stages[0].id)
    await db_session.commit()

    fake_provider.calls = 0
    fake_provider.version = 2
    exec2 = await _execute(db_session, workflow.id)

    assert fake_provider.calls == 3
    assert [r.cache_hit for r in await _records(db_session, exec2)] == [False, False, False]


# ============================================================================
# End-to-End via the HTTP API
# ============================================================================

async def test_e2e_workflow_with_caching(client, db_session: AsyncSession, fake_provider, semantic_embeddings):
    """
    Create workflow + stages via API → execute → cache filled → re-execute → all cache
    hits → execution details and cache stats reflect it → clear cache → misses again.
    """
    resp = await client.post("/api/workflows", json={"name": "E2E Cache Test",
                                                     "objective": "Test full caching pipeline"})
    assert resp.status_code == 201, resp.text
    workflow_id = resp.json()["id"]

    for order, (name, stage_type, instruction) in enumerate([
        ("Analyze", "analysis", "Analyze requirements"),
        ("Design", "design", "Design architecture"),
    ]):
        resp = await client.post("/api/stages", json={
            "workflow_id": workflow_id, "name": name, "instruction": instruction,
            "stage_order": order, "stage_type": stage_type,
        })
        assert resp.status_code == 201, resp.text

    # First execution — LLM called for both stages, both cached
    resp = await client.post(f"/api/workflows/{workflow_id}/execute", json={"default_provider": "fake"})
    assert resp.status_code == 200, resp.text
    exec1 = resp.json()["execution_id"]
    assert fake_provider.calls == 2

    entries = (await client.get("/api/cache/entries", params={"workflow_id": workflow_id})).json()
    assert len(entries) == 2
    assert {e["stage_type"] for e in entries} == {"analysis", "design"}

    # Second execution — served entirely from cache
    fake_provider.calls = 0
    resp = await client.post(f"/api/workflows/{workflow_id}/execute", json={"default_provider": "fake"})
    assert resp.status_code == 200, resp.text
    exec2 = resp.json()["execution_id"]
    assert fake_provider.calls == 0

    details1 = (await client.get(f"/api/executions/{exec1}")).json()
    details2 = (await client.get(f"/api/executions/{exec2}")).json()
    assert [s["result"] for s in details2["stages"]] == [s["result"] for s in details1["stages"]]
    assert all(s["cache_hit"] and s["provider"] == "cache" for s in details2["stages"])
    assert all(s["tokens_saved"] == 150 and s["cache_similarity"] >= 0.99 for s in details2["stages"])
    assert float(details2["summary"]["total_cost"]) == 0
    assert details2["summary"]["total_tokens"] == 0

    stats = (await client.get("/api/cache/stats", params={"workflow_id": workflow_id})).json()
    assert stats["total_entries"] == 2
    assert stats["total_hits"] == 2
    assert stats["hit_rate"] == pytest.approx(0.5)

    hit_rate = (await client.get(f"/api/cache/hit-rate/{workflow_id}")).json()
    assert hit_rate["hit_rate_percentage"] == "50.00%"

    # Clear → next run misses again
    resp = await client.post("/api/cache/clear", params={"workflow_id": workflow_id})
    assert resp.json()["entries_invalidated"] == 2
    resp = await client.post(f"/api/workflows/{workflow_id}/execute", json={"default_provider": "fake"})
    assert resp.status_code == 200, resp.text
    assert fake_provider.calls == 2
