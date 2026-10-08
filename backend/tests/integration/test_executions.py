"""
Tests for execution API endpoints.
"""
import uuid
from decimal import Decimal
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.models import Workflow, Stage, ExecutionRecord


@pytest.mark.asyncio
async def test_list_executions_empty(client: AsyncClient, db_session):
    """Test listing executions when none exist."""
    response = await client.get("/api/executions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_list_executions_with_data(client: AsyncClient, db_session):
    """Test listing executions with existing data."""
    # Create workflow and stages
    workflow = Workflow(
        name="Test Workflow",
        description="Test",
        objective="Test objective"
    )
    db_session.add(workflow)
    await db_session.flush()
    
    stage = Stage(
        workflow_id=workflow.id,
        name="Test Stage",
        instruction="Test instruction",
        stage_order=1
    )
    db_session.add(stage)
    await db_session.flush()
    
    # Create execution records
    exec_id = uuid.uuid4()
    record = ExecutionRecord(
        workflow_id=workflow.id,
        stage_id=stage.id,
        execution_id=exec_id,
        model_used="gpt-3.5-turbo",
        provider="openai",
        input_tokens=100,
        output_tokens=50,
        latency_ms=1000,
        estimated_cost=Decimal("0.0001"),
        status="completed",
        result="Test result",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    db_session.add(record)
    await db_session.commit()
    
    # Test list endpoint
    response = await client.get("/api/executions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    
    # Verify structure
    item = data[0]
    assert str(item["execution_id"]) == str(exec_id)
    assert str(item["workflow_id"]) == str(workflow.id)
    assert item["workflow_name"] == "Test Workflow"
    assert item["total_stages"] == 1
    assert item["completed_stages"] == 1


@pytest.mark.asyncio
async def test_list_executions_with_filter(client: AsyncClient, db_session):
    """Test listing executions filtered by workflow_id."""
    # Create two workflows
    workflow1 = Workflow(name="Workflow 1", description="Test 1")
    workflow2 = Workflow(name="Workflow 2", description="Test 2")
    db_session.add_all([workflow1, workflow2])
    await db_session.flush()
    
    stage1 = Stage(
        workflow_id=workflow1.id,
        name="Stage 1",
        instruction="Test",
        stage_order=1
    )
    stage2 = Stage(
        workflow_id=workflow2.id,
        name="Stage 2",
        instruction="Test",
        stage_order=1
    )
    db_session.add_all([stage1, stage2])
    await db_session.flush()
    
    # Create execution records for both
    exec_id1 = uuid.uuid4()
    exec_id2 = uuid.uuid4()
    
    record1 = ExecutionRecord(
        workflow_id=workflow1.id,
        stage_id=stage1.id,
        execution_id=exec_id1,
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    record2 = ExecutionRecord(
        workflow_id=workflow2.id,
        stage_id=stage2.id,
        execution_id=exec_id2,
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    db_session.add_all([record1, record2])
    await db_session.commit()
    
    # Test filtering by workflow_id
    response = await client.get(f"/api/executions?workflow_id={workflow1.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert str(data[0]["workflow_id"]) == str(workflow1.id)


@pytest.mark.asyncio
async def test_get_execution_details(client: AsyncClient, db_session):
    """Test getting detailed execution information."""
    # Create workflow with stages
    workflow = Workflow(name="Test Workflow", description="Test")
    db_session.add(workflow)
    await db_session.flush()
    
    stage1 = Stage(
        workflow_id=workflow.id,
        name="Stage 1",
        instruction="Test 1",
        stage_order=1
    )
    stage2 = Stage(
        workflow_id=workflow.id,
        name="Stage 2",
        instruction="Test 2",
        stage_order=2
    )
    db_session.add_all([stage1, stage2])
    await db_session.flush()
    
    # Create execution records
    exec_id = uuid.uuid4()
    record1 = ExecutionRecord(
        workflow_id=workflow.id,
        stage_id=stage1.id,
        execution_id=exec_id,
        model_used="gpt-3.5-turbo",
        provider="openai",
        input_tokens=100,
        output_tokens=50,
        latency_ms=1000,
        estimated_cost=Decimal("0.0001"),
        status="completed",
        result="Result 1",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    record2 = ExecutionRecord(
        workflow_id=workflow.id,
        stage_id=stage2.id,
        execution_id=exec_id,
        model_used="gpt-4",
        provider="openai",
        input_tokens=200,
        output_tokens=100,
        latency_ms=2000,
        estimated_cost=Decimal("0.0002"),
        status="completed",
        result="Result 2",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    db_session.add_all([record1, record2])
    await db_session.commit()
    
    # Test get details endpoint
    response = await client.get(f"/api/executions/{exec_id}")
    assert response.status_code == 200
    data = response.json()
    
    # Verify summary
    assert "summary" in data
    summary = data["summary"]
    assert str(summary["execution_id"]) == str(exec_id)
    assert str(summary["workflow_id"]) == str(workflow.id)
    assert summary["total_stages"] == 2
    assert summary["completed_stages"] == 2
    assert summary["failed_stages"] == 0
    assert summary["total_tokens"] == 450  # 100+50+200+100
    assert float(summary["total_cost"]) == 0.0003
    assert summary["total_latency_ms"] == 3000
    
    # Verify stages
    assert "stages" in data
    stages = data["stages"]
    assert len(stages) == 2
    assert stages[0]["stage_name"] == "Stage 1"
    assert stages[0]["model_used"] == "gpt-3.5-turbo"
    assert stages[0]["total_tokens"] == 150
    assert stages[1]["stage_name"] == "Stage 2"
    assert stages[1]["model_used"] == "gpt-4"
    assert stages[1]["total_tokens"] == 300


@pytest.mark.asyncio
async def test_get_execution_details_not_found(client: AsyncClient, db_session):
    """Test getting details for non-existent execution."""
    fake_id = uuid.uuid4()
    response = await client.get(f"/api/executions/{fake_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_latest_execution(client: AsyncClient, db_session):
    """Test getting the latest execution for a workflow."""
    # Create workflow
    workflow = Workflow(name="Test Workflow", description="Test")
    db_session.add(workflow)
    await db_session.flush()
    
    stage = Stage(
        workflow_id=workflow.id,
        name="Test Stage",
        instruction="Test",
        stage_order=1
    )
    db_session.add(stage)
    await db_session.flush()
    
    # Create multiple execution records with different times
    exec_id1 = uuid.uuid4()
    exec_id2 = uuid.uuid4()
    
    record1 = ExecutionRecord(
        workflow_id=workflow.id,
        stage_id=stage.id,
        execution_id=exec_id1,
        status="completed",
        started_at=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, 10, 0, 1, tzinfo=timezone.utc)
    )
    record2 = ExecutionRecord(
        workflow_id=workflow.id,
        stage_id=stage.id,
        execution_id=exec_id2,
        status="completed",
        started_at=datetime(2026, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 2, 10, 0, 1, tzinfo=timezone.utc)
    )
    db_session.add(record1)
    await db_session.flush()
    # Small delay to ensure different created_at
    import asyncio
    await asyncio.sleep(0.01)
    db_session.add(record2)
    await db_session.commit()
    
    # Test get latest endpoint
    response = await client.get(f"/api/workflows/{workflow.id}/executions/latest")
    assert response.status_code == 200
    data = response.json()
    
    # Should return the latest execution (exec_id2 - has later started_at)
    assert str(data["summary"]["execution_id"]) == str(exec_id2)


@pytest.mark.asyncio
async def test_get_latest_execution_not_found(client: AsyncClient, db_session):
    """Test getting latest execution when none exist."""
    # Create workflow without executions
    workflow = Workflow(name="Test Workflow", description="Test")
    db_session.add(workflow)
    await db_session.commit()
    
    response = await client.get(f"/api/workflows/{workflow.id}/executions/latest")
    assert response.status_code == 404
    assert "no executions found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_execution_record_helper_properties(db_session):
    """Test ExecutionRecord helper properties."""
    # Create workflow and stage
    workflow = Workflow(name="Test", description="Test")
    db_session.add(workflow)
    await db_session.flush()
    
    stage = Stage(
        workflow_id=workflow.id,
        name="Test",
        instruction="Test",
        stage_order=1
    )
    db_session.add(stage)
    await db_session.flush()
    
    # Create execution record with timing
    start_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 1, 1, 12, 0, 5, tzinfo=timezone.utc)  # 5 seconds later
    
    record = ExecutionRecord(
        workflow_id=workflow.id,
        stage_id=stage.id,
        execution_id=uuid.uuid4(),
        input_tokens=100,
        output_tokens=50,
        status="completed",
        started_at=start_time,
        completed_at=end_time
    )
    db_session.add(record)
    await db_session.commit()
    
    # Refresh to get latest data
    await db_session.refresh(record)
    
    # Test total_tokens property
    assert record.total_tokens == 150
    
    # Test duration_ms property
    assert record.duration_ms == 5000  # 5 seconds = 5000ms


@pytest.mark.asyncio
async def test_execution_record_nullable_stage_id(db_session):
    """Test that ExecutionRecord can have NULL stage_id."""
    workflow = Workflow(name="Test", description="Test")
    db_session.add(workflow)
    await db_session.flush()
    
    # Create execution record without stage_id
    record = ExecutionRecord(
        workflow_id=workflow.id,
        stage_id=None,  # Should be allowed
        execution_id=uuid.uuid4(),
        status="completed",
        result="Workflow-level execution"
    )
    db_session.add(record)
    await db_session.commit()
    
    # Verify it was saved
    result = await db_session.execute(
        select(ExecutionRecord).where(ExecutionRecord.id == record.id)
    )
    saved_record = result.scalar_one()
    assert saved_record.stage_id is None
    assert saved_record.result == "Workflow-level execution"


@pytest.mark.asyncio
async def test_list_executions_pagination(client: AsyncClient, db_session):
    """Test execution list pagination."""
    # Create workflow
    workflow = Workflow(name="Test", description="Test")
    db_session.add(workflow)
    await db_session.flush()
    
    stage = Stage(
        workflow_id=workflow.id,
        name="Test",
        instruction="Test",
        stage_order=1
    )
    db_session.add(stage)
    await db_session.flush()
    
    # Create multiple executions
    for i in range(5):
        exec_id = uuid.uuid4()
        record = ExecutionRecord(
            workflow_id=workflow.id,
            stage_id=stage.id,
            execution_id=exec_id,
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        db_session.add(record)
    await db_session.commit()
    
    # Test pagination
    response = await client.get("/api/executions?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    response = await client.get("/api/executions?limit=2&offset=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    response = await client.get("/api/executions?limit=2&offset=4")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
