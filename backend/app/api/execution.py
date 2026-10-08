"""
Execution API endpoints.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import get_db, get_session_factory
from backend.app.models.workflow import Workflow
from backend.app.models.stage import Stage
from backend.app.models.execution import ExecutionRecord
from backend.app.schemas.execution import (
    ExecutionStartRequest, ExecutionStartResponse,
    ExecutionDetailResponse, ExecutionSummary,
    StageExecutionDetail, ExecutionListItem,
    ExecutionStatusResponse, ExecutionControlResponse,
)
from backend.app.schemas.dag import WorkflowDAGResponse
from backend.app.services.execution import ExecutionEngine
from backend.app.services.execution.dag_analyzer import DAGAnalyzer, DAGCycleError
from backend.app.services.execution.runner import start_background_execution
from backend.app.services.execution.tracker import tracker


router = APIRouter(tags=["executions"])


@router.post("/workflows/{workflow_id}/execute", response_model=ExecutionStartResponse)
async def start_workflow_execution(
    workflow_id: uuid.UUID,
    request: ExecutionStartRequest,
    db: AsyncSession = Depends(get_db),
    session_factory=Depends(get_session_factory),
):
    """
    Execute a workflow.
    By default the request waits for the execution to finish. With background=true it
    returns at once (status "running"); follow progress via GET /executions/{id}/status
    or the WebSocket at /ws/executions/{id}.
    """
    result = await db.execute(
        select(Workflow)
        .options(selectinload(Workflow.stages).selectinload(Stage.dependencies))
        .where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    if workflow.status in ("running", "paused"):
        raise HTTPException(status_code=409, detail=f"Workflow is already {workflow.status}")
    if not workflow.stages:
        raise HTTPException(status_code=422, detail="Workflow has no stages")
    try:
        DAGAnalyzer(workflow.stages)
    except DAGCycleError as e:
        raise HTTPException(status_code=422, detail=str(e))

    options = dict(
        default_provider=request.default_provider,
        default_model=request.default_model,
        use_cache=request.use_cache,
        use_routing=request.use_routing,
        routing_preferences=request.routing_preferences,
        parallel=request.parallel,
    )

    if request.background:
        # Commit "running" first so a second request gets 409 while the task starts
        workflow.status = "running"
        await db.commit()
        execution_id = start_background_execution(session_factory, workflow, options)
        return ExecutionStartResponse(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status="running",
            message="Workflow execution started in the background",
            started_at=datetime.now(timezone.utc),
        )

    # Start execution
    # Capture start time up front: workflow.updated_at is refreshed server-side on
    # status change, and lazily reloading it after commit fails under asyncio.
    started_at = datetime.now(timezone.utc)
    try:
        engine = ExecutionEngine(db)
        execution_id = await engine.execute_workflow(workflow_id, **options)
        await db.commit()

        final = tracker.get(execution_id).status
        return ExecutionStartResponse(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status=final,
            message=f"Workflow execution {final}",
            started_at=started_at
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.get("/executions/{execution_id}", response_model=ExecutionDetailResponse)
async def get_execution_details(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed execution results including all stage outputs."""
    # Get all execution records for this execution
    result = await db.execute(
        select(ExecutionRecord)
        .options(selectinload(ExecutionRecord.stage), selectinload(ExecutionRecord.workflow))
        .where(ExecutionRecord.execution_id == execution_id)
        .order_by(ExecutionRecord.created_at)
    )
    records = result.scalars().all()

    if not records:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")

    # Build summary
    workflow = records[0].workflow
    total_tokens = sum(r.total_tokens for r in records)
    total_cost = sum(r.estimated_cost or Decimal(0) for r in records)
    total_latency = sum(r.latency_ms or 0 for r in records)
    completed = sum(1 for r in records if r.status == "completed")
    failed = sum(1 for r in records if r.status == "failed")
    
    # Calculate workflow-level timing
    started_times = [r.started_at for r in records if r.started_at]
    completed_times = [r.completed_at for r in records if r.completed_at]
    workflow_started = min(started_times) if started_times else None
    workflow_completed = max(completed_times) if completed_times else None
    workflow_duration = None
    if workflow_started and workflow_completed:
        workflow_duration = int((workflow_completed - workflow_started).total_seconds() * 1000)

    summary = ExecutionSummary(
        execution_id=execution_id,
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        status=workflow.status,
        total_stages=len(records),
        completed_stages=completed,
        failed_stages=failed,
        total_tokens=total_tokens,
        total_cost=total_cost,
        total_latency_ms=total_latency,
        started_at=workflow_started,
        completed_at=workflow_completed,
        duration_ms=workflow_duration
    )

    # Build stage details
    stages = []
    for record in records:
        routing = (record.metadata_ or {}).get("routing") or {}
        attempts = (record.metadata_ or {}).get("attempts") or []
        stages.append(StageExecutionDetail(
            id=record.id,
            stage_id=record.stage_id,
            stage_name=record.stage.name if record.stage else "Unknown",
            stage_order=record.stage.stage_order if record.stage else 0,
            model_used=record.model_used,
            provider=record.provider,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            total_tokens=record.total_tokens,
            latency_ms=record.latency_ms,
            estimated_cost=record.estimated_cost,
            status=record.status,
            result=record.result,
            error_message=record.error_message,
            started_at=record.started_at,
            completed_at=record.completed_at,
            duration_ms=record.duration_ms,
            cache_hit=record.cache_hit,
            cache_similarity=(record.metadata_ or {}).get("similarity_score") if record.cache_hit else None,
            tokens_saved=(record.metadata_ or {}).get("tokens_saved") if record.cache_hit else None,
            cost_saved=(record.metadata_ or {}).get("cost_saved") if record.cache_hit else None,
            was_routed=bool(routing.get("routed")),
            routing_reason=routing.get("reason"),
            was_user_override=bool(routing.get("was_user_override")),
            was_fallback=bool(routing.get("was_fallback")),
            retry_count=len(attempts),
            fallback_from=routing.get("fallback_from"),
        ))

    return ExecutionDetailResponse(summary=summary, stages=stages)


@router.get("/executions", response_model=List[ExecutionListItem])
async def list_executions(
    workflow_id: Optional[uuid.UUID] = Query(None, description="Filter by workflow ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """List all executions, optionally filtered by workflow."""
    # Subquery to get unique execution_ids with aggregated data
    subq = (
        select(
            ExecutionRecord.execution_id,
            ExecutionRecord.workflow_id,
            func.count(ExecutionRecord.id).label("total_stages"),
            func.sum(
                func.cast(ExecutionRecord.status == "completed", Integer)
            ).label("completed_stages"),
            func.min(ExecutionRecord.started_at).label("started_at"),
            func.max(ExecutionRecord.completed_at).label("completed_at"),
            func.sum(ExecutionRecord.estimated_cost).label("total_cost")
        )
        .group_by(ExecutionRecord.execution_id, ExecutionRecord.workflow_id)
    )
    
    if workflow_id:
        subq = subq.where(ExecutionRecord.workflow_id == workflow_id)
    
    subq = subq.subquery()

    # Join with workflow to get name and status
    query = (
        select(
            subq.c.execution_id,
            subq.c.workflow_id,
            Workflow.name.label("workflow_name"),
            Workflow.status,
            subq.c.total_stages,
            subq.c.completed_stages,
            subq.c.started_at,
            subq.c.completed_at,
            subq.c.total_cost
        )
        .join(Workflow, Workflow.id == subq.c.workflow_id)
        .order_by(subq.c.started_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    rows = result.all()

    items = []
    for row in rows:
        duration_ms = None
        if row.started_at and row.completed_at:
            duration_ms = int((row.completed_at - row.started_at).total_seconds() * 1000)
        
        items.append(ExecutionListItem(
            execution_id=row.execution_id,
            workflow_id=row.workflow_id,
            workflow_name=row.workflow_name,
            status=row.status,
            total_stages=row.total_stages,
            completed_stages=row.completed_stages or 0,
            started_at=row.started_at,
            completed_at=row.completed_at,
            duration_ms=duration_ms,
            total_cost=row.total_cost or Decimal(0)
        ))

    return items


@router.get("/workflows/{workflow_id}/executions/latest", response_model=ExecutionDetailResponse)
async def get_latest_execution(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get the most recent execution for a workflow."""
    # Find latest execution_id for this workflow (by started_at)
    result = await db.execute(
        select(ExecutionRecord.execution_id)
        .where(ExecutionRecord.workflow_id == workflow_id)
        .order_by(ExecutionRecord.started_at.desc().nulls_last(), ExecutionRecord.created_at.desc())
        .limit(1)
    )
    execution_id = result.scalar_one_or_none()

    if not execution_id:
        raise HTTPException(status_code=404, detail=f"No executions found for workflow {workflow_id}")

    # Reuse get_execution_details logic
    return await get_execution_details(execution_id, db)


# ---------- Live status and control ----------

@router.get("/executions/{execution_id}/status", response_model=ExecutionStatusResponse)
async def get_execution_status(execution_id: uuid.UUID):
    """Live per-stage status of an execution run by this server (kept for a while after it ends)."""
    live = tracker.get(execution_id)
    if live is None:
        raise HTTPException(status_code=404, detail=f"No live status for execution {execution_id}")
    return live.snapshot()


CONTROL_MESSAGES = {
    "pause": "Paused: running stages finish, no new stages start",
    "resume": "Resumed",
    "cancel": "Cancelling: in-flight LLM calls are being stopped",
}


async def _control(execution_id: uuid.UUID, action: str) -> ExecutionControlResponse:
    try:
        live = await getattr(tracker, action)(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return ExecutionControlResponse(execution_id=execution_id, status=live.status, message=CONTROL_MESSAGES[action])


@router.post("/executions/{execution_id}/pause", response_model=ExecutionControlResponse)
async def pause_execution(execution_id: uuid.UUID):
    return await _control(execution_id, "pause")


@router.post("/executions/{execution_id}/resume", response_model=ExecutionControlResponse)
async def resume_execution(execution_id: uuid.UUID):
    return await _control(execution_id, "resume")


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionControlResponse)
async def cancel_execution(execution_id: uuid.UUID):
    return await _control(execution_id, "cancel")


@router.get("/workflows/{workflow_id}/dag", response_model=WorkflowDAGResponse)
async def get_workflow_dag(workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Dependency graph: execution levels, merge points, critical path, parallelism."""
    result = await db.execute(
        select(Workflow)
        .options(selectinload(Workflow.stages).selectinload(Stage.dependencies))
        .where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    try:
        analyzer = DAGAnalyzer(workflow.stages)
    except DAGCycleError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return WorkflowDAGResponse(workflow_id=workflow_id, ascii=analyzer.visualize_dag(), **analyzer.to_dict())


@router.get("/workflows/{workflow_id}/executions/live", response_model=ExecutionStatusResponse)
async def get_live_execution(workflow_id: uuid.UUID):
    """The workflow's execution that is still queued, running or paused on this server."""
    live = tracker.find_active(workflow_id)
    if live is None:
        raise HTTPException(status_code=404, detail=f"No active execution for workflow {workflow_id}")
    return live.snapshot()
