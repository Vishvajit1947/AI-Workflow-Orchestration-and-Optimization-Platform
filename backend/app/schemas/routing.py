"""
Pydantic schemas for the model registry and routing (profiles, rules, decisions).
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PriorityFactor = Literal["cost", "speed", "quality", "balanced"]


class ModelProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    provider: str
    model_name: str
    display_name: str
    capabilities: dict[str, float]
    max_context_tokens: int
    max_output_tokens: Optional[int]
    cost_per_input_token: Decimal
    cost_per_output_token: Decimal
    avg_latency_ms: Optional[int]
    is_available: bool
    supports_streaming: bool
    supports_function_calling: bool
    description: Optional[str]
    strengths: list[str]
    limitations: list[str]
    created_at: datetime
    routable: bool = Field(default=False, description="Available and its provider has an API key configured")


class ModelProfileUpdate(BaseModel):
    """Editable fields of a model profile."""
    model_config = ConfigDict(protected_namespaces=())

    display_name: Optional[str] = None
    capabilities: Optional[dict[str, float]] = None
    avg_latency_ms: Optional[int] = Field(default=None, ge=0)
    is_available: Optional[bool] = None
    description: Optional[str] = None


class ModelComparisonResponse(BaseModel):
    models: list[ModelProfileResponse]
    cheapest: Optional[str] = None  # model_name
    fastest: Optional[str] = None  # model_name
    most_capable: dict[str, str] = Field(default_factory=dict)  # capability -> model_name


class ModelRef(BaseModel):
    """Short reference to a model profile."""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    provider: str
    model_name: str
    display_name: str


class RoutingRuleBase(BaseModel):
    priority_factor: PriorityFactor = "balanced"
    max_cost_per_call: Optional[Decimal] = Field(default=None, ge=0, description="Max USD for a typical 1K-in/500-out call")
    max_latency_ms: Optional[int] = Field(default=None, gt=0)
    min_capability_score: Decimal = Field(default=Decimal("0.80"), ge=0, le=1)
    preferred_model_id: Optional[uuid.UUID] = None
    fallback_model_id: Optional[uuid.UUID] = None
    is_active: bool = True


class RoutingRuleCreate(RoutingRuleBase):
    stage_type: str = Field(..., min_length=1, max_length=100)


class RoutingRuleUpdate(BaseModel):
    """Partial update; send null to clear a nullable field."""
    priority_factor: Optional[PriorityFactor] = None
    max_cost_per_call: Optional[Decimal] = Field(default=None, ge=0)
    max_latency_ms: Optional[int] = Field(default=None, gt=0)
    min_capability_score: Optional[Decimal] = Field(default=None, ge=0, le=1)
    preferred_model_id: Optional[uuid.UUID] = None
    fallback_model_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class RoutingRuleResponse(RoutingRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage_type: str
    preferred_model: Optional[ModelRef] = None
    fallback_model: Optional[ModelRef] = None
    created_at: datetime
    updated_at: datetime


class RoutingDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    execution_id: uuid.UUID
    stage_id: uuid.UUID
    stage_type: Optional[str]
    selected_model_id: Optional[uuid.UUID]
    selected_provider: str
    selected_model_name: str
    selection_reason: Optional[str]
    priority_factor: Optional[str]
    alternatives_considered: list[dict]
    was_user_override: bool
    was_fallback: bool
    created_at: datetime


class RoutingPreviewItem(BaseModel):
    """What the router would pick for a stage right now (nothing is logged)."""
    stage_id: uuid.UUID
    stage_name: str
    stage_type: Optional[str]
    provider: Optional[str]
    model_name: Optional[str]
    reason: str
