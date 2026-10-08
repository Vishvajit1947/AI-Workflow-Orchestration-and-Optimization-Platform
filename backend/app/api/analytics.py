"""
Analytics API endpoints.
All routes are prefixed with /api/analytics (set in router include). Every endpoint
accepts the same optional filters: start_date, end_date (ISO datetimes) and workflow_id.
"""
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.analytics import (
    CacheMetrics, CostTrendPoint, ExecutionTimeline, LatencyMetrics, ModelUtilization,
    RoutingEffectiveness, StageTypeMetrics, TokenTrendPoint, WorkflowMetrics,
)
from backend.app.services.analytics.aggregator import MAX_TREND_DAYS, AnalyticsAggregator, AnalyticsFilter
from backend.app.services.analytics.export import AnalyticsExporter

router = APIRouter(prefix="/analytics", tags=["analytics"])


def date_filter(
    start_date: Optional[datetime] = Query(None, description="Include records created at or after this time"),
    end_date: Optional[datetime] = Query(None, description="Include records created at or before this time"),
) -> AnalyticsFilter:
    def aware(dt: Optional[datetime]) -> Optional[datetime]:
        return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt  # naive = UTC
    start, end = aware(start_date), aware(end_date)
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start_date must be before end_date")
    return AnalyticsFilter(start_date=start, end_date=end)


def analytics_filter(
    flt: AnalyticsFilter = Depends(date_filter),
    workflow_id: Optional[uuid.UUID] = Query(None, description="Only this workflow"),
) -> AnalyticsFilter:
    flt.workflow_id = workflow_id
    return flt


@router.get("/overview", response_model=WorkflowMetrics)
async def get_overview(flt: AnalyticsFilter = Depends(analytics_filter), db: AsyncSession = Depends(get_db)):
    """Headline execution, stage, token, cost and latency metrics."""
    return await AnalyticsAggregator(db).get_workflow_metrics(flt)


@router.get("/workflows/{workflow_id}", response_model=WorkflowMetrics)
async def get_workflow_metrics(workflow_id: uuid.UUID, flt: AnalyticsFilter = Depends(date_filter),
                               db: AsyncSession = Depends(get_db)):
    flt.workflow_id = workflow_id
    return await AnalyticsAggregator(db).get_workflow_metrics(flt)


@router.get("/stage-types", response_model=list[StageTypeMetrics])
async def get_stage_type_metrics(flt: AnalyticsFilter = Depends(analytics_filter), db: AsyncSession = Depends(get_db)):
    return await AnalyticsAggregator(db).get_stage_type_metrics(flt)


@router.get("/cache", response_model=CacheMetrics)
async def get_cache_metrics(flt: AnalyticsFilter = Depends(analytics_filter), db: AsyncSession = Depends(get_db)):
    """Hit rate = cache hits / (cache hits + LLM calls) over stage runs in the slice."""
    return await AnalyticsAggregator(db).get_cache_metrics(flt)


@router.get("/models", response_model=list[ModelUtilization])
async def get_model_utilization(flt: AnalyticsFilter = Depends(analytics_filter), db: AsyncSession = Depends(get_db)):
    return await AnalyticsAggregator(db).get_model_utilization(flt)


@router.get("/latency", response_model=LatencyMetrics)
async def get_latency(flt: AnalyticsFilter = Depends(analytics_filter), db: AsyncSession = Depends(get_db)):
    """Latency percentiles of LLM calls (cache hits excluded)."""
    return await AnalyticsAggregator(db).get_latency_metrics(flt)


@router.get("/costs", response_model=list[CostTrendPoint])
async def get_cost_trend(days: int = Query(30, ge=1, le=MAX_TREND_DAYS, description="Used when start_date is not given"),
                         flt: AnalyticsFilter = Depends(analytics_filter), db: AsyncSession = Depends(get_db)):
    """Daily cost (UTC days); every day in the range is present, zero when idle."""
    return await AnalyticsAggregator(db).get_cost_trend(flt, days)


@router.get("/tokens", response_model=list[TokenTrendPoint])
async def get_token_trend(days: int = Query(30, ge=1, le=MAX_TREND_DAYS, description="Used when start_date is not given"),
                          flt: AnalyticsFilter = Depends(analytics_filter), db: AsyncSession = Depends(get_db)):
    return await AnalyticsAggregator(db).get_token_usage_trend(flt, days)


@router.get("/routing", response_model=RoutingEffectiveness)
async def get_routing_effectiveness(flt: AnalyticsFilter = Depends(analytics_filter), db: AsyncSession = Depends(get_db)):
    return await AnalyticsAggregator(db).get_routing_effectiveness(flt)


@router.get("/timeline/{execution_id}", response_model=ExecutionTimeline)
async def get_execution_timeline(execution_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Stage runs of one execution with start/end offsets, for a Gantt chart."""
    timeline = await AnalyticsAggregator(db).get_execution_timeline(execution_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    return timeline


@router.get("/export")
async def export_analytics(
    format: Literal["csv", "json"] = Query("json"),
    dataset: Literal["summary", "stage_runs"] = Query("summary", description="Aggregate report, or one row per stage run"),
    flt: AnalyticsFilter = Depends(analytics_filter),
    db: AsyncSession = Depends(get_db),
):
    """Download analytics as a CSV or JSON file."""
    exporter = AnalyticsExporter(db)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if format == "csv":
        content, media_type = await exporter.export_csv(flt, dataset), "text/csv"
    else:
        content, media_type = await exporter.export_json(flt, dataset), "application/json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="analytics-{dataset}-{stamp}.{format}"'},
    )
