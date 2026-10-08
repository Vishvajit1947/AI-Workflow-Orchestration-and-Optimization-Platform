"""Background executions: run a workflow in its own session and task, outside the request."""
import asyncio
import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.models.workflow import Workflow
from backend.app.services.execution.execution_engine import ExecutionEngine
from backend.app.services.execution.tracker import tracker


async def _run(session_factory: async_sessionmaker, workflow_id: uuid.UUID,
               execution_id: uuid.UUID, options: dict) -> None:
    async with session_factory() as db:
        try:
            await ExecutionEngine(db).execute_workflow(
                workflow_id, execution_id=execution_id, commit_progress=True, **options
            )
            await db.commit()
        except Exception as e:
            print(f"[EXECUTION] Background execution {execution_id} crashed: {e!r}")
            await db.rollback()
            await db.execute(update(Workflow).where(Workflow.id == workflow_id).values(status="failed"))
            await db.commit()
            await tracker.set_status(execution_id, "failed", error=str(e))


def start_background_execution(session_factory: async_sessionmaker, workflow: Workflow,
                               options: dict) -> uuid.UUID:
    """Register the execution with the tracker and start it; returns the execution_id at once."""
    execution_id = uuid.uuid4()
    live = tracker.register(execution_id, workflow.id, workflow.name)
    # Keep a reference on the live record so the task isn't garbage-collected mid-run
    live.task = asyncio.create_task(_run(session_factory, workflow.id, execution_id, options))
    return execution_id


async def fail_interrupted_workflows(db: AsyncSession) -> int:
    """At startup: executions die with the process, so no workflow can still be running/paused."""
    result = await db.execute(
        update(Workflow).where(Workflow.status.in_(("running", "paused"))).values(status="failed")
    )
    await db.commit()
    return result.rowcount
