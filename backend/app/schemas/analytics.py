"""
Pydantic schemas for analytics.
Rates are percentages (0-100); costs are USD; latencies and durations are milliseconds.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WorkflowMetrics(BaseModel):
    total_executions: int
    successful_executions: int
    execution_success_rate: float
    avg_execution_duration_ms: float
    total_stages: int
    completed_stages: int
    failed_stages: int
    cancelled_stages: int
    llm_calls: int
    cache_hits: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float
    success_rate: float   # completed / (completed + failed) stage runs
    failure_rate: float


class StageTypeMetrics(BaseModel):
    stage_type: str
    runs: int
    completed: int
    failed: int
    cache_hits: int
    cache_hit_rate: float
    avg_latency_ms: float
    total_tokens: int
    total_cost: float


class ModelUtilization(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: str
    model: str
    usage_count: int
    share: float
    total_tokens: int
    total_cost: float
    avg_latency_ms: float


class CacheMetrics(BaseModel):
    valid_entries: int
    total_hits: int
    total_misses: int
    hit_rate: float
    total_tokens_saved: int
    total_cost_saved: float


class LatencyMetrics(BaseModel):
    sample_count: int
    min_ms: float
    max_ms: float
    avg_ms: float
    p50: float
    p75: float
    p90: float
    p95: float
    p99: float


class CostTrendPoint(BaseModel):
    date: str
    cost: float
    executions: int
    llm_calls: int
    cache_hits: int


class TokenTrendPoint(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


class RoutingEffectiveness(BaseModel):
    total_decisions: int
    override_count: int
    override_rate: float
    fallback_count: int
    fallback_rate: float
    priority_distribution: dict[str, int]
    top_models: list[dict]


class TimelineStage(BaseModel):
    stage_id: Optional[str]
    stage_name: str
    stage_order: int
    stage_type: Optional[str]
    status: str
    cache_hit: bool
    model_used: Optional[str]
    provider: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    start_offset_ms: Optional[int]
    end_offset_ms: Optional[int]
    duration_ms: Optional[int]
    latency_ms: Optional[int]
    estimated_cost: float


class ExecutionTimeline(BaseModel):
    execution_id: str
    workflow_id: str
    started_at: Optional[str]
    completed_at: Optional[str]
    total_duration_ms: int
    parallelism: float
    stages: list[TimelineStage]
