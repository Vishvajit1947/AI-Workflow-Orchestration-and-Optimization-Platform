"""
Semantic Cache Service Tests.

Integration tests run against the live PostgreSQL database (with vector extension).
The embedding service is mocked to return 1536-dim vectors so tests are fast,
deterministic, and don't require an OpenAI API key.
"""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from backend.app.services.cache.semantic_cache import SemanticCacheService
    from backend.app.models.cache import CacheEntry
    EMBEDDING_SERVICE_PATH = "backend.app.services.cache.semantic_cache.get_embedding_service"
except ImportError:
    from app.services.cache.semantic_cache import SemanticCacheService
    from app.models.cache import CacheEntry
    EMBEDDING_SERVICE_PATH = "app.services.cache.semantic_cache.get_embedding_service"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding(seed: float = 0.1, dim: int = 1536) -> list:
    """Return a deterministic unit-like vector of length `dim`."""
    import math
    v = [seed + i * 0.0001 for i in range(dim)]
    magnitude = math.sqrt(sum(x * x for x in v))
    return [x / magnitude for x in v]


def _mock_embedding_service(embedding: list | None = None):
    """Return a patched get_embedding_service that yields a mock service."""
    mock_svc = MagicMock()
    mock_svc.generate_embedding = AsyncMock(return_value=embedding or _make_embedding())
    mock_factory = MagicMock(return_value=mock_svc)
    return patch(EMBEDDING_SERVICE_PATH, mock_factory)


# ---------------------------------------------------------------------------
# Integration tests (live DB, mocked embeddings)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_store_and_lookup(db_session: AsyncSession):
    """Store an entry and retrieve it with the same text (near-identical embedding)."""
    vec = _make_embedding(seed=0.1)

    with _mock_embedding_service(vec):
        cache_service = SemanticCacheService(db_session)

        entry = await cache_service.store(
            input_text="What are the key features of a todo app?",
            result="Key features: create, read, update, delete tasks",
            stage_type="analysis",
            result_tokens=50,
            model_used="gpt-4o-mini",
        )
        await db_session.commit()

        assert entry.id is not None
        assert entry.hit_count == 0

        # Lookup with the same embedding (identical vectors → similarity ≈ 1)
        hit = await cache_service.lookup(
            input_text="What are the key features of a todo app?",
            stage_type="analysis",
        )
        await db_session.commit()

    assert hit.cache_hit is True
    assert hit.entry is not None
    assert hit.entry.result == "Key features: create, read, update, delete tasks"
    assert hit.similarity_score >= 0.99
    assert hit.tokens_saved == 50


@pytest.mark.asyncio
async def test_cache_semantic_similarity(db_session: AsyncSession):
    """Test that a stored entry is retrieved when query embedding is similar."""
    stored_vec = _make_embedding(seed=0.2)
    # Query vector is slightly different — cosine similarity will be very high
    query_vec = _make_embedding(seed=0.201)

    with patch(EMBEDDING_SERVICE_PATH) as mock_factory:
        mock_svc = MagicMock()
        # First call (store) → stored_vec; subsequent calls (lookup) → query_vec
        mock_svc.generate_embedding = AsyncMock(side_effect=[stored_vec, query_vec])
        mock_factory.return_value = mock_svc

        cache_service = SemanticCacheService(db_session)

        await cache_service.store(
            input_text="List the main requirements for a task management application",
            result="Requirements: CRUD operations, user auth, categories",
            stage_type="analysis",
        )
        await db_session.commit()

        hit = await cache_service.lookup(
            input_text="What are the core features needed for a task manager?",
            stage_type="analysis",
            similarity_threshold=0.70,
        )

    assert hit.cache_hit is True
    assert hit.similarity_score >= 0.70


@pytest.mark.asyncio
async def test_cache_miss_on_different_text(db_session: AsyncSession):
    """Unrelated query embedding does not produce a cache hit above the threshold."""
    stored_vec = _make_embedding(seed=0.1)
    # Negative / orthogonal vector → low cosine similarity
    unrelated_vec = [-x for x in stored_vec]

    with patch(EMBEDDING_SERVICE_PATH) as mock_factory:
        mock_svc = MagicMock()
        mock_svc.generate_embedding = AsyncMock(side_effect=[stored_vec, unrelated_vec])
        mock_factory.return_value = mock_svc

        cache_service = SemanticCacheService(db_session)

        await cache_service.store(
            input_text="Design a REST API for user authentication",
            result="API endpoints: POST /login, POST /register, GET /profile",
            stage_type="design",
        )
        await db_session.commit()

        hit = await cache_service.lookup(
            input_text="How to cook pasta?",
            stage_type="design",
        )

    assert hit.cache_hit is False
    assert hit.entry is None


@pytest.mark.asyncio
async def test_cache_invalidation(db_session: AsyncSession):
    """Invalidated entries must not be returned on lookup."""
    vec = _make_embedding(seed=0.5)

    with _mock_embedding_service(vec):
        cache_service = SemanticCacheService(db_session)

        await cache_service.store(
            input_text="Test input for invalidation",
            result="Test result",
            stage_type="analysis",
        )
        await db_session.commit()

        count = await cache_service.invalidate(stage_type="analysis")
        await db_session.commit()

        assert count == 1

        hit = await cache_service.lookup(
            input_text="Test input for invalidation",
            stage_type="analysis",
        )

    assert hit.cache_hit is False


@pytest.mark.asyncio
async def test_hit_count_increment(db_session: AsyncSession):
    """hit_count must increment by 1 on each cache hit."""
    vec = _make_embedding(seed=0.7)

    with _mock_embedding_service(vec):
        cache_service = SemanticCacheService(db_session)

        entry = await cache_service.store(
            input_text="Unique text for hit count test",
            result="Some result",
        )
        await db_session.commit()

        initial_hits = entry.hit_count  # 0

        for _ in range(3):
            hit = await cache_service.lookup(input_text="Unique text for hit count test")
            assert hit.cache_hit is True

        await db_session.commit()
        await db_session.refresh(entry)

    assert entry.hit_count == initial_hits + 3


# ---------------------------------------------------------------------------
# Unit tests (no DB required)
# ---------------------------------------------------------------------------

def test_compute_dependency_hash():
    """Dependency hash must be deterministic and order-sensitive."""
    outputs = ["output A", "output B", "output C"]
    h1 = SemanticCacheService.compute_dependency_hash(outputs)
    h2 = SemanticCacheService.compute_dependency_hash(outputs)

    assert h1 == h2           # deterministic
    assert len(h1) == 64      # SHA-256 hex digest

    h3 = SemanticCacheService.compute_dependency_hash(list(reversed(outputs)))
    assert h1 != h3            # order-sensitive


def test_estimate_cost_saved():
    """Cost estimate should be proportional to token count."""
    cost = SemanticCacheService._estimate_cost_saved(1000)
    assert cost == Decimal("0.001000")
    assert cost > Decimal("0")

    cost_zero = SemanticCacheService._estimate_cost_saved(0)
    assert cost_zero == Decimal("0")
