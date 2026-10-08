"""Pydantic schemas for Stage and StageDependency CRUD operations."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StageDependencyCreate(BaseModel):
    """Schema for creating a stage dependency."""
    depends_on_stage_id: uuid.UUID
    dependency_type: str = Field(
        default="sequential",
        pattern="^(sequential|merge)$",
        examples=["sequential"],
    )


class StageDependencyRead(BaseModel):
    """Schema for reading a stage dependency."""
    id: uuid.UUID
    stage_id: uuid.UUID
    depends_on_stage_id: uuid.UUID
    dependency_type: str

    model_config = {"from_attributes": True}


class StageBase(BaseModel):
    """Shared stage fields."""
    name: str = Field(..., min_length=1, max_length=255, examples=["Requirement Analysis"])
    instruction: str = Field(
        ...,
        min_length=1,
        examples=["Analyze the project requirements and produce a structured requirements document."],
    )
    stage_order: int = Field(default=0, ge=0, examples=[1])
    stage_type: Optional[str] = Field(
        None,
        pattern="^(analysis|design|generation|testing|documentation|review|custom)$",
        examples=["analysis"],
    )
    model_preference: Optional[str] = Field(None, examples=["gpt-4o"])
    config: dict = Field(default_factory=dict)


class StageCreate(StageBase):
    """Schema for creating a new stage within a workflow."""
    workflow_id: uuid.UUID
    dependencies: list[StageDependencyCreate] = Field(default_factory=list)


class StageUpdate(BaseModel):
    """Schema for updating a stage. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    instruction: Optional[str] = Field(None, min_length=1)
    stage_order: Optional[int] = Field(None, ge=0)
    stage_type: Optional[str] = None
    model_preference: Optional[str] = None
    config: Optional[dict] = None
    status: Optional[str] = Field(None, pattern="^(pending|running|completed|failed|skipped|cached)$")


class StageRead(StageBase):
    """Full stage response with dependencies."""
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    dependencies: list[StageDependencyRead] = []

    model_config = {"from_attributes": True}


class StageReorder(BaseModel):
    """Schema for reordering stages."""
    stage_ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="Ordered list of stage IDs. The index becomes the new stage_order.",
    )
