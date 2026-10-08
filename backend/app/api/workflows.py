"""
Workflow REST API endpoints.
All routes are prefixed with /api/workflows (set in router include).
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowRead, WorkflowListItem,
)
from backend.app.schemas.common import PaginatedResponse, MessageResponse
from backend.app.services.workflow_manager import WorkflowManager
from backend.app.utils.validators import validate_workflow as run_validation

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.post("", response_model=WorkflowRead, status_code=201)
async def create_workflow(
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new workflow."""
    manager = WorkflowManager(db)
    workflow = await manager.create_workflow(data)
    return workflow


@router.get("", response_model=PaginatedResponse[WorkflowListItem])
async def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all workflows with pagination."""
    manager = WorkflowManager(db)
    workflows, total = await manager.list_workflows(skip, limit, status)
    items = []
    for w in workflows:
        items.append(WorkflowListItem(
            id=w.id,
            name=w.name,
            description=w.description,
            status=w.status,
            stage_count=len(w.stages) if w.stages else 0,
            created_at=w.created_at,
            updated_at=w.updated_at,
        ))
    return PaginatedResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        has_more=(skip + limit) < total,
    )


@router.get("/{workflow_id}", response_model=WorkflowRead)
async def get_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single workflow by ID with its stages."""
    manager = WorkflowManager(db)
    return await manager.get_workflow(workflow_id)


@router.patch("/{workflow_id}", response_model=WorkflowRead)
async def update_workflow(
    workflow_id: uuid.UUID,
    data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a workflow (partial update)."""
    manager = WorkflowManager(db)
    return await manager.update_workflow(workflow_id, data)


@router.delete("/{workflow_id}", response_model=MessageResponse)
async def delete_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a workflow and all its stages."""
    manager = WorkflowManager(db)
    await manager.delete_workflow(workflow_id)
    return MessageResponse(message=f"Workflow {workflow_id} deleted")


@router.post("/{workflow_id}/validate")
async def validate_workflow(
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Validate a workflow's structure (stages, dependencies, cycles)."""
    # Verify workflow exists
    manager = WorkflowManager(db)
    await manager.get_workflow(workflow_id)

    errors = await run_validation(db, workflow_id)
    return {
        "workflow_id": str(workflow_id),
        "is_valid": len(errors) == 0,
        "errors": errors,
    }
