"""Pydantic schemas for workflow dependency graphs."""
import uuid
from typing import Optional

from pydantic import BaseModel


class DAGNodeResponse(BaseModel):
    stage_id: uuid.UUID
    name: str
    stage_order: int
    stage_type: Optional[str]
    level: int
    dependencies: list[uuid.UUID]
    is_merge_point: bool
    on_critical_path: bool


class DAGEdgeResponse(BaseModel):
    source: uuid.UUID
    target: uuid.UUID


class WorkflowDAGResponse(BaseModel):
    workflow_id: uuid.UUID
    nodes: list[DAGNodeResponse]
    edges: list[DAGEdgeResponse]
    levels: list[list[uuid.UUID]]
    critical_path: list[uuid.UUID]
    parallelism_factor: float
    max_width: int
    ascii: str
