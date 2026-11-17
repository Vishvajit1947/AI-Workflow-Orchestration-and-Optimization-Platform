"""
Resource ownership checks.

Ownership is recorded on workflows (workflows.user_id). Every other user-owned
resource is reached through its workflow:

    stage            -> stage.workflow_id
    execution        -> execution_records.workflow_id  (or the live tracker entry)
    artifact / ZIP   -> execution record -> workflow
    cache entry      -> cache_entries.workflow_id
    routing decision -> stage -> workflow

Policy: a resource that does not exist and a resource owned by someone else get the
same 404, so IDs cannot be probed. Workflows with no owner (created before ownership
existed) match no user and are therefore never returned.
"""
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.execution import ExecutionRecord
from backend.app.models.stage import Stage
from backend.app.models.workflow import Workflow


def not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} not found")


def owned_workflow_ids(user_id: uuid.UUID) -> Select:
    """Subquery of the IDs of workflows owned by `user_id`, for `column.in_(...)` filters."""
    return select(Workflow.id).where(Workflow.user_id == user_id)


async def get_owned_workflow(
    db: AsyncSession, workflow_id: uuid.UUID, user_id: uuid.UUID, *options
) -> Workflow:
    """The workflow if `user_id` owns it, else 404."""
    stmt = select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    if options:
        stmt = stmt.options(*options)
    workflow = (await db.execute(stmt)).scalar_one_or_none()
    if workflow is None:
        raise not_found("Workflow")
    return workflow


async def get_owned_stage(db: AsyncSession, stage_id: uuid.UUID, user_id: uuid.UUID, *options) -> Stage:
    """The stage if its workflow is owned by `user_id`, else 404."""
    stmt = (
        select(Stage)
        .join(Workflow, Workflow.id == Stage.workflow_id)
        .where(Stage.id == stage_id, Workflow.user_id == user_id)
    )
    if options:
        stmt = stmt.options(*options)
    stage = (await db.execute(stmt)).scalar_one_or_none()
    if stage is None:
        raise not_found("Stage")
    return stage


async def execution_workflow_id(db: AsyncSession, execution_id: uuid.UUID) -> Optional[uuid.UUID]:
    """The workflow an execution ran, from its stored records or (while running) the live tracker."""
    workflow_id = (await db.execute(
        select(ExecutionRecord.workflow_id).where(ExecutionRecord.execution_id == execution_id).limit(1)
    )).scalar_one_or_none()
    if workflow_id is None:
        from backend.app.services.execution.tracker import tracker  # avoid import cycle at module load
        live = tracker.get(execution_id)
        workflow_id = live.workflow_id if live is not None else None
    return workflow_id


async def require_owned_execution(db: AsyncSession, execution_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
    """404 unless the execution belongs to a workflow owned by `user_id`; returns that workflow's ID."""
    workflow_id = await execution_workflow_id(db, execution_id)
    if workflow_id is None:
        raise not_found("Execution")
    owned = (await db.execute(
        select(Workflow.id).where(Workflow.id == workflow_id, Workflow.user_id == user_id)
    )).scalar_one_or_none()
    if owned is None:
        raise not_found("Execution")
    return workflow_id
