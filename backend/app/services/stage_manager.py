"""
Stage Manager — business logic for stage CRUD and dependency management.
"""

import uuid
from typing import Optional

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from backend.app.models.stage import Stage, StageDependency
from backend.app.models.workflow import Workflow
from backend.app.schemas.stage import (
    StageCreate, StageUpdate, StageReorder, StageDependencyCreate,
)


class StageManager:
    """Handles all stage-level business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_workflow_or_404(self, workflow_id: uuid.UUID) -> Workflow:
        """Fetch workflow or raise 404."""
        result = await self.db.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
        return workflow

    async def _get_stage_or_404(self, stage_id: uuid.UUID) -> Stage:
        """Fetch stage with dependencies or raise 404."""
        result = await self.db.execute(
            select(Stage)
            .options(selectinload(Stage.dependencies))
            .where(Stage.id == stage_id)
        )
        stage = result.scalar_one_or_none()
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_id} not found")
        return stage

    async def create_stage(self, data: StageCreate) -> Stage:
        """Create a new stage in a workflow."""
        await self._get_workflow_or_404(data.workflow_id)

        stage = Stage(
            workflow_id=data.workflow_id,
            name=data.name,
            instruction=data.instruction,
            stage_order=data.stage_order,
            stage_type=data.stage_type,
            model_preference=data.model_preference,
            config=data.config,
        )
        self.db.add(stage)
        await self.db.commit()
        await self.db.refresh(stage)

        # Add dependencies if provided
        for dep in data.dependencies:
            await self._add_dependency(stage.id, dep)

        await self.db.refresh(stage, attribute_names=["dependencies"])
        return stage

    async def get_stage(self, stage_id: uuid.UUID) -> Stage:
        """Get a stage by ID."""
        return await self._get_stage_or_404(stage_id)

    async def list_stages(self, workflow_id: uuid.UUID) -> list[Stage]:
        """List all stages for a workflow, ordered by stage_order."""
        await self._get_workflow_or_404(workflow_id)
        result = await self.db.execute(
            select(Stage)
            .options(selectinload(Stage.dependencies))
            .where(Stage.workflow_id == workflow_id)
            .order_by(Stage.stage_order)
        )
        return list(result.scalars().all())

    async def update_stage(self, stage_id: uuid.UUID, data: StageUpdate) -> Stage:
        """Update a stage (partial)."""
        stage = await self._get_stage_or_404(stage_id)
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        for field, value in update_data.items():
            setattr(stage, field, value)
        await self.db.commit()
        return await self.get_stage(stage_id)

    async def delete_stage(self, stage_id: uuid.UUID) -> None:
        """Delete a stage. Also removes all dependencies referencing it."""
        stage = await self._get_stage_or_404(stage_id)
        await self.db.delete(stage)
        await self.db.commit()

    async def reorder_stages(self, workflow_id: uuid.UUID, data: StageReorder) -> list[Stage]:
        """Reorder stages by setting stage_order based on position in the list."""
        await self._get_workflow_or_404(workflow_id)
        for index, stage_id in enumerate(data.stage_ids):
            await self.db.execute(
                update(Stage)
                .where(Stage.id == stage_id, Stage.workflow_id == workflow_id)
                .values(stage_order=index)
            )
        await self.db.commit()
        return await self.list_stages(workflow_id)

    async def _add_dependency(
        self, stage_id: uuid.UUID, dep: StageDependencyCreate
    ) -> StageDependency:
        """Add a dependency to a stage."""
        # Verify the depends_on stage exists
        await self._get_stage_or_404(dep.depends_on_stage_id)

        # Prevent self-dependency
        if stage_id == dep.depends_on_stage_id:
            raise HTTPException(status_code=400, detail="A stage cannot depend on itself")

        # Check if already exists
        existing = await self.db.execute(
            select(StageDependency).where(
                StageDependency.stage_id == stage_id,
                StageDependency.depends_on_stage_id == dep.depends_on_stage_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Dependency already exists")

        dependency = StageDependency(
            stage_id=stage_id,
            depends_on_stage_id=dep.depends_on_stage_id,
            dependency_type=dep.dependency_type,
        )
        self.db.add(dependency)
        await self.db.commit()
        return dependency

    async def add_dependency(
        self, stage_id: uuid.UUID, dep: StageDependencyCreate
    ) -> StageDependency:
        """Add a dependency with cycle detection."""
        stage = await self._get_stage_or_404(stage_id)

        # Import cycle detection
        from backend.app.utils.validators import would_create_cycle

        # Check for cycles
        if await would_create_cycle(self.db, stage.workflow_id, stage_id, dep.depends_on_stage_id):
            raise HTTPException(
                status_code=400,
                detail="Adding this dependency would create a circular dependency cycle."
            )

        return await self._add_dependency(stage_id, dep)

    async def remove_dependency(self, dependency_id: uuid.UUID) -> None:
        """Remove a dependency by its ID."""
        result = await self.db.execute(
            select(StageDependency).where(StageDependency.id == dependency_id)
        )
        dep = result.scalar_one_or_none()
        if not dep:
            raise HTTPException(status_code=404, detail=f"Dependency {dependency_id} not found")
        await self.db.delete(dep)
        await self.db.commit()
