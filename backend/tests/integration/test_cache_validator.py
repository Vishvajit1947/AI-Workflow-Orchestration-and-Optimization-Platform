"""
Cache Validator Tests.

Integration tests against the test PostgreSQL database (with vector extension).
The embedding service is mocked so tests don't need an OpenAI API key.
"""
import math
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.models.cache import CacheEntry
from backend.app.models.stage import Stage, StageDependency
from backend.app.models.workflow import Workflow
from backend.app.services.cache.cache_validator import CacheValidator
from backend.app.services.cache.semantic_cache import SemanticCacheService
from backend.app.services.context_manager import ContextManager

EMBEDDING_SERVICE_PATH = "backend.app.services.cache.semantic_cache.get_embedding_service"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding(seed: float = 0.1, dim: int = 1536) -> list:
    v = [seed + i * 0.0001 for i in range(dim)]
    magnitude = math.sqrt(sum(x * x for x in v))
    return [x / magnitude for x in v]


def _mock_embedding_service(embedding: list | None = None):
    mock_svc = MagicMock()
    mock_svc.generate_embedding = AsyncMock(return_value=embedding or _make_embedding())
    return patch(EMBEDDING_SERVICE_PATH, MagicMock(return_value=mock_svc))


async def _create_workflow(db: AsyncSession, n_stages: int) -> tuple[Workflow, list[Stage]]:
    workflow = Workflow(name="Test", objective="Test cache validation")
    db.add(workflow)
    await db.flush()

    types = ["analysis", "design", "generation", "testing"]
    stages = [
        Stage(
            workflow_id=workflow.id, name=f"Stage {i + 1}",
            instruction=f"Stage {i + 1} instruction", stage_order=i,
            stage_type=types[i % len(types)],
        )
        for i in range(n_stages)
    ]
    db.add_all(stages)
    await db.flush()
    return workflow, stages


# ---------------------------------------------------------------------------
# Dependency hash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dependency_hash_computation(db_session: AsyncSession):
    """Hash is a SHA-256 digest and changes when upstream output changes."""
    workflow, (stage1, stage2) = await _create_workflow(db_session, 2)
    execution_id = uuid.uuid4()

    ctx_mgr = ContextManager(db_session)
    await ctx_mgr.add_context(
        workflow.id, execution_id, stage1.id,
        content="Stage 1 output", context_type="stage_output",
    )
    await db_session.commit()

    validator = CacheValidator(db_session)
    hash1 = await validator.compute_dependency_hash(workflow.id, execution_id, stage2)

    assert hash1 is not None
    assert len(hash1) == 64

    # Same inputs → same hash (deterministic)
    assert await validator.compute_dependency_hash(workflow.id, execution_id, stage2) == hash1

    await ctx_mgr.add_context(
        workflow.id, execution_id, stage1.id,
        content="Stage 1 updated output", context_type="stage_output",
    )
    await db_session.commit()

    hash2 = await validator.compute_dependency_hash(workflow.id, execution_id, stage2)
    assert hash2 != hash1


@pytest.mark.asyncio
async def test_dependency_hash_same_outputs_across_executions(db_session: AsyncSession):
    """Two executions with identical upstream outputs share a hash, so the cache can be reused."""
    workflow, (stage1, stage2) = await _create_workflow(db_session, 2)
    ctx_mgr = ContextManager(db_session)
    validator = CacheValidator(db_session)

    exec_a, exec_b = uuid.uuid4(), uuid.uuid4()
    for exec_id in (exec_a, exec_b):
        await ctx_mgr.add_context(workflow.id, exec_id, stage1.id, content="Same output")
    await db_session.commit()

    hash_a = await validator.compute_dependency_hash(workflow.id, exec_a, stage2)
    hash_b = await validator.compute_dependency_hash(workflow.id, exec_b, stage2)
    assert hash_a == hash_b


@pytest.mark.asyncio
async def test_dependency_hash_no_dependencies(db_session: AsyncSession):
    """First stage has no upstream outputs → hash of empty input."""
    import hashlib

    workflow, (stage1,) = await _create_workflow(db_session, 1)
    validator = CacheValidator(db_session)

    h = await validator.compute_dependency_hash(workflow.id, uuid.uuid4(), stage1)
    assert h == hashlib.sha256(b"").hexdigest()


# ---------------------------------------------------------------------------
# is_cache_valid
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_ttl_expiry(db_session: AsyncSession):
    """Entry past its expires_at is invalid."""
    entry = CacheEntry(
        input_text="Test",
        input_embedding=[0.1] * 1536,
        result="Test result",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(entry)
    await db_session.commit()

    validator = CacheValidator(db_session)
    assert await validator.is_cache_valid(entry) is False


@pytest.mark.asyncio
async def test_is_cache_valid_checks_flag_and_hash(db_session: AsyncSession):
    """Validity flag and dependency hash mismatch both make an entry invalid."""
    entry = CacheEntry(
        input_text="Test",
        input_embedding=[0.1] * 1536,
        result="Test result",
        dependency_hash="a" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(entry)
    await db_session.commit()

    validator = CacheValidator(db_session)
    assert await validator.is_cache_valid(entry) is True
    assert await validator.is_cache_valid(entry, "a" * 64) is True
    assert await validator.is_cache_valid(entry, "b" * 64) is False

    entry.is_valid = False
    assert await validator.is_cache_valid(entry, "a" * 64) is False


# ---------------------------------------------------------------------------
# Downstream invalidation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_invalidation_on_upstream_change(db_session: AsyncSession):
    """Re-executing stage 1 invalidates stage 2's cached result."""
    workflow, (stage1, stage2) = await _create_workflow(db_session, 2)
    execution_id = uuid.uuid4()

    ctx_mgr = ContextManager(db_session)
    await ctx_mgr.add_context(
        workflow.id, execution_id, stage1.id,
        content="Initial requirements", context_type="stage_output",
    )
    await db_session.commit()

    with _mock_embedding_service():
        cache_service = SemanticCacheService(db_session)
        entry = await cache_service.store_with_dependencies(
            input_text="Design based on requirements",
            result="Initial design",
            workflow_id=workflow.id,
            execution_id=execution_id,
            current_stage=stage2,
            model_used="gpt-4o-mini",
        )
        await db_session.commit()

    assert entry.is_valid is True
    assert entry.stage_id == stage2.id
    assert entry.dependency_hash is not None

    validator = CacheValidator(db_session)
    invalidated = await validator.invalidate_downstream_cache(workflow.id, stage1.id)
    await db_session.commit()

    assert invalidated == 1

    await db_session.refresh(entry)
    assert entry.is_valid is False


@pytest.mark.asyncio
async def test_invalidation_cascades_and_spares_upstream(db_session: AsyncSession):
    """Changing stage 2 invalidates stages 3 and 4 but not stage 1."""
    workflow, stages = await _create_workflow(db_session, 4)

    entries = [
        CacheEntry(
            workflow_id=workflow.id, stage_id=s.id, stage_type=s.stage_type,
            input_text=f"input {i}", input_embedding=_make_embedding(0.1 + i),
            result=f"result {i}",
        )
        for i, s in enumerate(stages)
    ]
    db_session.add_all(entries)
    await db_session.commit()

    validator = CacheValidator(db_session)
    invalidated = await validator.invalidate_downstream_cache(workflow.id, stages[1].id)
    await db_session.commit()

    assert invalidated == 2
    for e in entries:
        await db_session.refresh(e)
    assert [e.is_valid for e in entries] == [True, True, False, False]


@pytest.mark.asyncio
async def test_invalidation_follows_explicit_dependencies(db_session: AsyncSession):
    """A stage with a lower stage_order that explicitly depends on the changed stage is invalidated."""
    workflow, (stage_a, stage_b) = await _create_workflow(db_session, 2)
    # stage_a (order 0) explicitly depends on stage_b (order 1)
    db_session.add(StageDependency(stage_id=stage_a.id, depends_on_stage_id=stage_b.id))

    entry = CacheEntry(
        workflow_id=workflow.id, stage_id=stage_a.id,
        input_text="input", input_embedding=_make_embedding(), result="result",
    )
    db_session.add(entry)
    await db_session.commit()

    validator = CacheValidator(db_session)
    assert await validator.invalidate_downstream_cache(workflow.id, stage_b.id) == 1


@pytest.mark.asyncio
async def test_invalidate_unknown_stage_returns_zero(db_session: AsyncSession):
    workflow, _ = await _create_workflow(db_session, 1)
    validator = CacheValidator(db_session)
    assert await validator.invalidate_downstream_cache(workflow.id, uuid.uuid4()) == 0


# ---------------------------------------------------------------------------
# TTL cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup_expired_entries(db_session: AsyncSession):
    """Only expired entries are marked invalid."""
    valid_entry = CacheEntry(
        input_text="Valid",
        input_embedding=[0.1] * 1536,
        result="Valid result",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    expired_entry = CacheEntry(
        input_text="Expired",
        input_embedding=[0.2] * 1536,
        result="Expired result",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add_all([valid_entry, expired_entry])
    await db_session.commit()

    validator = CacheValidator(db_session)
    cleaned = await validator.cleanup_expired_entries()
    await db_session.commit()

    assert cleaned == 1

    await db_session.refresh(expired_entry)
    assert expired_entry.is_valid is False

    await db_session.refresh(valid_entry)
    assert valid_entry.is_valid is True


@pytest.mark.asyncio
async def test_store_with_dependencies_uses_configured_ttl(db_session: AsyncSession, monkeypatch):
    """Default TTL comes from CACHE_TTL_SECONDS; ttl_seconds=0 disables expiry."""
    monkeypatch.setattr(settings, "CACHE_TTL_SECONDS", 3600)
    workflow, (stage1,) = await _create_workflow(db_session, 1)
    execution_id = uuid.uuid4()

    with _mock_embedding_service():
        cache_service = SemanticCacheService(db_session)
        entry = await cache_service.store_with_dependencies(
            input_text="x", result="y", workflow_id=workflow.id,
            execution_id=execution_id, current_stage=stage1,
        )
        no_expiry = await cache_service.store_with_dependencies(
            input_text="x2", result="y2", workflow_id=workflow.id,
            execution_id=execution_id, current_stage=stage1, ttl_seconds=0,
        )

    remaining = (entry.expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 3500 < remaining <= 3600
    assert no_expiry.expires_at is None


# ---------------------------------------------------------------------------
# Workflow-aware lookup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lookup_with_validation_hits_then_misses_on_upstream_change(db_session: AsyncSession):
    """Hit while upstream output is unchanged; miss once upstream output changes."""
    workflow, (stage1, stage2) = await _create_workflow(db_session, 2)
    ctx_mgr = ContextManager(db_session)

    exec1 = uuid.uuid4()
    await ctx_mgr.add_context(workflow.id, exec1, stage1.id, content="Requirements v1")
    await db_session.commit()

    with _mock_embedding_service():
        cache_service = SemanticCacheService(db_session)
        await cache_service.store_with_dependencies(
            input_text="Design it", result="Design v1",
            workflow_id=workflow.id, execution_id=exec1, current_stage=stage2,
        )
        await db_session.commit()

        # New execution, same upstream output → hit
        exec2 = uuid.uuid4()
        await ctx_mgr.add_context(workflow.id, exec2, stage1.id, content="Requirements v1")
        await db_session.commit()
        hit = await cache_service.lookup_with_validation(
            input_text="Design it", workflow_id=workflow.id,
            execution_id=exec2, current_stage=stage2,
        )
        assert hit.cache_hit is True
        assert hit.entry.result == "Design v1"

        # New execution, different upstream output → miss
        exec3 = uuid.uuid4()
        await ctx_mgr.add_context(workflow.id, exec3, stage1.id, content="Requirements v2")
        await db_session.commit()
        miss = await cache_service.lookup_with_validation(
            input_text="Design it", workflow_id=workflow.id,
            execution_id=exec3, current_stage=stage2,
        )
        assert miss.cache_hit is False


@pytest.mark.asyncio
async def test_lookup_with_validation_disabled(db_session: AsyncSession, monkeypatch):
    """With workflow validation off, dependency hash is ignored."""
    monkeypatch.setattr(settings, "CACHE_ENABLE_WORKFLOW_VALIDATION", False)
    workflow, (stage1, stage2) = await _create_workflow(db_session, 2)
    ctx_mgr = ContextManager(db_session)

    exec1, exec2 = uuid.uuid4(), uuid.uuid4()
    await ctx_mgr.add_context(workflow.id, exec1, stage1.id, content="Requirements v1")
    await ctx_mgr.add_context(workflow.id, exec2, stage1.id, content="Requirements v2")
    await db_session.commit()

    with _mock_embedding_service():
        cache_service = SemanticCacheService(db_session)
        await cache_service.store_with_dependencies(
            input_text="Design it", result="Design v1",
            workflow_id=workflow.id, execution_id=exec1, current_stage=stage2,
        )
        await db_session.commit()

        hit = await cache_service.lookup_with_validation(
            input_text="Design it", workflow_id=workflow.id,
            execution_id=exec2, current_stage=stage2,
        )
    assert hit.cache_hit is True
