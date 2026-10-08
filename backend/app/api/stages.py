"""
Stage REST API endpoints.
All routes are prefixed with /api/stages (set in router include).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.stage import (
    StageCreate, StageUpdate, StageRead, StageReorder,
    StageDependencyCreate, StageDependencyRead,
)
from backend.app.schemas.common import MessageResponse
from backend.app.services.stage_manager import StageManager

router = APIRouter(prefix="/stages", tags=["Stages"])


@router.post("", response_model=StageRead, status_code=201)
async def create_stage(
    data: StageCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new stage in a workflow."""
    manager = StageManager(db)
    return await manager.create_stage(data)


@router.get("/workflow/{workflow_id}", response_model=list[StageRead])
async def list_stages(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all stages for a workflow."""
    manager = StageManager(db)
    return await manager.list_stages(workflow_id)


@router.get("/{stage_id}", response_model=StageRead)
async def get_stage(
    stage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single stage by ID."""
    manager = StageManager(db)
    return await manager.get_stage(stage_id)


@router.patch("/{stage_id}", response_model=StageRead)
async def update_stage(
    stage_id: uuid.UUID,
    data: StageUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a stage (partial update)."""
    manager = StageManager(db)
    return await manager.update_stage(stage_id, data)


@router.delete("/{stage_id}", response_model=MessageResponse)
async def delete_stage(
    stage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a stage."""
    manager = StageManager(db)
    await manager.delete_stage(stage_id)
    return MessageResponse(message=f"Stage {stage_id} deleted")


@router.put("/workflow/{workflow_id}/reorder", response_model=list[StageRead])
async def reorder_stages(
    workflow_id: uuid.UUID,
    data: StageReorder,
    db: AsyncSession = Depends(get_db),
):
    """Reorder stages within a workflow."""
    manager = StageManager(db)
    return await manager.reorder_stages(workflow_id, data)


@router.post("/{stage_id}/dependencies", response_model=StageDependencyRead, status_code=201)
async def add_dependency(
    stage_id: uuid.UUID,
    data: StageDependencyCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a dependency to a stage."""
    manager = StageManager(db)
    dep = await manager.add_dependency(stage_id, data)
    return dep


@router.delete("/dependencies/{dependency_id}", response_model=MessageResponse)
async def remove_dependency(
    dependency_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove a stage dependency."""
    manager = StageManager(db)
    await manager.remove_dependency(dependency_id)
    return MessageResponse(message=f"Dependency {dependency_id} removed")
