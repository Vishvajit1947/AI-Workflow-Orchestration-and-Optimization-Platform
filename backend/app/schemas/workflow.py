"""Pydantic schemas for Workflow CRUD operations."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WorkflowBase(BaseModel):
    """Shared workflow fields."""
    name: str = Field(..., min_length=1, max_length=255, examples=["Software Development Workflow"])
    description: Optional[str] = Field(None, examples=["A multi-stage workflow for building software"])
    objective: Optional[str] = Field(None, examples=["Build an online course management system"])


class WorkflowCreate(WorkflowBase):
    """Schema for creating a new workflow."""
    pass


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    objective: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|running|completed|failed|paused)$")


class StageReadBrief(BaseModel):
    """Brief stage info for embedding in workflow responses."""
    id: uuid.UUID
    name: str
    stage_order: int
    stage_type: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


class WorkflowRead(WorkflowBase):
    """Full workflow response with stages."""
    id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    stages: list[StageReadBrief] = []

    model_config = {"from_attributes": True}


class WorkflowListItem(BaseModel):
    """Workflow item for list responses (without full stage details)."""
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    status: str
    stage_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
