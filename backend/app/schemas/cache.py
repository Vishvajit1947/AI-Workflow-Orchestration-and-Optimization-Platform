"""
Pydantic schemas for semantic cache operations.
"""
import uuid
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from pydantic import BaseModel, Field


class CacheEntryCreate(BaseModel):
    """Schema for creating a cache entry."""
    workflow_id: Optional[uuid.UUID] = None
    stage_id: Optional[uuid.UUID] = None
    stage_type: Optional[str] = None
    input_text: str
    input_embedding: List[float]
    result: str
    result_tokens: Optional[int] = None
    model_used: Optional[str] = None
    dependency_hash: Optional[str] = None
    similarity_threshold: Decimal = Field(default=Decimal("0.92"))
    expires_at: Optional[datetime] = None


class CacheEntryResponse(BaseModel):
    """Schema for cache entry response."""
    id: uuid.UUID
    workflow_id: Optional[uuid.UUID] = None
    stage_id: Optional[uuid.UUID] = None
    stage_type: Optional[str]
    input_text: str
    result: str
    result_tokens: Optional[int]
    model_used: Optional[str]
    hit_count: int
    similarity_score: Optional[float] = None  # Populated during similarity search
    is_valid: bool
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CacheHitResponse(BaseModel):
    """Response when a cache lookup is performed."""
    cache_hit: bool
    entry: Optional[CacheEntryResponse] = None
    similarity_score: Optional[float] = None
    tokens_saved: Optional[int] = None
    cost_saved: Optional[Decimal] = None


class CacheStats(BaseModel):
    """Cache performance statistics."""
    total_entries: int
    total_hits: int
    hit_rate: float
    total_tokens_saved: int
    total_cost_saved: Decimal
    avg_similarity_score: float
