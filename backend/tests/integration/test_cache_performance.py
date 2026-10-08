"""
Cache Performance Benchmarks.

Run with `-s` to see the measurements:
    python -m pytest backend/tests/test_cache_performance.py -v -s

Thresholds are deliberately generous (they guard against regressions such as an
accidental full-table scan or re-loading the model per call, not machine speed).
"""
import statistics
import time
import uuid

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models.cache import CacheEntry
from backend.app.services.cache.semantic_cache import SemanticCacheService
from backend.app.services.embedding_service import EmbeddingService

from backend.tests.conftest import text_hash_embedding

pytestmark = pytest.mark.performance

N_ENTRIES = 500
N_LOOKUPS = 30


def _report(label: str, samples_s: list[float]) -> tuple[float, float]:
    ms = sorted(s * 1000 for s in samples_s)
    p50 = statistics.median(ms)
    p95 = ms[max(0, int(len(ms) * 0.95) - 1)]
    print(f"\n  {label}: p50 {p50:.1f}ms  p95 {p95:.1f}ms  (n={len(ms)})")
    return p50, p95


async def _seed_entries(db: AsyncSession, n: int) -> list[str]:
    """Bulk-insert n cache entries with text-hash embeddings; returns their input texts."""
    texts = [f"Benchmark stage input #{i}: describe component {i} of the system" for i in range(n)]
    await db.execute(insert(CacheEntry), [
        {"id": uuid.uuid4(), "input_text": t, "input_embedding": text_hash_embedding(t),
         "result": f"result {i}", "stage_type": "analysis", "result_tokens": 100}
        for i, t in enumerate(texts)
    ])
    await db.commit()
    return texts


async def test_local_embedding_generation_latency(local_embedding_service):
    """Warm local-model embedding latency."""
    await local_embedding_service.generate_embedding("warm-up")

    samples = []
    for i in range(N_LOOKUPS):
        start = time.perf_counter()
        await local_embedding_service.generate_embedding(f"Test text for latency benchmark {i}")
        samples.append(time.perf_counter() - start)

    p50, p95 = _report("local embedding", samples)
    assert p95 < 500


@pytest.mark.requires_openai
@pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
async def test_openai_embedding_generation_latency():
    service = EmbeddingService(provider="openai")
    start = time.perf_counter()
    await service.generate_embedding("Test text for latency benchmark")
    duration = time.perf_counter() - start
    print(f"\n  OpenAI embedding: {duration * 1000:.0f}ms")
    assert duration < 2.0


async def test_cache_lookup_db_latency(db_session: AsyncSession, mock_embeddings):
    """Vector search over N_ENTRIES entries (embedding cost excluded)."""
    texts = await _seed_entries(db_session, N_ENTRIES)
    cache_service = SemanticCacheService(db_session)

    samples = []
    for t in texts[:N_LOOKUPS]:
        start = time.perf_counter()
        result = await cache_service.lookup(input_text=t, stage_type="analysis")
        samples.append(time.perf_counter() - start)
        assert result.cache_hit and result.similarity_score >= 0.99

    p50, p95 = _report(f"cache lookup, {N_ENTRIES} entries (DB only)", samples)
    assert p95 < 250


async def test_cache_lookup_end_to_end_latency(db_session: AsyncSession, semantic_embeddings):
    """Full lookup: real local embedding + vector search."""
    cache_service = SemanticCacheService(db_session)
    queries = [f"Explain how module {i} handles user authentication" for i in range(N_LOOKUPS)]
    for i, q in enumerate(queries):
        await cache_service.store(input_text=q, result=f"answer {i}", stage_type="analysis")
    await db_session.commit()

    samples = []
    for q in queries:
        start = time.perf_counter()
        result = await cache_service.lookup(input_text=q, stage_type="analysis")
        samples.append(time.perf_counter() - start)
        assert result.cache_hit

    p50, p95 = _report("cache lookup incl. local embedding", samples)
    assert p95 < 1000


async def test_cache_store_latency(db_session: AsyncSession, semantic_embeddings):
    cache_service = SemanticCacheService(db_session)
    samples = []
    for i in range(N_LOOKUPS):
        start = time.perf_counter()
        await cache_service.store(input_text=f"Store benchmark input {i}", result="r", stage_type="design")
        samples.append(time.perf_counter() - start)
    await db_session.commit()

    p50, p95 = _report("cache store incl. local embedding", samples)
    assert p95 < 1000


async def test_lookup_recall_with_migration_ivfflat_index(db_session: AsyncSession, mock_embeddings):
    """
    The test DB is built with create_all, which doesn't create the migration's IVFFlat
    index. Recreate it exactly as the migration does — on an EMPTY table, which pgvector
    warns can hurt recall — then check every exact-match lookup still hits.
    """
    from sqlalchemy import text
    await db_session.execute(text(
        "CREATE INDEX idx_cache_entries_embedding ON cache_entries "
        "USING ivfflat (input_embedding vector_cosine_ops) WITH (lists = 100)"
    ))
    await db_session.commit()

    texts = await _seed_entries(db_session, N_ENTRIES)
    cache_service = SemanticCacheService(db_session)

    samples, hits = [], 0
    for t in texts[:N_LOOKUPS]:
        start = time.perf_counter()
        result = await cache_service.lookup(input_text=t, stage_type="analysis")
        samples.append(time.perf_counter() - start)
        hits += result.cache_hit and result.entry.input_text == t

    _report(f"cache lookup with IVFFlat index, {N_ENTRIES} entries", samples)
    assert hits == N_LOOKUPS
