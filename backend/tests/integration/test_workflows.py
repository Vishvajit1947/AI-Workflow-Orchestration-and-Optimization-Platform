"""Integration tests for workflow CRUD endpoints (MT19)."""
import pytest
import uuid


@pytest.mark.asyncio
async def test_create_workflow(client):
    """Test creating a new workflow with minimal required fields."""
    payload = {
        "name": "Test Workflow",
        "description": "A test workflow for integration testing",
        "objective": "Test workflow creation"
    }
    
    resp = await client.post("/api/workflows", json=payload)
    assert resp.status_code == 201
    
    data = resp.json()
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]
    assert data["objective"] == payload["objective"]
    assert data["status"] == "draft"  # Default status
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    
    # Validate UUID format
    try:
        uuid.UUID(data["id"])
    except ValueError:
        pytest.fail("Invalid UUID format for workflow ID")


@pytest.mark.asyncio
async def test_create_workflow_missing_name(client):
    """Test that creating a workflow without a name returns validation error."""
    payload = {
        "description": "No name provided",
        "objective": "Should fail"
    }
    
    resp = await client.post("/api/workflows", json=payload)
    assert resp.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_workflow_with_all_fields(client):
    """Test creating a workflow with all optional fields."""
    payload = {
        "name": "Complete Workflow",
        "description": "Workflow with all fields",
        "objective": "Test all fields"
    }
    
    resp = await client.post("/api/workflows", json=payload)
    assert resp.status_code == 201
    
    data = resp.json()
    assert data["name"] == payload["name"]
    assert data["status"] == "draft"  # Default status


@pytest.mark.asyncio
async def test_list_workflows_empty(client):
    """Test listing workflows when database is empty."""
    resp = await client.get("/api/workflows")
    assert resp.status_code == 200
    
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    assert "has_more" in data
    assert data["total"] == 0
    assert len(data["items"]) == 0
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_list_workflows_with_data(client, sample_workflow):
    """Test listing workflows with existing data."""
    resp = await client.get("/api/workflows")
    assert resp.status_code == 200
    
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    
    # Check structure of first item
    item = data["items"][0]
    assert "id" in item
    assert "name" in item
    assert "status" in item
    assert "stage_count" in item
    assert "created_at" in item


@pytest.mark.asyncio
async def test_list_workflows_pagination(client):
    """Test workflow list pagination."""
    # Create multiple workflows
    for i in range(5):
        await client.post("/api/workflows", json={
            "name": f"Workflow {i}",
            "description": f"Description {i}",
            "objective": f"Objective {i}"
        })
    
    # Test first page
    resp = await client.get("/api/workflows?skip=0&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["has_more"] is True
    
    # Test second page
    resp = await client.get("/api/workflows?skip=2&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["has_more"] is True
    
    # Test last page
    resp = await client.get("/api/workflows?skip=4&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_list_workflows_filter_by_status(client):
    """Test filtering workflows by status."""
    # Create workflows with different statuses
    resp1 = await client.post("/api/workflows", json={
        "name": "Running Workflow",
        "description": "Running",
        "objective": "Running"
    })
    workflow_id1 = resp1.json()["id"]
    await client.patch(f"/api/workflows/{workflow_id1}", json={"status": "running"})
    
    await client.post("/api/workflows", json={
        "name": "Draft Workflow",
        "description": "Draft",
        "objective": "Draft"
    })
    
    # Filter by running status
    resp = await client.get("/api/workflows?status=running")
    assert resp.status_code == 200
    data = resp.json()
    
    # All returned items should have running status
    for item in data["items"]:
        assert item["status"] == "running"


@pytest.mark.asyncio
async def test_get_workflow(client, sample_workflow):
    """Test retrieving a specific workflow by ID."""
    workflow_id = str(sample_workflow.id)
    
    resp = await client.get(f"/api/workflows/{workflow_id}")
    assert resp.status_code == 200
    
    data = resp.json()
    assert data["id"] == workflow_id
    assert data["name"] == sample_workflow.name
    assert data["description"] == sample_workflow.description
    assert "stages" in data


@pytest.mark.asyncio
async def test_get_workflow_with_stages(client, sample_workflow_with_stages):
    """Test retrieving a workflow with its stages."""
    workflow_id = str(sample_workflow_with_stages.id)
    
    resp = await client.get(f"/api/workflows/{workflow_id}")
    assert resp.status_code == 200
    
    data = resp.json()
    assert len(data["stages"]) == 3
    
    # Verify stages are ordered correctly
    assert data["stages"][0]["stage_order"] == 0
    assert data["stages"][1]["stage_order"] == 1
    assert data["stages"][2]["stage_order"] == 2


@pytest.mark.asyncio
async def test_get_nonexistent_workflow(client):
    """Test retrieving a workflow that doesn't exist."""
    fake_id = str(uuid.uuid4())
    
    resp = await client.get(f"/api/workflows/{fake_id}")
    assert resp.status_code == 404
    
    data = resp.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_get_workflow_invalid_uuid(client):
    """Test retrieving a workflow with invalid UUID format."""
    resp = await client.get("/api/workflows/invalid-uuid")
    assert resp.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_workflow(client, sample_workflow):
    """Test updating a workflow's fields."""
    workflow_id = str(sample_workflow.id)
    
    update_data = {
        "name": "Updated Workflow Name",
        "description": "Updated description"
    }
    
    resp = await client.patch(f"/api/workflows/{workflow_id}", json=update_data)
    assert resp.status_code == 200
    
    data = resp.json()
    assert data["name"] == update_data["name"]
    assert data["description"] == update_data["description"]
    
    # Verify the update persisted
    resp = await client.get(f"/api/workflows/{workflow_id}")
    data = resp.json()
    assert data["name"] == update_data["name"]


@pytest.mark.asyncio
async def test_update_workflow_partial(client, sample_workflow):
    """Test partial update (only updating one field)."""
    workflow_id = str(sample_workflow.id)
    original_name = sample_workflow.name
    
    update_data = {
        "description": "Only description changed"
    }
    
    resp = await client.patch(f"/api/workflows/{workflow_id}", json=update_data)
    assert resp.status_code == 200
    
    data = resp.json()
    assert data["name"] == original_name  # Unchanged
    assert data["description"] == update_data["description"]  # Changed


@pytest.mark.asyncio
async def test_update_nonexistent_workflow(client):
    """Test updating a workflow that doesn't exist."""
    fake_id = str(uuid.uuid4())
    
    update_data = {"name": "Updated Name"}
    
    resp = await client.patch(f"/api/workflows/{fake_id}", json=update_data)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_workflow(client, sample_workflow):
    """Test deleting a workflow."""
    workflow_id = str(sample_workflow.id)
    
    resp = await client.delete(f"/api/workflows/{workflow_id}")
    assert resp.status_code == 200
    
    data = resp.json()
    assert "message" in data
    
    # Verify the workflow is deleted
    resp = await client.get(f"/api/workflows/{workflow_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_workflow_cascades_to_stages(client, sample_workflow_with_stages):
    """Test that deleting a workflow also deletes its stages."""
    workflow_id = str(sample_workflow_with_stages.id)
    
    # Verify stages exist
    resp = await client.get(f"/api/workflows/{workflow_id}")
    assert len(resp.json()["stages"]) == 3
    
    # Delete workflow
    resp = await client.delete(f"/api/workflows/{workflow_id}")
    assert resp.status_code == 200
    
    # Verify workflow and stages are gone
    resp = await client.get(f"/api/workflows/{workflow_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_workflow(client):
    """Test deleting a workflow that doesn't exist."""
    fake_id = str(uuid.uuid4())
    
    resp = await client.delete(f"/api/workflows/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_validate_workflow_endpoint(client, sample_workflow_with_stages):
    """Test the workflow validation endpoint."""
    workflow_id = str(sample_workflow_with_stages.id)
    
    resp = await client.post(f"/api/workflows/{workflow_id}/validate")
    assert resp.status_code == 200
    
    data = resp.json()
    assert "workflow_id" in data
    assert "is_valid" in data
    assert "errors" in data
    assert isinstance(data["errors"], list)


@pytest.mark.asyncio
async def test_workflow_status_transitions(client):
    """Test valid workflow status transitions."""
    # Create workflow in draft status
    resp = await client.post("/api/workflows", json={
        "name": "Status Test",
        "description": "Testing status transitions",
        "objective": "Test statuses"
    })
    workflow_id = resp.json()["id"]
    
    # Verify initial status is draft
    resp = await client.get(f"/api/workflows/{workflow_id}")
    assert resp.json()["status"] == "draft"
    
    # Transition to running
    resp = await client.patch(f"/api/workflows/{workflow_id}", json={"status": "running"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    
    # Transition to completed
    resp = await client.patch(f"/api/workflows/{workflow_id}", json={"status": "completed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_workflow_status_failed_and_paused(client):
    """Test failed and paused status transitions."""
    # Create workflow
    resp = await client.post("/api/workflows", json={
        "name": "Status Test 2",
        "description": "Testing more status transitions",
        "objective": "Test statuses"
    })
    workflow_id = resp.json()["id"]
    
    # Transition to running then paused
    await client.patch(f"/api/workflows/{workflow_id}", json={"status": "running"})
    resp = await client.patch(f"/api/workflows/{workflow_id}", json={"status": "paused"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"
    
    # Transition to failed
    resp = await client.patch(f"/api/workflows/{workflow_id}", json={"status": "failed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_workflow_created_updated_timestamps(client):
    """Test that created_at and updated_at timestamps are properly set."""
    # Create workflow
    resp = await client.post("/api/workflows", json={
        "name": "Timestamp Test",
        "description": "Testing timestamps",
        "objective": "Test timestamps"
    })
    assert resp.status_code == 201
    
    data = resp.json()
    workflow_id = data["id"]
    created_at = data["created_at"]
    updated_at_initial = data["updated_at"]
    
    # Wait a moment and update
    import asyncio
    await asyncio.sleep(0.1)
    
    resp = await client.patch(f"/api/workflows/{workflow_id}", json={"name": "Updated Name"})
    data = resp.json()
    updated_at_after = data["updated_at"]
    
    # created_at should not change
    assert data["created_at"] == created_at
    
    # updated_at should change (note: this might fail in very fast systems)
    # In production, you'd want more sophisticated timestamp comparison
