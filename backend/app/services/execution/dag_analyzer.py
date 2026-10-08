"""
DAG Analyzer.
Builds a workflow's stage dependency graph and derives execution levels,
merge points and the critical path for parallel execution.

Dependency rule (shared with ContextManager):
  - a stage with explicit stage_dependencies depends on exactly those stages;
  - otherwise it depends on every stage at the nearest lower stage_order.
So distinct orders run sequentially, and stages sharing a stage_order are
parallel peers that the next order waits for (a merge point).
"""
import uuid
from collections import deque
from typing import Iterable, Sequence

from backend.app.models.stage import Stage


class DAGCycleError(ValueError):
    """The workflow's dependencies contain a cycle."""


def implicit_dependency_ids(stage: Stage, stages: Iterable[Stage]) -> list[uuid.UUID]:
    """Ids of the stages at the nearest stage_order below `stage` (empty for the first order)."""
    earlier = [s for s in stages if s.stage_order < stage.stage_order]
    if not earlier:
        return []
    nearest = max(s.stage_order for s in earlier)
    return [s.id for s in earlier if s.stage_order == nearest]


def _explicit_dependency_ids(stage: Stage) -> list[uuid.UUID]:
    # `dependencies` is eagerly loaded for persisted stages and an empty list on transient ones
    return [dep.depends_on_stage_id for dep in (stage.dependencies or [])]


class DAGNode:
    def __init__(self, stage: Stage):
        self.stage = stage
        self.dependencies: set[uuid.UUID] = set()  # stages this one waits for
        self.dependents: set[uuid.UUID] = set()    # stages waiting for this one
        self.level = 0                              # longest dependency chain above this node

    def __repr__(self) -> str:
        return f"<DAGNode({self.stage.name}, level={self.level})>"


class DAGAnalyzer:
    def __init__(self, stages: Sequence[Stage]):
        self.stages = sorted(stages, key=lambda s: (s.stage_order, s.name))
        self.nodes: dict[uuid.UUID, DAGNode] = {s.id: DAGNode(s) for s in self.stages}
        self._build_edges()
        self.topological_order: list[uuid.UUID] = self._topological_sort()
        self._assign_levels()

    def _build_edges(self) -> None:
        for stage in self.stages:
            node = self.nodes[stage.id]
            # Explicit dependencies on stages outside this workflow are ignored
            explicit = [d for d in _explicit_dependency_ids(stage) if d in self.nodes and d != stage.id]
            for dep_id in explicit or implicit_dependency_ids(stage, self.stages):
                node.dependencies.add(dep_id)
                self.nodes[dep_id].dependents.add(stage.id)

    def _topological_sort(self) -> list[uuid.UUID]:
        """Kahn's algorithm; ties resolve by stage_order so output is deterministic."""
        rank = {s.id: i for i, s in enumerate(self.stages)}
        in_degree = {nid: len(n.dependencies) for nid, n in self.nodes.items()}
        ready = deque(sorted((nid for nid, d in in_degree.items() if d == 0), key=rank.get))
        order = []
        while ready:
            nid = ready.popleft()
            order.append(nid)
            for child in sorted(self.nodes[nid].dependents, key=rank.get):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    ready.append(child)
        if len(order) != len(self.nodes):
            stuck = [self.nodes[nid].stage.name for nid, d in in_degree.items() if d > 0]
            raise DAGCycleError(f"Cycle detected in workflow dependencies involving: {', '.join(stuck)}")
        return order

    def _assign_levels(self) -> None:
        for nid in self.topological_order:
            node = self.nodes[nid]
            node.level = max((self.nodes[d].level + 1 for d in node.dependencies), default=0)

    # ---------- Queries ----------

    @property
    def execution_levels(self) -> list[list[Stage]]:
        """Stages grouped by level; every stage in a level can run in parallel."""
        levels: dict[int, list[Stage]] = {}
        for nid in self.topological_order:
            node = self.nodes[nid]
            levels.setdefault(node.level, []).append(node.stage)
        return [levels[i] for i in sorted(levels)]

    def get_execution_order(self) -> list[list[Stage]]:
        return self.execution_levels

    def get_independent_stages(self) -> list[Stage]:
        """Stages with no dependencies (can start immediately)."""
        return [self.nodes[nid].stage for nid in self.topological_order if not self.nodes[nid].dependencies]

    def get_dependencies(self, stage_id: uuid.UUID) -> list[Stage]:
        node = self.nodes.get(stage_id)
        return [self.nodes[d].stage for d in node.dependencies] if node else []

    def get_dependents(self, stage_id: uuid.UUID) -> list[Stage]:
        node = self.nodes.get(stage_id)
        return [self.nodes[d].stage for d in node.dependents] if node else []

    def get_descendants(self, stage_id: uuid.UUID) -> set[uuid.UUID]:
        """All stages that directly or transitively depend on stage_id."""
        found: set[uuid.UUID] = set()
        queue = deque([stage_id])
        while queue:
            for child in self.nodes[queue.popleft()].dependents:
                if child not in found:
                    found.add(child)
                    queue.append(child)
        return found

    def is_merge_point(self, stage_id: uuid.UUID) -> bool:
        """A stage that waits for more than one stage."""
        node = self.nodes.get(stage_id)
        return bool(node and len(node.dependencies) > 1)

    def get_parallelism_factor(self) -> float:
        """Average stages per level: 1.0 means fully sequential."""
        levels = self.execution_levels
        return len(self.stages) / len(levels) if levels else 1.0

    def get_max_width(self) -> int:
        """Largest number of stages that can run at once."""
        return max((len(level) for level in self.execution_levels), default=0)

    def get_critical_path(self) -> list[Stage]:
        """Longest dependency chain (by stage count): the minimum number of sequential steps."""
        best: dict[uuid.UUID, list[uuid.UUID]] = {}
        for nid in self.topological_order:
            node = self.nodes[nid]
            longest = max((best[d] for d in node.dependencies), key=len, default=[])
            best[nid] = longest + [nid]
        path = max(best.values(), key=len, default=[])
        return [self.nodes[nid].stage for nid in path]

    def to_dict(self) -> dict:
        """JSON-friendly description of the graph for the API."""
        critical = {s.id for s in self.get_critical_path()}
        return {
            "nodes": [
                {
                    "stage_id": str(nid),
                    "name": self.nodes[nid].stage.name,
                    "stage_order": self.nodes[nid].stage.stage_order,
                    "stage_type": self.nodes[nid].stage.stage_type,
                    "level": self.nodes[nid].level,
                    "dependencies": sorted(str(d) for d in self.nodes[nid].dependencies),
                    "is_merge_point": self.is_merge_point(nid),
                    "on_critical_path": nid in critical,
                }
                for nid in self.topological_order
            ],
            "edges": [
                {"source": str(dep), "target": str(nid)}
                for nid in self.topological_order
                for dep in sorted(self.nodes[nid].dependencies, key=str)
            ],
            "levels": [[str(s.id) for s in level] for level in self.execution_levels],
            "critical_path": [str(s.id) for s in self.get_critical_path()],
            "parallelism_factor": round(self.get_parallelism_factor(), 2),
            "max_width": self.get_max_width(),
        }

    def visualize_dag(self) -> str:
        """ASCII summary of levels, dependencies and the critical path."""
        lines = ["Execution DAG:", "=" * 60]
        for i, level in enumerate(self.execution_levels):
            lines.append(f"\nLevel {i} ({'parallel' if len(level) > 1 else 'single'}):")
            for stage in level:
                deps = [self.nodes[d].stage.name for d in self.nodes[stage.id].dependencies]
                lines.append(f"  • {stage.name}" + (f" <- {', '.join(sorted(deps))}" if deps else " (no dependencies)"))
        lines += [
            "\n" + "=" * 60,
            f"Total Stages: {len(self.stages)}",
            f"Execution Levels: {len(self.execution_levels)}",
            f"Parallelism Factor: {self.get_parallelism_factor():.2f}x",
        ]
        critical = self.get_critical_path()
        if critical:
            lines.append(f"Critical Path: {' -> '.join(s.name for s in critical)}")
        return "\n".join(lines)
