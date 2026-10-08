"""
Cache Management API endpoints.
All routes are prefixed with /api/cache (set in router include).
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, Float
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.cache import CacheEntry
from backend.app.models.execution import ExecutionRecord
from backend.app.models.workflow import Workflow
from backend.app.schemas.cache import CacheEntryResponse, CacheStats
from backend.app.schemas.execution import ExecutionStartRequest
from backend.app.services.cache.cache_validator import CacheValidator
from backend.app.services.cache.semantic_cache import SemanticCacheService
from backend.app.services.execution import ExecutionEngine


router = APIRouter(prefix="/cache", tags=["cache"])


def _hit_rate(total_entries: int, total_hits: int) -> float:
    """Each entry was created by one miss, so lookups ≈ entries + hits."""
    total_lookups = total_entries + total_hits
    return total_hits / total_lookups if total_lookups > 0 else 0.0


@router.get("/entries", response_model=List[CacheEntryResponse])
async def list_cache_entries(
    workflow_id: Optional[uuid.UUID] = Query(None, description="Filter by workflow"),
    stage_id: Optional[uuid.UUID] = Query(None, description="Filter by stage"),
    stage_type: Optional[str] = Query(None, description="Filter by stage type"),
    is_valid: Optional[bool] = Query(None, description="Filter by validity"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List cache entries with optional filters, newest first."""
    query = select(CacheEntry)

    if workflow_id:
        query = query.where(CacheEntry.workflow_id == workflow_id)
    if stage_id:
        query = query.where(CacheEntry.stage_id == stage_id)
    if stage_type:
        query = query.where(CacheEntry.stage_type == stage_type)
    if is_valid is not None:
        query = query.where(CacheEntry.is_valid == is_valid)

    query = query.order_by(CacheEntry.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)

    return [CacheEntryResponse.model_validate(e) for e in result.scalars().all()]


@router.get("/stats", response_model=CacheStats)
async def get_cache_stats(
    workflow_id: Optional[uuid.UUID] = Query(None, description="Filter by workflow"),
    db: AsyncSession = Depends(get_db),
):
    """
    Cache performance statistics.

    total_entries counts currently valid entries. Hits, tokens and cost saved
    include invalidated entries, since those savings already happened.
    """
    entry_query = select(
        func.count(CacheEntry.id).label("all_entries"),
        func.count(CacheEntry.id).filter(CacheEntry.is_valid == True).label("valid_entries"),
        func.coalesce(func.sum(CacheEntry.hit_count), 0).label("total_hits"),
        func.coalesce(
            func.sum(func.coalesce(CacheEntry.result_tokens, 0) * CacheEntry.hit_count), 0
        ).label("tokens_saved"),
    )
    similarity_query = select(
        func.avg(ExecutionRecord.metadata_["similarity_score"].astext.cast(Float))
    ).where(ExecutionRecord.cache_hit == True)

    if workflow_id:
        entry_query = entry_query.where(CacheEntry.workflow_id == workflow_id)
        similarity_query = similarity_query.where(ExecutionRecord.workflow_id == workflow_id)

    row = (await db.execute(entry_query)).one()
    avg_similarity = (await db.execute(similarity_query)).scalar()

    return CacheStats(
        total_entries=row.valid_entries,
        total_hits=row.total_hits,
        hit_rate=_hit_rate(row.all_entries, row.total_hits),
        total_tokens_saved=row.tokens_saved,
        total_cost_saved=SemanticCacheService._estimate_cost_saved(row.tokens_saved),
        avg_similarity_score=float(avg_similarity or 0.0),
    )


@router.delete("/entries/{entry_id}")
async def delete_cache_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a specific cache entry."""
    entry = await db.get(CacheEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Cache entry {entry_id} not found")

    await db.delete(entry)
    await db.commit()

    return {"message": "Cache entry deleted", "id": entry_id}


@router.post("/clear")
async def clear_cache(
    workflow_id: Optional[uuid.UUID] = Query(None),
    stage_id: Optional[uuid.UUID] = Query(None),
    stage_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Invalidate cache entries by workflow, stage, stage type, or all when no filter is given."""
    cache_service = SemanticCacheService(db)
    count = await cache_service.invalidate(
        workflow_id=workflow_id, stage_id=stage_id, stage_type=stage_type
    )
    await db.commit()

    return {
        "message": "Cache cleared",
        "entries_invalidated": count,
        "workflow_id": workflow_id,
        "stage_id": stage_id,
        "stage_type": stage_type,
    }


@router.post("/cleanup-expired")
async def cleanup_expired_cache(db: AsyncSession = Depends(get_db)):
    """Invalidate cache entries whose TTL has passed."""
    validator = CacheValidator(db)
    count = await validator.cleanup_expired_entries()
    await db.commit()

    return {"message": "Expired cache entries cleaned up", "entries_cleaned": count}


async def _run_for_cache(
    workflow_id: uuid.UUID, request: ExecutionStartRequest, db: AsyncSession,
    use_cache: bool,
) -> tuple[uuid.UUID, int, int]:
    """Execute a workflow and return (execution_id, stages served from cache, stages run by LLM)."""
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    if workflow.status == "running":
        raise HTTPException(status_code=409, detail="Workflow is already running")

    try:
        engine = ExecutionEngine(db)
        execution_id = await engine.execute_workflow(
            workflow_id,
            default_provider=request.default_provider,
            default_model=request.default_model,
            use_cache=use_cache,
            use_routing=request.use_routing,
            routing_preferences=request.routing_preferences,
            parallel=request.parallel,
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

    result = await db.execute(
        select(ExecutionRecord.cache_hit, func.count())
        .where(ExecutionRecord.execution_id == execution_id, ExecutionRecord.status == "completed")
        .group_by(ExecutionRecord.cache_hit)
    )
    counts = dict(result.all())
    return execution_id, counts.get(True, 0), counts.get(False, 0)


@router.post("/warm")
async def warm_cache(
    workflow_id: uuid.UUID = Query(..., description="Workflow to pre-warm"),
    request: ExecutionStartRequest = ExecutionStartRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Pre-warm the cache by executing the workflow once.
    Stages already cached are served from cache; the rest are run and stored,
    so subsequent executions hit the cache.
    """
    execution_id, cached, executed = await _run_for_cache(workflow_id, request, db, use_cache=True)
    return {
        "message": "Cache warmed",
        "workflow_id": workflow_id,
        "execution_id": execution_id,
        "stages_already_cached": cached,
        "stages_cached_now": executed,
    }


@router.post("/refresh/{workflow_id}")
async def refresh_workflow_cache(
    workflow_id: uuid.UUID,
    request: ExecutionStartRequest = ExecutionStartRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Force a cache refresh for a workflow: invalidate its entries, then
    re-execute every stage with the LLM and store fresh results.
    """
    if not await db.get(Workflow, workflow_id):
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    invalidated = await SemanticCacheService(db).invalidate(workflow_id=workflow_id)
    execution_id, _, executed = await _run_for_cache(workflow_id, request, db, use_cache=False)
    return {
        "message": "Cache refreshed",
        "workflow_id": workflow_id,
        "execution_id": execution_id,
        "entries_invalidated": invalidated,
        "stages_cached_now": executed,
    }


@router.get("/hit-rate/{workflow_id}")
async def get_workflow_cache_hit_rate(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cache hit rate for a specific workflow."""
    result = await db.execute(
        select(func.count(CacheEntry.id), func.coalesce(func.sum(CacheEntry.hit_count), 0))
        .where(CacheEntry.workflow_id == workflow_id)
    )
    total_entries, total_hits = result.one()
    hit_rate = _hit_rate(total_entries, total_hits)

    return {
        "workflow_id": workflow_id,
        "total_cache_entries": total_entries,
        "total_cache_hits": total_hits,
        "hit_rate": hit_rate,
        "hit_rate_percentage": f"{hit_rate * 100:.2f}%",
    }
