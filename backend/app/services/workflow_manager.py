"""
Workflow Manager — business logic for workflow CRUD operations.
"""

import uuid
from typing import Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from backend.app.models.workflow import Workflow
from backend.app.models.stage import Stage
from backend.app.schemas.workflow import WorkflowCreate, WorkflowUpdate


class WorkflowManager:
    """
    Handles all workflow-level business logic for one user.

    Every query is scoped to `owner_id`: workflows of other users (and unowned legacy
    workflows) behave exactly like workflows that do not exist (404).
    """

    def __init__(self, db: AsyncSession, owner_id: uuid.UUID):
        self.db = db
        self.owner_id = owner_id

    async def create_workflow(self, data: WorkflowCreate) -> Workflow:
        """Create a new workflow."""
        workflow = Workflow(
            name=data.name,
            description=data.description,
            objective=data.objective,
            user_id=self.owner_id,
        )
        self.db.add(workflow)
        await self.db.commit()
        return await self.get_workflow(workflow.id)

    async def get_workflow(self, workflow_id: uuid.UUID) -> Workflow:
        """Get a workflow by ID with its stages."""
        stmt = (
            select(Workflow)
            .options(selectinload(Workflow.stages))
            .where(Workflow.id == workflow_id, Workflow.user_id == self.owner_id)
            # Refresh an already-loaded workflow: stages created in this session since it was
            # loaded would otherwise be missing from workflow.stages
            .execution_options(populate_existing=True)
        )
        result = await self.db.execute(stmt)
        workflow = result.scalar_one_or_none()
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found",
            )
        return workflow

    async def list_workflows(
        self, skip: int = 0, limit: int = 20, status_filter: Optional[str] = None
    ) -> tuple[list[Workflow], int]:
        """List workflows with pagination. Returns (items, total_count)."""
        query = select(Workflow).where(Workflow.user_id == self.owner_id)
        count_query = select(func.count(Workflow.id)).where(Workflow.user_id == self.owner_id)

        if status_filter:
            query = query.where(Workflow.status == status_filter)
            count_query = count_query.where(Workflow.status == status_filter)

        # Get total count
        total = (await self.db.execute(count_query)).scalar() or 0

        # Get paginated results
        query = (
            query
            .options(selectinload(Workflow.stages))
            .order_by(Workflow.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        workflows = list(result.scalars().all())

        return workflows, total

    async def update_workflow(
        self, workflow_id: uuid.UUID, data: WorkflowUpdate
    ) -> Workflow:
        """Update a workflow's fields (partial update)."""
        workflow = await self.get_workflow(workflow_id)
        update_data = data.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update",
            )

        for field, value in update_data.items():
            setattr(workflow, field, value)

        await self.db.commit()
        return await self.get_workflow(workflow_id)

    async def delete_workflow(self, workflow_id: uuid.UUID) -> None:
        """Delete a workflow and all its stages (cascade)."""
        workflow = await self.get_workflow(workflow_id)
        await self.db.delete(workflow)
        await self.db.commit()
