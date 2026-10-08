"""
Tests for the Workflow Planner.

Tests intelligent workflow generation from natural language objectives.
"""

import pytest
from backend.app.services.workflow_planner import WorkflowPlanner, PlannerValidationError
from backend.app.schemas.planner import ObjectiveAnalysisResponse, StagePlan


@pytest.mark.asyncio
async def test_planner_detects_circular_dependency(db_session):
    """Planner should reject plans with circular dependencies."""
    planner = WorkflowPlanner(db_session)
    
    # Create a plan with circular dependency: A → B → C → A
    stages = [
        StagePlan(
            id="stage_a",
            name="Stage A",
            description="First stage in the workflow",
            instruction="Execute stage A processing",
            stage_type="analysis",
            dependencies=["stage_c"],  # A depends on C
            expected_output="Output from stage A",
        ),
        StagePlan(
            id="stage_b",
            name="Stage B",
            description="Second stage in the workflow",
            instruction="Execute stage B processing",
            stage_type="design",
            dependencies=["stage_a"],  # B depends on A
            expected_output="Output from stage B",
        ),
        StagePlan(
            id="stage_c",
            name="Stage C",
            description="Third stage in the workflow",
            instruction="Execute stage C processing",
            stage_type="generation",
            dependencies=["stage_b"],  # C depends on B → cycle!
            expected_output="Output from stage C",
        ),
    ]
    
    plan = ObjectiveAnalysisResponse(
        complexity="complex",
        reason="Test circular dependency detection",
        stages=stages,
    )
    
    with pytest.raises(PlannerValidationError, match="Circular dependency"):
        planner._validate_plan(plan)


@pytest.mark.asyncio
async def test_planner_rejects_duplicate_stage_ids(db_session):
    """Planner should reject plans with duplicate stage IDs."""
    planner = WorkflowPlanner(db_session)
    
    stages = [
        StagePlan(
            id="duplicate_id",
            name="Stage A",
            description="First stage in the workflow",
            instruction="Execute stage A processing",
            stage_type="analysis",
            dependencies=[],
            expected_output="Output from stage A",
        ),
        StagePlan(
            id="duplicate_id",  # Duplicate!
            name="Stage B",
            description="Second stage in the workflow",
            instruction="Execute stage B processing",
            stage_type="design",
            dependencies=[],
            expected_output="Output from stage B",
        ),
    ]
    
    plan = ObjectiveAnalysisResponse(
        complexity="complex",
        reason="Test duplicate IDs detection",
        stages=stages,
    )
    
    with pytest.raises(PlannerValidationError, match="Duplicate stage IDs"):
        planner._validate_plan(plan)


@pytest.mark.asyncio
async def test_planner_rejects_invalid_dependency_references(db_session):
    """Planner should reject stages that depend on non-existent stages."""
    planner = WorkflowPlanner(db_session)
    
    stages = [
        StagePlan(
            id="stage_a",
            name="Stage A",
            description="First stage in the workflow",
            instruction="Execute stage A processing",
            stage_type="analysis",
            dependencies=["nonexistent_stage"],  # Invalid!
            expected_output="Output from stage A",
        ),
        StagePlan(
            id="stage_b",
            name="Stage B",
            description="Second stage in the workflow",
            instruction="Execute stage B processing",
            stage_type="design",
            dependencies=[],
            expected_output="Output from stage B",
        ),
    ]
    
    plan = ObjectiveAnalysisResponse(
        complexity="complex",
        reason="Test invalid dependency reference",
        stages=stages,
    )
    
    with pytest.raises(PlannerValidationError, match="non-existent stage"):
        planner._validate_plan(plan)


@pytest.mark.asyncio
async def test_planner_rejects_self_dependency(db_session):
    """Planner should reject stages that depend on themselves."""
    planner = WorkflowPlanner(db_session)
    
    stages = [
        StagePlan(
            id="stage_a",
            name="Stage A",
            description="First stage in the workflow",
            instruction="Execute stage A processing",
            stage_type="analysis",
            dependencies=["stage_a"],  # Self-dependency!
            expected_output="Output from stage A",
        ),
    ]
    
    plan = ObjectiveAnalysisResponse(
        complexity="simple",
        reason="Test self dependency detection",
        stages=stages,
    )
    
    with pytest.raises(PlannerValidationError, match="Circular dependency"):
        planner._validate_plan(plan)


@pytest.mark.asyncio
async def test_planner_validates_simple_vs_complex_stage_count(db_session):
    """Simple complexity should have 1 stage, complex should have multiple."""
    planner = WorkflowPlanner(db_session)
    
    # Simple with multiple stages → invalid
    stages_multiple = [
        StagePlan(
            id="stage_a",
            name="Stage A",
            description="First stage in the workflow",
            instruction="Execute stage A processing",
            stage_type="analysis",
            dependencies=[],
            expected_output="Output from stage A",
        ),
        StagePlan(
            id="stage_b",
            name="Stage B",
            description="Second stage in the workflow",
            instruction="Execute stage B processing",
            stage_type="design",
            dependencies=[],
            expected_output="Output from stage B",
        ),
    ]
    
    plan = ObjectiveAnalysisResponse(
        complexity="simple",
        reason="Test stage count validation",
        stages=stages_multiple,
    )
    
    with pytest.raises(PlannerValidationError, match="Simple complexity should have 1 stage"):
        planner._validate_plan(plan)
    
    # Complex with single stage → invalid
    stages_single = [
        StagePlan(
            id="stage_a",
            name="Stage A",
            description="Only stage in the workflow",
            instruction="Execute stage A processing",
            stage_type="analysis",
            dependencies=[],
            expected_output="Output from stage A",
        ),
    ]
    
    plan = ObjectiveAnalysisResponse(
        complexity="complex",
        reason="Test stage count validation",
        stages=stages_single,
    )
    
    with pytest.raises(PlannerValidationError, match="Complex complexity should have multiple stages"):
        planner._validate_plan(plan)


@pytest.mark.asyncio
async def test_planner_accepts_valid_dag(db_session):
    """Planner should accept a valid DAG with proper dependencies."""
    planner = WorkflowPlanner(db_session)
    
    # Valid DAG: A → B → C
    #            A → D → C  (merge at C)
    stages = [
        StagePlan(
            id="stage_a",
            name="Stage A",
            description="Requirements",
            instruction="Analyze requirements",
            stage_type="analysis",
            dependencies=[],
            expected_output="Requirements doc",
        ),
        StagePlan(
            id="stage_b",
            name="Stage B",
            description="Architecture",
            instruction="Design architecture",
            stage_type="design",
            dependencies=["stage_a"],
            expected_output="Architecture doc",
        ),
        StagePlan(
            id="stage_d",
            name="Stage D",
            description="Database Design",
            instruction="Design database",
            stage_type="design",
            dependencies=["stage_a"],
            expected_output="Database schema",
        ),
        StagePlan(
            id="stage_c",
            name="Stage C",
            description="Implementation",
            instruction="Implement system",
            stage_type="generation",
            dependencies=["stage_b", "stage_d"],  # Merge point
            expected_output="Implementation",
        ),
    ]
    
    plan = ObjectiveAnalysisResponse(
        complexity="complex",
        reason="Valid multi-stage workflow",
        stages=stages,
    )
    
    # Should not raise
    planner._validate_plan(plan)


@pytest.mark.asyncio
async def test_planner_with_mock_provider(db_session, fake_provider):
    """
    Test planner with a mock LLM provider.
    
    This test uses FakeProvider which returns deterministic output.
    """
    planner = WorkflowPlanner(db_session, provider_name="fake")
    
    # FakeProvider returns the prompt as output, so we'll get back our prompt
    # This tests the planner can call an LLM, but not the parsing
    # (Real parsing tests require either real LLM or very specific mock)
    
    # For now, just verify planner can be instantiated with mock provider
    provider = planner._get_provider()
    assert provider.provider_name == "fake"


@pytest.mark.asyncio
async def test_cycle_detection_complex_case(db_session):
    """Test cycle detection in more complex scenarios."""
    planner = WorkflowPlanner(db_session)
    
    # No cycle: A → B, C → D, B → E, D → E
    stages_no_cycle = [
        StagePlan(id="a", name="A", description="Stage A processing", instruction="Execute A tasks", 
                 stage_type="analysis", dependencies=[], expected_output="Results from A"),
        StagePlan(id="b", name="B", description="Stage B processing", instruction="Execute B tasks",
                 stage_type="design", dependencies=["a"], expected_output="Results from B"),
        StagePlan(id="c", name="C", description="Stage C processing", instruction="Execute C tasks",
                 stage_type="analysis", dependencies=[], expected_output="Results from C"),
        StagePlan(id="d", name="D", description="Stage D processing", instruction="Execute D tasks",
                 stage_type="design", dependencies=["c"], expected_output="Results from D"),
        StagePlan(id="e", name="E", description="Stage E processing", instruction="Execute E tasks",
                 stage_type="generation", dependencies=["b", "d"], expected_output="Results from E"),
    ]
    
    plan_no_cycle = ObjectiveAnalysisResponse(
        complexity="complex",
        reason="Test no cycle in DAG",
        stages=stages_no_cycle,
    )
    
    # Should not raise
    planner._validate_plan(plan_no_cycle)
    
    # With cycle: A → B → C → B (cycle B-C-B)
    stages_with_cycle = [
        StagePlan(id="a", name="A", description="Stage A processing", instruction="Execute A tasks",
                 stage_type="analysis", dependencies=[], expected_output="Results from A"),
        StagePlan(id="b", name="B", description="Stage B processing", instruction="Execute B tasks",
                 stage_type="design", dependencies=["a", "c"], expected_output="Results from B"),
        StagePlan(id="c", name="C", description="Stage C processing", instruction="Execute C tasks",
                 stage_type="generation", dependencies=["b"], expected_output="Results from C"),
    ]
    
    plan_with_cycle = ObjectiveAnalysisResponse(
        complexity="complex",
        reason="Test cycle detection",
        stages=stages_with_cycle,
    )
    
    with pytest.raises(PlannerValidationError, match="Circular dependency"):
        planner._validate_plan(plan_with_cycle)

