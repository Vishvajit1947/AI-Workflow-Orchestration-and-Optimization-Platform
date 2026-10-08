"""
Pydantic schemas for execution operations.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# Request schemas
class ExecutionStartRequest(BaseModel):
    """Request to start workflow execution."""
    default_provider: Optional[str] = Field(default="gemini", description="Default LLM provider")
    default_model: Optional[str] = Field(default=None, description="Default model name")
    user_inputs: Optional[dict] = Field(default_factory=dict, description="Additional user inputs")
    use_cache: bool = Field(default=True, description="Serve stages from the semantic cache when possible; false forces fresh LLM calls")
    use_routing: bool = Field(default=True, description="Let the routing engine pick each stage's model; false always uses the default provider/model")
    routing_preferences: dict[str, str] = Field(
        default_factory=dict,
        description="Per-stage model overrides for this execution: {stage_id: model_name}",
    )
    parallel: bool = Field(default=True, description="Run independent stages concurrently; false runs one stage at a time")
    background: bool = Field(
        default=False,
        description="Return immediately with status 'running' and execute in the background "
                    "(follow it via /executions/{id}/status or the WebSocket)",
    )


# Response schemas
class StageExecutionDetail(BaseModel):
    """Details of a single stage execution."""
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    stage_id: uuid.UUID
    stage_name: str
    stage_order: int
    model_used: Optional[str]
    provider: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: int
    latency_ms: Optional[int]
    estimated_cost: Optional[Decimal]
    status: str
    result: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    cache_hit: bool = Field(default=False, description="Whether result was served from cache")
    cache_similarity: Optional[float] = Field(default=None, description="Similarity of the matched cache entry (cache hits only)")
    tokens_saved: Optional[int] = Field(default=None, description="Tokens the cache hit avoided (cache hits only)")
    cost_saved: Optional[Decimal] = Field(default=None, description="Estimated cost the cache hit avoided (cache hits only)")
    was_routed: bool = Field(default=False, description="Model was chosen by the routing engine")
    routing_reason: Optional[str] = Field(default=None, description="Why this model was chosen")
    was_user_override: bool = Field(default=False, description="Model came from a per-execution user override")
    was_fallback: bool = Field(default=False, description="Routing fell back because no candidate met the rule")
    retry_count: int = Field(default=0, description="Failed LLM attempts before the result (or final failure)")
    fallback_from: Optional[str] = Field(default=None, description="provider/model that failed before the fallback model answered")


class ExecutionSummary(BaseModel):
    """Summary of a workflow execution."""
    execution_id: uuid.UUID
    workflow_id: uuid.UUID
    workflow_name: str
    status: str
    total_stages: int
    completed_stages: int
    failed_stages: int
    total_tokens: int
    total_cost: Decimal
    total_latency_ms: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]


class ExecutionDetailResponse(BaseModel):
    """Full execution details with all stages."""
    summary: ExecutionSummary
    stages: list[StageExecutionDetail]


class ExecutionStartResponse(BaseModel):
    """Response after starting execution."""
    execution_id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    message: str
    started_at: datetime


class ExecutionListItem(BaseModel):
    """Item in execution list."""
    model_config = ConfigDict(from_attributes=True)
    
    execution_id: uuid.UUID
    workflow_id: uuid.UUID
    workflow_name: str
    status: str
    total_stages: int
    completed_stages: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    total_cost: Decimal


class LiveStageStatus(BaseModel):
    stage_id: uuid.UUID
    name: str
    stage_order: int
    stage_type: Optional[str]
    level: int
    status: str  # pending, running, completed, failed, skipped, cancelled
    provider: Optional[str] = None
    model: Optional[str] = None
    cache_hit: bool = False
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ExecutionStatusResponse(BaseModel):
    """Live state of an execution (also sent as the WebSocket 'snapshot' message)."""
    execution_id: uuid.UUID
    workflow_id: uuid.UUID
    workflow_name: str
    status: str  # queued, running, paused, completed, failed, cancelled
    parallel: bool
    progress: float
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stages: list[LiveStageStatus]
    dag: Optional[dict] = None


class ExecutionControlResponse(BaseModel):
    execution_id: uuid.UUID
    status: str
    message: str
