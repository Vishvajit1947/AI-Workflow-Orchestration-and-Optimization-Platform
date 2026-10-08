"""
Graph validators for workflow stage dependencies.
- Cycle detection using DFS
- Workflow completeness validation
"""

import uuid
from collections import defaultdict
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.stage import Stage, StageDependency


async def build_dependency_graph(
    db: AsyncSession, workflow_id: uuid.UUID
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """
    Build an adjacency list of stage dependencies for a workflow.
    Returns: {stage_id: [list of stage_ids it depends on]}
    """
    # Get all stages for this workflow
    stages_result = await db.execute(
        select(Stage.id).where(Stage.workflow_id == workflow_id)
    )
    stage_ids = {row[0] for row in stages_result.fetchall()}

    # Get all dependencies between these stages
    deps_result = await db.execute(
        select(StageDependency.stage_id, StageDependency.depends_on_stage_id)
        .where(StageDependency.stage_id.in_(stage_ids))
    )

    graph: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for stage_id in stage_ids:
        graph[stage_id]  # ensure all stages appear in graph even without deps

    for stage_id, depends_on_id in deps_result.fetchall():
        graph[stage_id].append(depends_on_id)

    return dict(graph)


def detect_cycle(
    graph: dict[uuid.UUID, list[uuid.UUID]],
    new_edge: Optional[tuple[uuid.UUID, uuid.UUID]] = None,
) -> Optional[list[uuid.UUID]]:
    """
    Detect a cycle in the dependency graph using iterative DFS.
    If new_edge is provided, temporarily add it before checking.
    Returns: The cycle path if found, None otherwise.
    """
    # Create a working copy
    working_graph: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for node, deps in graph.items():
        working_graph[node] = list(deps)

    # Add the proposed new edge
    if new_edge:
        stage_id, depends_on_id = new_edge
        working_graph[stage_id].append(depends_on_id)
        if depends_on_id not in working_graph:
            working_graph[depends_on_id] = []

    # DFS-based cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in working_graph}
    parent = {node: None for node in working_graph}

    def dfs(start: uuid.UUID) -> Optional[list[uuid.UUID]]:
        stack = [start]
        while stack:
            node = stack[-1]
            if color[node] == WHITE:
                color[node] = GRAY
                for neighbor in working_graph.get(node, []):
                    if neighbor not in color:
                        color[neighbor] = WHITE
                        parent[neighbor] = None
                    if color[neighbor] == GRAY:
                        # Found a cycle — reconstruct path
                        cycle = [neighbor, node]
                        current = node
                        while current != neighbor and parent.get(current) is not None:
                            current = parent[current]
                            cycle.append(current)
                        return cycle
                    elif color[neighbor] == WHITE:
                        parent[neighbor] = node
                        stack.append(neighbor)
            else:
                stack.pop()
                color[node] = BLACK

        return None

    for node in list(working_graph.keys()):
        if color.get(node, WHITE) == WHITE:
            cycle = dfs(node)
            if cycle:
                return cycle

    return None


async def would_create_cycle(
    db: AsyncSession,
    workflow_id: uuid.UUID,
    stage_id: uuid.UUID,
    depends_on_stage_id: uuid.UUID,
) -> bool:
    """Check if adding a dependency would create a cycle."""
    graph = await build_dependency_graph(db, workflow_id)
    cycle = detect_cycle(graph, new_edge=(stage_id, depends_on_stage_id))
    return cycle is not None


async def validate_workflow(
    db: AsyncSession, workflow_id: uuid.UUID
) -> list[str]:
    """
    Validate a workflow's structure. Returns a list of warning/error messages.
    Empty list = valid.
    """
    errors: list[str] = []

    # Get stages
    stages_result = await db.execute(
        select(Stage).where(Stage.workflow_id == workflow_id).order_by(Stage.stage_order)
    )
    stages = list(stages_result.scalars().all())

    if not stages:
        errors.append("Workflow has no stages.")
        return errors

    # Check for stages without instructions
    for stage in stages:
        if not stage.instruction or not stage.instruction.strip():
            errors.append(f"Stage '{stage.name}' (order {stage.stage_order}) has no instruction.")

    # Check for dependency cycles
    graph = await build_dependency_graph(db, workflow_id)
    cycle = detect_cycle(graph)
    if cycle:
        cycle_names = [str(sid)[:8] for sid in cycle]
        errors.append(f"Circular dependency detected: {' → '.join(cycle_names)}")

    # Check for duplicate stage_order values
    orders = [s.stage_order for s in stages]
    if len(orders) != len(set(orders)):
        errors.append("Duplicate stage_order values detected. Use reorder to fix.")

    return errors
