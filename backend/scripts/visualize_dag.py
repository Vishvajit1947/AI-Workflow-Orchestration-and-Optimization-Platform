"""
Print a workflow's execution DAG: levels, dependencies, critical path.

Usage (from the repo root):  python -m backend.scripts.visualize_dag <workflow_id>
"""
import asyncio
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.database import async_session_factory
from backend.app.models.workflow import Workflow
from backend.app.services.execution.dag_analyzer import DAGAnalyzer


async def visualize_workflow_dag(workflow_id: str) -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(Workflow).options(selectinload(Workflow.stages)).where(Workflow.id == uuid.UUID(workflow_id))
        )
        workflow = result.scalar_one_or_none()
        if not workflow:
            print(f"Workflow {workflow_id} not found")
            return
        if not workflow.stages:
            print("Workflow has no stages")
            return
        print(f"\nWorkflow: {workflow.name}\nObjective: {workflow.objective}\n")
        print(DAGAnalyzer(workflow.stages).visualize_dag())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m backend.scripts.visualize_dag <workflow_id>")
        sys.exit(1)
    asyncio.run(visualize_workflow_dag(sys.argv[1]))
