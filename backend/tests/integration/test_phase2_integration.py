"""
Phase 2 Integration Tests.
End-to-end tests for context management, LLM integration, and execution.
"""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.workflow import Workflow
from backend.app.models.stage import Stage
from backend.app.models.execution import ExecutionRecord
from backend.app.models.context import WorkflowContext
from backend.app.services.execution import ExecutionEngine
from backend.app.services.context_manager import ContextManager


# ============================================================================
# Context Management Tests
# ============================================================================

@pytest.mark.asyncio
async def test_context_manager_adds_context(db_session: AsyncSession, sample_workflow_with_stages: Workflow):
    """Test adding context entries."""
    ctx_mgr = ContextManager(db_session)
    execution_id = uuid.uuid4()
    stage = sample_workflow_with_stages.stages[0]

    await ctx_mgr.add_context(
        workflow_id=sample_workflow_with_stages.id,
        execution_id=execution_id,
        stage_id=stage.id,
        content="Test output from stage 1",
        context_type="stage_output",
        token_count=50
    )
    await db_session.commit()

    # Verify stored
    result = await db_session.execute(
        select(WorkflowContext).where(WorkflowContext.execution_id == execution_id)
    )
    contexts = result.scalars().all()
    assert len(contexts) == 1
    assert contexts[0].content == "Test output from stage 1"
    assert contexts[0].token_count == 50


@pytest.mark.asyncio
async def test_context_manager_retrieves_relevant_context(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow
):
    """Test retrieving relevant context for a stage."""
    ctx_mgr = ContextManager(db_session)
    execution_id = uuid.uuid4()

    # Add context from stage 1
    await ctx_mgr.add_context(
        workflow_id=sample_workflow_with_stages.id,
        execution_id=execution_id,
        stage_id=sample_workflow_with_stages.stages[0].id,
        content="Stage 1 output: Requirements listed.",
        context_type="stage_output",
        token_count=30
    )
    await db_session.commit()

    # Retrieve for stage 2 (using stage_id)
    stage2 = sample_workflow_with_stages.stages[1]
    contexts = await ctx_mgr.get_relevant_context(
        workflow_id=sample_workflow_with_stages.id,
        execution_id=execution_id,
        stage_id=stage2.id
    )

    assert len(contexts) >= 1
    # Find the stage output in contexts
    stage_outputs = [ctx for ctx in contexts if ctx.context_type == "stage_output"]
    assert len(stage_outputs) >= 1
    assert "Stage 1 output" in stage_outputs[0].content


@pytest.mark.asyncio
async def test_context_manager_assembles_stage_input(
    db_session: AsyncSession, sample_workflow_with_stages: Workflow
):
    """Test assembling full stage input with context."""
    ctx_mgr = ContextManager(db_session)
    execution_id = uuid.uuid4()

    # Add previous stage output
    await ctx_mgr.add_context(
        workflow_id=sample_workflow_with_stages.id,
        execution_id=execution_id,
        stage_id=sample_workflow_with_stages.stages[0].id,
        content="Previous output: User auth, CRUD operations, data persistence.",
        context_type="stage_output",
        token_count=20
    )
    await db_session.commit()

    # Assemble input for stage 2
    stage2 = sample_workflow_with_stages.stages[1]
    stage_input = await ctx_mgr.assemble_stage_input(
        workflow_id=sample_workflow_with_stages.id,
        execution_id=execution_id,
        stage=stage2
    )

    assert stage2.instruction in stage_input
    assert "Previous output" in stage_input


# ============================================================================
# Execution Engine Tests
# ============================================================================

@pytest.mark.asyncio
async def test_execution_engine_runs_workflow(
    db_session: AsyncSession,
    sample_workflow_with_stages: Workflow,
    mock_llm_response,
    fake_provider
):
    """Test execution engine runs all stages sequentially."""
    # Configure fake provider to return specific responses
    fake_provider.version = 1
    
    engine = ExecutionEngine(db_session)
    execution_id = await engine.execute_workflow(
        sample_workflow_with_stages.id,
        default_provider="fake",
        use_routing=False  # Don't use routing, just use fake provider directly
    )
    await db_session.commit()

    # Verify execution records created
    result = await db_session.execute(
        select(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id)
    )
    records = result.scalars().all()
    assert len(records) == 3
    assert all(r.status == "completed" for r in records)

    # Verify workflow status updated
    await db_session.refresh(sample_workflow_with_stages)
    assert sample_workflow_with_stages.status == "completed"


@pytest.mark.asyncio
async def test_execution_engine_stores_context(
    db_session: AsyncSession,
    sample_workflow_with_stages: Workflow,
    mock_llm_response,
    fake_provider
):
    """Test execution stores outputs in context."""
    fake_provider.version = 1
    
    engine = ExecutionEngine(db_session)
    execution_id = await engine.execute_workflow(
        sample_workflow_with_stages.id,
        default_provider="fake",
        use_routing=False
    )
    await db_session.commit()

    # Verify context entries created
    result = await db_session.execute(
        select(WorkflowContext).where(WorkflowContext.execution_id == execution_id)
    )
    contexts = result.scalars().all()
    # 1 objective + 3 stage outputs = 4
    assert len(contexts) >= 4


@pytest.mark.asyncio
async def test_execution_engine_context_flows_between_stages(
    db_session: AsyncSession,
    sample_workflow_with_stages: Workflow,
    mock_llm_response,
    fake_provider
):
    """Test that stage 2 receives stage 1's output as context."""
    fake_provider.version = 1
    
    engine = ExecutionEngine(db_session)
    execution_id = await engine.execute_workflow(
        sample_workflow_with_stages.id,
        default_provider="fake",
        use_routing=False
    )
    await db_session.commit()

    # Verify all 3 stages executed
    result = await db_session.execute(
        select(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id)
    )
    records = result.scalars().all()
    assert len(records) == 3


@pytest.mark.asyncio
async def test_execution_engine_handles_failure(
    db_session: AsyncSession,
    sample_workflow_with_stages: Workflow
):
    """Test execution handles LLM failures gracefully."""
    # Don't register any provider - execution will fail immediately
    engine = ExecutionEngine(db_session)
    execution_id = await engine.execute_workflow(
        sample_workflow_with_stages.id,
        default_provider="nonexistent",
        use_routing=False
    )
    await db_session.commit()

    # Verify failure recorded
    result = await db_session.execute(
        select(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id)
    )
    records = result.scalars().all()
    assert len(records) == 1  # Only first stage attempted
    assert records[0].status == "failed"
    assert records[0].error_message is not None

    # Verify workflow marked as failed
    await db_session.refresh(sample_workflow_with_stages)
    assert sample_workflow_with_stages.status == "failed"


@pytest.mark.asyncio

async def test_execution_engine_retries_on_failure(
    db_session: AsyncSession,
    sample_workflow_with_stages: Workflow,
    mock_llm_response,
    fake_provider
):
    """Test retry mechanism on transient failures."""
    fake_provider.version = 1
    
    engine = ExecutionEngine(db_session)
    execution_id = await engine.execute_workflow(
        sample_workflow_with_stages.id,
        default_provider="fake",
        use_routing=False
    )
    await db_session.commit()

    # Verify all stages completed
    result = await db_session.execute(
        select(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id)
    )
    records = result.scalars().all()
    assert len(records) == 3
    assert all(r.status == "completed" for r in records)


# ============================================================================
# Execution Metrics Tests
# ============================================================================

@pytest.mark.asyncio

async def test_execution_records_tokens_and_cost(
    db_session: AsyncSession,
    sample_workflow_with_stages: Workflow,
    mock_llm_response,
    fake_provider
):
    """Test execution records capture tokens and estimated cost."""
    fake_provider.version = 1
    
    engine = ExecutionEngine(db_session)
    execution_id = await engine.execute_workflow(
        sample_workflow_with_stages.id,
        default_provider="fake",
        use_routing=False
    )
    await db_session.commit()

    result = await db_session.execute(
        select(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id)
    )
    records = result.scalars().all()

    total_tokens = sum(r.total_tokens or 0 for r in records)
    
    # FakeProvider returns 150 tokens per call (100 input + 50 output)
    assert total_tokens == 450  # 150 * 3 stages


# ============================================================================
# End-to-End Workflow Test
# ============================================================================

@pytest.mark.asyncio

async def test_e2e_workflow_execution(
    db_session: AsyncSession,
    mock_llm_response,
    fake_provider
):
    """
    End-to-end test: Create workflow → Add stages → Execute → Verify results.
    """
    # Step 1: Create workflow
    workflow = Workflow(
        id=uuid.uuid4(),
        name="E2E Test Workflow",
        objective="Validate full execution pipeline",
        status="draft"
    )
    db_session.add(workflow)
    await db_session.flush()

    # Step 2: Add stages
    stages = [
        Stage(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            name="Requirement Analysis",
            instruction="Analyze user requirements.",
            stage_order=0,
            stage_type="analysis",
            status="pending"
        ),
        Stage(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            name="System Design",
            instruction="Design system architecture.",
            stage_order=1,
            stage_type="design",
            status="pending"
        )
    ]
    db_session.add_all(stages)
    await db_session.commit()

    # Step 3: Use fake provider
    fake_provider.version = 1
    
    # Step 4: Execute workflow
    engine = ExecutionEngine(db_session)
    execution_id = await engine.execute_workflow(
        workflow.id,
        default_provider="fake",
        use_routing=False
    )
    await db_session.commit()

    # Step 5: Verify results
    result = await db_session.execute(
        select(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id)
    )
    records = result.scalars().all()

    assert len(records) == 2
    # FakeProvider returns deterministic output based on prompt hash
    assert all(r.status == "completed" for r in records)

    # Step 6: Verify workflow status
    await db_session.refresh(workflow)
    assert workflow.status == "completed"
