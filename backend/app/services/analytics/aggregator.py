"""
Analytics Aggregation Service.
Computes platform metrics from execution records, cache entries and routing decisions.

Definitions used throughout:
  - a *stage run* is one execution_records row;
  - an *LLM call* is a completed stage run that was not served from cache;
  - an execution *succeeded* if none of its stage runs failed or was cancelled.
All filters apply to execution_records.created_at (UTC); trends bucket by UTC day.
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Integer, Numeric, and_, case, cast, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.cache import CacheEntry
from backend.app.models.execution import ExecutionRecord
from backend.app.models.routing_rule import RoutingDecision
from backend.app.models.stage import Stage

DEFAULT_TREND_DAYS = 30
MAX_TREND_DAYS = 366
PERCENTILES = (0.5, 0.75, 0.9, 0.95, 0.99)


@dataclass
class AnalyticsFilter:
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    workflow_id: Optional[uuid.UUID] = None

    def conditions(self) -> list:
        conds = []
        if self.workflow_id:
            conds.append(ExecutionRecord.workflow_id == self.workflow_id)
        if self.start_date:
            conds.append(ExecutionRecord.created_at >= self.start_date)
        if self.end_date:
            conds.append(ExecutionRecord.created_at <= self.end_date)
        return conds


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 2) if whole else 0.0


def _float(value) -> float:
    return float(value or 0)


# Reusable column expressions
_TOKENS = func.coalesce(ExecutionRecord.input_tokens, 0) + func.coalesce(ExecutionRecord.output_tokens, 0)
_IS_LLM_CALL = and_(ExecutionRecord.status == "completed", ExecutionRecord.cache_hit.is_(False))
_COST_SAVED = cast(ExecutionRecord.metadata_["cost_saved"].astext, Numeric(12, 6))
_TOKENS_SAVED = cast(ExecutionRecord.metadata_["tokens_saved"].astext, Integer)


def _count_if(condition):
    return func.count(case((condition, 1)))


class AnalyticsAggregator:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- headline metrics ----------

    async def get_workflow_metrics(self, flt: Optional[AnalyticsFilter] = None) -> dict:
        """Execution, stage, token, cost and latency totals for the filtered slice."""
        flt = flt or AnalyticsFilter()
        conds = flt.conditions()

        stage_row = (await self.db.execute(
            select(
                func.count(ExecutionRecord.id).label("stage_runs"),
                _count_if(ExecutionRecord.status == "completed").label("completed"),
                _count_if(ExecutionRecord.status == "failed").label("failed"),
                _count_if(ExecutionRecord.status == "cancelled").label("cancelled"),
                _count_if(ExecutionRecord.cache_hit.is_(True)).label("cache_hits"),
                _count_if(_IS_LLM_CALL).label("llm_calls"),
                func.sum(_TOKENS).label("tokens"),
                func.sum(ExecutionRecord.estimated_cost).label("cost"),
                func.avg(case((_IS_LLM_CALL, ExecutionRecord.latency_ms))).label("avg_latency"),
            ).where(*conds)
        )).one()

        # Per-execution outcome and wall-clock duration
        per_execution = (
            select(
                ExecutionRecord.execution_id,
                func.bool_or(ExecutionRecord.status.in_(("failed", "cancelled"))).label("unsuccessful"),
                (func.extract("epoch", func.max(ExecutionRecord.completed_at) - func.min(ExecutionRecord.started_at))
                 * 1000).label("duration_ms"),
            )
            .where(*conds)
            .group_by(ExecutionRecord.execution_id)
            .subquery()
        )
        exec_row = (await self.db.execute(
            select(
                func.count().label("executions"),
                _count_if(per_execution.c.unsuccessful.is_(False)).label("succeeded"),
                func.avg(per_execution.c.duration_ms).label("avg_duration"),
            )
        )).one()

        finished_stages = stage_row.completed + stage_row.failed
        return {
            "total_executions": exec_row.executions,
            "successful_executions": exec_row.succeeded,
            "execution_success_rate": _pct(exec_row.succeeded, exec_row.executions),
            "avg_execution_duration_ms": round(_float(exec_row.avg_duration), 1),
            "total_stages": stage_row.stage_runs,
            "completed_stages": stage_row.completed,
            "failed_stages": stage_row.failed,
            "cancelled_stages": stage_row.cancelled,
            "llm_calls": stage_row.llm_calls,
            "cache_hits": stage_row.cache_hits,
            "total_tokens": int(stage_row.tokens or 0),
            "total_cost": round(_float(stage_row.cost), 6),
            "avg_latency_ms": round(_float(stage_row.avg_latency), 1),
            "success_rate": _pct(stage_row.completed, finished_stages),
            "failure_rate": _pct(stage_row.failed, finished_stages),
        }

    async def get_stage_type_metrics(self, flt: Optional[AnalyticsFilter] = None) -> list[dict]:
        """Metrics per stage type (stage runs joined to their stage)."""
        flt = flt or AnalyticsFilter()
        stage_type = func.coalesce(Stage.stage_type, "untyped").label("stage_type")
        rows = (await self.db.execute(
            select(
                stage_type,
                func.count(ExecutionRecord.id).label("runs"),
                _count_if(ExecutionRecord.status == "completed").label("completed"),
                _count_if(ExecutionRecord.status == "failed").label("failed"),
                _count_if(ExecutionRecord.cache_hit.is_(True)).label("cache_hits"),
                func.avg(case((_IS_LLM_CALL, ExecutionRecord.latency_ms))).label("avg_latency"),
                func.sum(_TOKENS).label("tokens"),
                func.sum(ExecutionRecord.estimated_cost).label("cost"),
            )
            .join(Stage, Stage.id == ExecutionRecord.stage_id)
            .where(*flt.conditions())
            .group_by(stage_type)
            .order_by(func.count(ExecutionRecord.id).desc(), stage_type)
        )).all()
        return [
            {
                "stage_type": r.stage_type,
                "runs": r.runs,
                "completed": r.completed,
                "failed": r.failed,
                "cache_hits": r.cache_hits,
                "cache_hit_rate": _pct(r.cache_hits, r.runs),
                "avg_latency_ms": round(_float(r.avg_latency), 1),
                "total_tokens": int(r.tokens or 0),
                "total_cost": round(_float(r.cost), 6),
            }
            for r in rows
        ]

    async def get_model_utilization(self, flt: Optional[AnalyticsFilter] = None) -> list[dict]:
        """LLM calls per provider/model (cache hits excluded: no model was called)."""
        flt = flt or AnalyticsFilter()
        rows = (await self.db.execute(
            select(
                ExecutionRecord.provider,
                ExecutionRecord.model_used,
                func.count(ExecutionRecord.id).label("calls"),
                func.sum(_TOKENS).label("tokens"),
                func.sum(ExecutionRecord.estimated_cost).label("cost"),
                func.avg(ExecutionRecord.latency_ms).label("avg_latency"),
            )
            .where(_IS_LLM_CALL, ExecutionRecord.model_used.isnot(None), *flt.conditions())
            .group_by(ExecutionRecord.provider, ExecutionRecord.model_used)
            .order_by(func.count(ExecutionRecord.id).desc(), ExecutionRecord.model_used)
        )).all()
        total_calls = sum(r.calls for r in rows)
        return [
            {
                "provider": r.provider or "unknown",
                "model": r.model_used,
                "usage_count": r.calls,
                "share": _pct(r.calls, total_calls),
                "total_tokens": int(r.tokens or 0),
                "total_cost": round(_float(r.cost), 6),
                "avg_latency_ms": round(_float(r.avg_latency), 1),
            }
            for r in rows
        ]

    async def get_cache_metrics(self, flt: Optional[AnalyticsFilter] = None) -> dict:
        """
        Hit rate and savings from stage runs in the slice (hits / (hits + LLM calls)),
        plus the current number of valid cache entries.
        """
        flt = flt or AnalyticsFilter()
        row = (await self.db.execute(
            select(
                _count_if(ExecutionRecord.cache_hit.is_(True)).label("hits"),
                _count_if(_IS_LLM_CALL).label("misses"),
                func.sum(case((ExecutionRecord.cache_hit.is_(True), _TOKENS_SAVED))).label("tokens_saved"),
                func.sum(case((ExecutionRecord.cache_hit.is_(True), _COST_SAVED))).label("cost_saved"),
            ).where(*flt.conditions())
        )).one()

        entries_query = select(func.count(CacheEntry.id)).where(CacheEntry.is_valid.is_(True))
        if flt.workflow_id:
            entries_query = entries_query.where(CacheEntry.workflow_id == flt.workflow_id)
        valid_entries = await self.db.scalar(entries_query) or 0

        lookups = row.hits + row.misses
        return {
            "valid_entries": valid_entries,
            "total_hits": row.hits,
            "total_misses": row.misses,
            "hit_rate": _pct(row.hits, lookups),
            "total_tokens_saved": int(row.tokens_saved or 0),
            "total_cost_saved": round(_float(row.cost_saved), 6),
        }

    async def get_latency_metrics(self, flt: Optional[AnalyticsFilter] = None) -> dict:
        """Latency distribution of LLM calls: real percentiles via percentile_cont."""
        flt = flt or AnalyticsFilter()
        latency = ExecutionRecord.latency_ms
        pct_cols = [
            func.percentile_cont(p).within_group(latency.asc()).label(f"p{int(p * 100)}")
            for p in PERCENTILES
        ]
        row = (await self.db.execute(
            select(func.count(latency).label("count"), func.min(latency).label("min"),
                   func.max(latency).label("max"), func.avg(latency).label("avg"), *pct_cols)
            .where(_IS_LLM_CALL, latency.isnot(None), *flt.conditions())
        )).one()
        result = {
            "sample_count": row.count,
            "min_ms": _float(row.min),
            "max_ms": _float(row.max),
            "avg_ms": round(_float(row.avg), 1),
        }
        for p in PERCENTILES:
            key = f"p{int(p * 100)}"
            result[key] = round(_float(getattr(row, key)), 1)
        return result

    # ---------- trends ----------

    def _trend_range(self, flt: AnalyticsFilter, days: Optional[int]) -> tuple[date, date]:
        end = (flt.end_date or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
        if flt.start_date:
            start = flt.start_date.astimezone(timezone.utc).date()
        else:
            start = end - timedelta(days=(days or DEFAULT_TREND_DAYS) - 1)
        if (end - start).days >= MAX_TREND_DAYS:
            start = end - timedelta(days=MAX_TREND_DAYS - 1)
        return start, end

    async def _daily(self, flt: AnalyticsFilter, days: Optional[int], *columns) -> tuple[list[date], dict]:
        """Run a per-UTC-day aggregate over [start, end]; returns (all days, {day: row})."""
        start, end = self._trend_range(flt, days)
        day = func.date(func.timezone("UTC", ExecutionRecord.created_at)).label("day")
        conds = AnalyticsFilter(workflow_id=flt.workflow_id).conditions()  # dates handled by the day range
        rows = (await self.db.execute(
            select(day, *columns)
            .where(day >= start, day <= end, *conds)
            .group_by(day)
        )).all()
        all_days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        return all_days, {r.day: r for r in rows}

    async def get_cost_trend(self, flt: Optional[AnalyticsFilter] = None, days: Optional[int] = None) -> list[dict]:
        """Daily cost, executions and LLM calls; days without activity are zero (not missing)."""
        flt = flt or AnalyticsFilter()
        all_days, by_day = await self._daily(
            flt, days,
            func.sum(ExecutionRecord.estimated_cost).label("cost"),
            func.count(ExecutionRecord.execution_id.distinct()).label("executions"),
            _count_if(_IS_LLM_CALL).label("llm_calls"),
            _count_if(ExecutionRecord.cache_hit.is_(True)).label("cache_hits"),
        )
        return [
            {
                "date": d.isoformat(),
                "cost": round(_float(getattr(by_day.get(d), "cost", 0)), 6),
                "executions": getattr(by_day.get(d), "executions", 0),
                "llm_calls": getattr(by_day.get(d), "llm_calls", 0),
                "cache_hits": getattr(by_day.get(d), "cache_hits", 0),
            }
            for d in all_days
        ]

    async def get_token_usage_trend(self, flt: Optional[AnalyticsFilter] = None, days: Optional[int] = None) -> list[dict]:
        flt = flt or AnalyticsFilter()
        all_days, by_day = await self._daily(
            flt, days,
            func.sum(func.coalesce(ExecutionRecord.input_tokens, 0)).label("input_tokens"),
            func.sum(func.coalesce(ExecutionRecord.output_tokens, 0)).label("output_tokens"),
        )
        points = []
        for d in all_days:
            row = by_day.get(d)
            inp = int(getattr(row, "input_tokens", 0) or 0)
            out = int(getattr(row, "output_tokens", 0) or 0)
            points.append({"date": d.isoformat(), "input_tokens": inp, "output_tokens": out, "total_tokens": inp + out})
        return points

    # ---------- routing ----------

    async def get_routing_effectiveness(self, flt: Optional[AnalyticsFilter] = None) -> dict:
        flt = flt or AnalyticsFilter()
        conds = []
        if flt.start_date:
            conds.append(RoutingDecision.created_at >= flt.start_date)
        if flt.end_date:
            conds.append(RoutingDecision.created_at <= flt.end_date)
        if flt.workflow_id:
            conds.append(Stage.workflow_id == flt.workflow_id)

        base = select(
            func.count(RoutingDecision.id).label("total"),
            _count_if(RoutingDecision.was_user_override.is_(True)).label("overrides"),
            _count_if(RoutingDecision.was_fallback.is_(True)).label("fallbacks"),
        ).select_from(RoutingDecision)
        if flt.workflow_id:
            base = base.join(Stage, Stage.id == RoutingDecision.stage_id)
        row = (await self.db.execute(base.where(*conds))).one()

        def grouped(column):
            q = select(column, func.count(RoutingDecision.id).label("n")).select_from(RoutingDecision)
            if flt.workflow_id:
                q = q.join(Stage, Stage.id == RoutingDecision.stage_id)
            return q.where(column.isnot(None), *conds).group_by(column).order_by(literal_column("n").desc())

        priorities = (await self.db.execute(grouped(RoutingDecision.priority_factor))).all()
        models = (await self.db.execute(grouped(RoutingDecision.selected_model_name).limit(8))).all()
        return {
            "total_decisions": row.total,
            "override_count": row.overrides,
            "override_rate": _pct(row.overrides, row.total),
            "fallback_count": row.fallbacks,
            "fallback_rate": _pct(row.fallbacks, row.total),
            "priority_distribution": {p: n for p, n in priorities},
            "top_models": [{"model": m, "decisions": n} for m, n in models],
        }

    # ---------- one execution ----------

    async def get_execution_timeline(self, execution_id: uuid.UUID) -> Optional[dict]:
        """Stage runs of one execution with offsets from its start, for a Gantt chart."""
        rows = (await self.db.execute(
            select(ExecutionRecord, Stage.name, Stage.stage_order, Stage.stage_type)
            .outerjoin(Stage, Stage.id == ExecutionRecord.stage_id)
            .where(ExecutionRecord.execution_id == execution_id)
            .order_by(ExecutionRecord.started_at, Stage.stage_order)
        )).all()
        if not rows:
            return None

        starts = [r.ExecutionRecord.started_at for r in rows if r.ExecutionRecord.started_at]
        ends = [r.ExecutionRecord.completed_at for r in rows if r.ExecutionRecord.completed_at]
        t0 = min(starts) if starts else None
        t1 = max(ends) if ends else None

        def offset(ts) -> Optional[int]:
            return int((ts - t0).total_seconds() * 1000) if ts and t0 else None

        stages = []
        for r in rows:
            rec = r.ExecutionRecord
            start_ms, end_ms = offset(rec.started_at), offset(rec.completed_at)
            stages.append({
                "stage_id": str(rec.stage_id) if rec.stage_id else None,
                "stage_name": r.name or "Unknown",
                "stage_order": r.stage_order if r.stage_order is not None else 0,
                "stage_type": r.stage_type,
                "status": rec.status,
                "cache_hit": rec.cache_hit,
                "model_used": rec.model_used,
                "provider": rec.provider,
                "started_at": rec.started_at.isoformat() if rec.started_at else None,
                "completed_at": rec.completed_at.isoformat() if rec.completed_at else None,
                "start_offset_ms": start_ms,
                "end_offset_ms": end_ms,
                "duration_ms": end_ms - start_ms if start_ms is not None and end_ms is not None else None,
                "latency_ms": rec.latency_ms,
                "estimated_cost": float(rec.estimated_cost or 0),
            })

        total_ms = int((t1 - t0).total_seconds() * 1000) if t0 and t1 else 0
        busy_ms = sum(s["duration_ms"] or 0 for s in stages)
        return {
            "execution_id": str(execution_id),
            "workflow_id": str(rows[0].ExecutionRecord.workflow_id),
            "started_at": t0.isoformat() if t0 else None,
            "completed_at": t1.isoformat() if t1 else None,
            "total_duration_ms": total_ms,
            # Sum of stage durations / wall-clock: >1 means stages overlapped (parallel speedup)
            "parallelism": round(busy_ms / total_ms, 2) if total_ms else 1.0,
            "stages": stages,
        }

    # ---------- raw rows (export) ----------

    async def get_stage_runs(self, flt: Optional[AnalyticsFilter] = None, limit: int = 10000) -> list[dict]:
        flt = flt or AnalyticsFilter()
        rows = (await self.db.execute(
            select(ExecutionRecord, Stage.name, Stage.stage_type)
            .outerjoin(Stage, Stage.id == ExecutionRecord.stage_id)
            .where(*flt.conditions())
            .order_by(ExecutionRecord.created_at.desc())
            .limit(limit)
        )).all()
        return [
            {
                "execution_id": str(r.ExecutionRecord.execution_id),
                "workflow_id": str(r.ExecutionRecord.workflow_id),
                "stage_id": str(r.ExecutionRecord.stage_id) if r.ExecutionRecord.stage_id else "",
                "stage_name": r.name or "",
                "stage_type": r.stage_type or "",
                "status": r.ExecutionRecord.status,
                "cache_hit": r.ExecutionRecord.cache_hit,
                "provider": r.ExecutionRecord.provider or "",
                "model_used": r.ExecutionRecord.model_used or "",
                "input_tokens": r.ExecutionRecord.input_tokens or 0,
                "output_tokens": r.ExecutionRecord.output_tokens or 0,
                "latency_ms": r.ExecutionRecord.latency_ms or 0,
                "estimated_cost": float(r.ExecutionRecord.estimated_cost or 0),
                "started_at": r.ExecutionRecord.started_at.isoformat() if r.ExecutionRecord.started_at else "",
                "completed_at": r.ExecutionRecord.completed_at.isoformat() if r.ExecutionRecord.completed_at else "",
                "error_message": r.ExecutionRecord.error_message or "",
            }
            for r in rows
        ]
