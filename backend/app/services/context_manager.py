"""
Context Manager — manages workflow context (stage outputs) and selects relevant context for each stage.
Key design: do NOT send the full history to every LLM call. Select only relevant context.
"""
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.context import WorkflowContext
from backend.app.models.stage import Stage, StageDependency

class ContextManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_context(self, workflow_id: uuid.UUID, execution_id: uuid.UUID,
                          stage_id: uuid.UUID, content: str, context_type: str = "stage_output",
                          token_count: int | None = None) -> WorkflowContext:
        ctx = WorkflowContext(
            workflow_id=workflow_id, execution_id=execution_id,
            stage_id=stage_id, content=content, context_type=context_type,
            token_count=token_count,
        )
        self.db.add(ctx)
        await self.db.flush()
        return ctx

    async def get_relevant_context(self, workflow_id: uuid.UUID, execution_id: uuid.UUID,
                                    stage_id: uuid.UUID) -> list[WorkflowContext]:
        """
        Select relevant context for a stage:
        1. Get the stage's direct dependencies.
        2. Return outputs from those dependency stages (not the entire history).
        3. Also include the workflow objective (context_type='user_input').
        """
        # Get direct dependencies
        deps_result = await self.db.execute(
            select(StageDependency.depends_on_stage_id)
            .where(StageDependency.stage_id == stage_id)
        )
        dep_stage_ids = [row[0] for row in deps_result.fetchall()]

        # If no explicit dependencies, use every stage at the nearest lower stage_order
        # (same rule as DAGAnalyzer, so parallel peers all feed the stage that merges them)
        if not dep_stage_ids:
            current_order = await self.db.scalar(select(Stage.stage_order).where(Stage.id == stage_id))
            if current_order is not None:
                nearest_order = await self.db.scalar(
                    select(func.max(Stage.stage_order))
                    .where(Stage.workflow_id == workflow_id, Stage.stage_order < current_order)
                )
                if nearest_order is not None:
                    prev_result = await self.db.execute(
                        select(Stage.id)
                        .where(Stage.workflow_id == workflow_id, Stage.stage_order == nearest_order)
                    )
                    dep_stage_ids = list(prev_result.scalars().all())

        # Fetch context entries for dependency stages
        contexts = []
        if dep_stage_ids:
            result = await self.db.execute(
                select(WorkflowContext)
                .where(
                    WorkflowContext.workflow_id == workflow_id,
                    WorkflowContext.execution_id == execution_id,
                    WorkflowContext.stage_id.in_(dep_stage_ids),
                    WorkflowContext.context_type == "stage_output",
                )
                .order_by(WorkflowContext.created_at)
            )
            contexts = list(result.scalars().all())

        # Also include user_input / system context
        sys_result = await self.db.execute(
            select(WorkflowContext)
            .where(
                WorkflowContext.workflow_id == workflow_id,
                WorkflowContext.execution_id == execution_id,
                WorkflowContext.context_type.in_(["user_input", "system"]),
            )
        )
        contexts.extend(sys_result.scalars().all())
        return contexts

    async def assemble_stage_input(self, workflow_id: uuid.UUID, execution_id: uuid.UUID,
                                    stage: Stage) -> str:
        """
        Assemble the full input for a stage:
        Stage Input = Stage Instruction + Relevant Previous Outputs + Workflow Context
        """
        relevant = await self.get_relevant_context(workflow_id, execution_id, stage.id)
        parts = []
        # System / user input context
        for ctx in relevant:
            if ctx.context_type in ("user_input", "system"):
                parts.append(f"[Workflow Context]\n{ctx.content}\n")
        # Previous stage outputs
        for ctx in relevant:
            if ctx.context_type == "stage_output":
                parts.append(f"[Previous Stage Output]\n{ctx.content}\n")
        # Current stage instruction
        parts.append(f"[Current Task: {stage.name}]\n{stage.instruction}")
        return "\n---\n".join(parts)

    async def get_all_context(self, workflow_id: uuid.UUID, execution_id: uuid.UUID) -> list[WorkflowContext]:
        result = await self.db.execute(
            select(WorkflowContext)
            .where(WorkflowContext.workflow_id == workflow_id, WorkflowContext.execution_id == execution_id)
            .order_by(WorkflowContext.created_at)
        )
        return list(result.scalars().all())
