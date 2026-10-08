"""
DAG Analyzer unit tests (no database: stages are transient ORM objects).
"""
import uuid

import pytest

from backend.app.models.stage import Stage, StageDependency
from backend.app.services.execution.dag_analyzer import DAGAnalyzer, DAGCycleError, implicit_dependency_ids

WORKFLOW_ID = uuid.uuid4()


def make_stage(name: str, order: int, depends_on: list[Stage] | None = None) -> Stage:
    stage = Stage(id=uuid.uuid4(), workflow_id=WORKFLOW_ID, name=name,
                  instruction=f"Do {name}", stage_order=order, stage_type="analysis")
    stage.dependencies = [
        StageDependency(stage_id=stage.id, depends_on_stage_id=dep.id) for dep in (depends_on or [])
    ]
    return stage


def names(stages) -> list[str]:
    return [s.name for s in stages]


def test_sequential_workflow_is_a_chain():
    stages = [make_stage(f"S{i}", i) for i in range(3)]
    analyzer = DAGAnalyzer(stages)

    assert [names(level) for level in analyzer.get_execution_order()] == [["S0"], ["S1"], ["S2"]]
    assert analyzer.get_parallelism_factor() == 1.0
    assert names(analyzer.get_critical_path()) == ["S0", "S1", "S2"]
    assert names(analyzer.get_independent_stages()) == ["S0"]
    # Each stage waits only for its predecessor: no merge points in a chain
    assert not any(analyzer.is_merge_point(s.id) for s in stages)


def test_same_order_stages_run_in_parallel_and_merge():
    start = make_stage("Start", 0)
    b1, b2 = make_stage("Branch 1", 1), make_stage("Branch 2", 1)
    merge = make_stage("Merge", 2)
    analyzer = DAGAnalyzer([merge, b2, start, b1])  # input order doesn't matter

    assert [names(level) for level in analyzer.execution_levels] == [["Start"], ["Branch 1", "Branch 2"], ["Merge"]]
    assert analyzer.is_merge_point(merge.id)
    assert set(names(analyzer.get_dependencies(merge.id))) == {"Branch 1", "Branch 2"}
    assert set(names(analyzer.get_dependents(start.id))) == {"Branch 1", "Branch 2"}
    assert analyzer.get_max_width() == 2
    assert analyzer.get_parallelism_factor() == pytest.approx(4 / 3)
    assert len(analyzer.get_critical_path()) == 3


def test_independent_first_level():
    stages = [make_stage(f"P{i}", 0) for i in range(3)]
    analyzer = DAGAnalyzer(stages)
    assert len(analyzer.execution_levels) == 1
    assert len(analyzer.get_independent_stages()) == 3
    assert analyzer.get_parallelism_factor() == 3.0


def test_explicit_dependencies_override_order():
    """A late stage that explicitly depends only on the first stage runs beside the middle one."""
    a = make_stage("A", 0)
    b = make_stage("B", 1)
    c = make_stage("C", 2, depends_on=[a])
    analyzer = DAGAnalyzer([a, b, c])

    assert [names(level) for level in analyzer.execution_levels] == [["A"], ["B", "C"]]
    assert names(analyzer.get_critical_path()) == ["A", "B"]


def test_explicit_merge_of_long_and_short_branch():
    a = make_stage("A", 0)
    long1 = make_stage("Long 1", 1, depends_on=[a])
    long2 = make_stage("Long 2", 2, depends_on=[long1])
    short = make_stage("Short", 1, depends_on=[a])
    merge = make_stage("Merge", 3, depends_on=[long2, short])
    analyzer = DAGAnalyzer([a, long1, long2, short, merge])

    assert analyzer.nodes[merge.id].level == 3
    assert analyzer.nodes[short.id].level == 1
    assert names(analyzer.get_critical_path()) == ["A", "Long 1", "Long 2", "Merge"]
    assert analyzer.get_descendants(a.id) == {long1.id, long2.id, short.id, merge.id}
    assert analyzer.get_descendants(short.id) == {merge.id}


def test_cycle_is_rejected():
    a = make_stage("A", 0)
    b = make_stage("B", 1)
    a.dependencies = [StageDependency(stage_id=a.id, depends_on_stage_id=b.id)]
    b.dependencies = [StageDependency(stage_id=b.id, depends_on_stage_id=a.id)]
    with pytest.raises(DAGCycleError, match="A, B|B, A"):
        DAGAnalyzer([a, b])


def test_dependencies_outside_workflow_are_ignored():
    outsider = make_stage("Elsewhere", 0)
    a = make_stage("A", 0, depends_on=[outsider])
    analyzer = DAGAnalyzer([a])
    assert analyzer.get_independent_stages() == [a]


def test_implicit_dependency_rule():
    s0, s1a, s1b, s2 = make_stage("0", 0), make_stage("1a", 1), make_stage("1b", 1), make_stage("2", 2)
    stages = [s0, s1a, s1b, s2]
    assert implicit_dependency_ids(s0, stages) == []
    assert implicit_dependency_ids(s1a, stages) == [s0.id]
    assert set(implicit_dependency_ids(s2, stages)) == {s1a.id, s1b.id}


def test_to_dict_and_visualization():
    start = make_stage("Start", 0)
    b1, b2 = make_stage("B1", 1), make_stage("B2", 1)
    analyzer = DAGAnalyzer([start, b1, b2])

    data = analyzer.to_dict()
    assert data["levels"] == [[str(start.id)], [str(b1.id), str(b2.id)]]
    assert {(e["source"], e["target"]) for e in data["edges"]} == {(str(start.id), str(b1.id)), (str(start.id), str(b2.id))}
    assert data["max_width"] == 2
    assert [n["on_critical_path"] for n in data["nodes"]].count(True) == 2

    text = analyzer.visualize_dag()
    assert "Execution DAG:" in text
    assert "Total Stages: 3" in text
    assert "Parallelism Factor: 1.50x" in text
    assert "B1 <- Start" in text
