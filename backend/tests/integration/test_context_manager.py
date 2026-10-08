"""Tests for ContextManager service"""
import pytest
import uuid
from backend.app.services.context_manager import ContextManager
from backend.app.models import WorkflowContext


@pytest.mark.asyncio
async def test_add_context(db_session, sample_workflow, sample_stage):
    """Test adding context entries"""
    ctx_mgr = ContextManager(db_session)
    execution_id = uuid.uuid4()
    
    ctx = await ctx_mgr.add_context(
        workflow_id=sample_workflow.id,
        execution_id=execution_id,
        stage_id=sample_stage.id,
        content="Test output from stage",
        context_type="stage_output",
        token_count=50
    )
    
    await db_session.commit()
    
    assert ctx.id is not None
    assert ctx.content == "Test output from stage"
    assert ctx.token_count == 50
    assert ctx.context_type == "stage_output"


@pytest.mark.asyncio
async def test_get_relevant_context_no_dependencies(db_session, sample_workflow, sample_stage):
    """Test context retrieval when stage has no explicit dependencies"""
    ctx_mgr = ContextManager(db_session)
    execution_id = uuid.uuid4()
    
    # Add workflow context (user input)
    await ctx_mgr.add_context(
        workflow_id=sample_workflow.id,
        execution_id=execution_id,
        stage_id=sample_stage.id,
        content="Initial workflow objective",
        context_type="user_input"
    )
    
    await db_session.commit()
    
    # Get relevant context
    contexts = await ctx_mgr.get_relevant_context(
        workflow_id=sample_workflow.id,
        execution_id=execution_id,
        stage_id=sample_stage.id
    )
    
    # Should include user_input context
    assert len(contexts) > 0
    assert any(c.context_type == "user_input" for c in contexts)


@pytest.mark.asyncio
async def test_assemble_stage_input(db_session, sample_workflow, sample_stage):
    """Test assembling complete stage input"""
    ctx_mgr = ContextManager(db_session)
    execution_id = uuid.uuid4()
    
    # Add some context
    await ctx_mgr.add_context(
        workflow_id=sample_workflow.id,
        execution_id=execution_id,
        stage_id=sample_stage.id,
        content="User wants to analyze data",
        context_type="user_input"
    )
    
    await db_session.commit()
    
    # Assemble input
    stage_input = await ctx_mgr.assemble_stage_input(
        workflow_id=sample_workflow.id,
        execution_id=execution_id,
        stage=sample_stage
    )
    
    # Should contain workflow context and stage instruction
    assert "Workflow Context" in stage_input or "User wants to analyze data" in stage_input
    assert sample_stage.name in stage_input or sample_stage.instruction in stage_input


@pytest.mark.asyncio
async def test_get_all_context(db_session, sample_workflow, sample_stage):
    """Test retrieving all context for an execution"""
    ctx_mgr = ContextManager(db_session)
    execution_id = uuid.uuid4()
    
    # Add multiple context entries
    await ctx_mgr.add_context(
        workflow_id=sample_workflow.id,
        execution_id=execution_id,
        stage_id=sample_stage.id,
        content="First context",
        context_type="user_input"
    )
    
    await ctx_mgr.add_context(
        workflow_id=sample_workflow.id,
        execution_id=execution_id,
        stage_id=sample_stage.id,
        content="Second context",
        context_type="stage_output"
    )
    
    await db_session.commit()
    
    # Get all context
    all_contexts = await ctx_mgr.get_all_context(
        workflow_id=sample_workflow.id,
        execution_id=execution_id
    )
    
    assert len(all_contexts) == 2
    assert all_contexts[0].content == "First context"
    assert all_contexts[1].content == "Second context"
