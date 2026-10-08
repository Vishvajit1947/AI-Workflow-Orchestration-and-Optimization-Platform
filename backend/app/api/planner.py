"""
Workflow Planner API endpoints.

Provides intelligent workflow planning from natural language objectives.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.schemas.planner import (
    ObjectiveAnalysisRequest,
    ObjectiveAnalysisResponse,
    WorkflowGenerationRequest,
)
from backend.app.schemas.workflow import WorkflowRead
from backend.app.services.workflow_planner import (
    WorkflowPlanner,
    PlannerLLMError,
    PlannerValidationError,
)
from backend.app.services.workflow_manager import WorkflowManager
from backend.app.services.stage_manager import StageManager


router = APIRouter(prefix="/planner", tags=["Workflow Planner"])


@router.post("/analyze", response_model=ObjectiveAnalysisResponse)
async def analyze_objective(
    request: ObjectiveAnalysisRequest,
    provider: Optional[str] = Query(None, description="LLM provider to use for planning"),
    model: Optional[str] = Query(None, description="Specific model to use for planning"),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze a user's objective and generate a workflow plan.
    
    This endpoint uses an LLM to:
    1. Determine if the objective is simple (1 stage) or complex (multiple stages)
    2. Generate appropriate workflow stages with dependencies
    3. Return a structured plan for user review
    
    The plan can then be edited by the user and submitted to /planner/generate to create
    the actual workflow.
    """
    planner = WorkflowPlanner(db, provider_name=provider, model=model)
    
    try:
        plan = await planner.analyze_objective(request.objective)
        return plan
    except PlannerLLMError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Planning service unavailable: {str(e)}",
        )
    except PlannerValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Generated plan validation failed: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Planning failed: {str(e)}",
        )


@router.post("/generate", response_model=WorkflowRead, status_code=201)
async def generate_workflow_from_plan(
    request: WorkflowGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a complete workflow from an approved plan.
    
    This endpoint:
    1. Takes the user's objective and approved plan (possibly edited)
    2. Creates a workflow record
    3. Creates all stage records with dependencies
    4. Validates the resulting DAG
    5. Returns the workflow ready for execution
    
    The workflow can then be executed via POST /api/workflows/{id}/execute
    """
    workflow_mgr = WorkflowManager(db)
    stage_mgr = StageManager(db)
    plan = request.plan
    
    # Re-validate plan (user may have edited it)
    planner = WorkflowPlanner(db)
    try:
        planner._validate_plan(plan)
    except PlannerValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Plan validation failed: {str(e)}. Please fix the plan and try again.",
        )
    
    # Generate workflow name from objective
    workflow_name = _generate_workflow_name(request.objective, plan.complexity)
    
    # Create workflow
    from backend.app.schemas.workflow import WorkflowCreate
    workflow = await workflow_mgr.create_workflow(
        WorkflowCreate(
            name=workflow_name,
            description=plan.reason,
            objective=request.objective,
        )
    )
    
    # Create stages
    from backend.app.schemas.stage import StageCreate, StageDependencyCreate
    stage_id_map: dict[str, uuid.UUID] = {}  # plan_id -> database_id
    
    for idx, stage_plan in enumerate(plan.stages):
        # Create stage
        stage_data = StageCreate(
            workflow_id=workflow.id,
            name=stage_plan.name,
            instruction=stage_plan.instruction,
            stage_order=idx,
            stage_type=stage_plan.stage_type,
            model_preference=stage_plan.model_preference,
            config={
                "description": stage_plan.description,
                "expected_output": stage_plan.expected_output,
                "planner_generated": True,
            },
            dependencies=[],  # Will add after all stages exist
        )
        
        stage = await stage_mgr.create_stage(stage_data)
        stage_id_map[stage_plan.id] = stage.id
    
    # Add dependencies
    for stage_plan in plan.stages:
        if stage_plan.dependencies:
            stage_db_id = stage_id_map[stage_plan.id]
            for dep_plan_id in stage_plan.dependencies:
                dep_db_id = stage_id_map[dep_plan_id]
                await stage_mgr.add_dependency(
                    stage_db_id,
                    StageDependencyCreate(
                        depends_on_stage_id=dep_db_id,
                        dependency_type="sequential",
                    ),
                )
    
    # Validate the resulting workflow
    from backend.app.utils.validators import validate_workflow
    errors = await validate_workflow(db, workflow.id)
    if errors:
        # Clean up on validation failure
        await workflow_mgr.delete_workflow(workflow.id)
        raise HTTPException(
            status_code=422,
            detail=f"Generated workflow failed validation: {'; '.join(errors)}",
        )
    
    # Reload with stages
    workflow = await workflow_mgr.get_workflow(workflow.id)
    
    return workflow


def _generate_workflow_name(objective: str, complexity: str) -> str:
    """
    Generate a concise workflow name from the objective.
    
    Examples:
        "Design a machine learning pipeline..." → "ML Pipeline Design"
        "Explain binary search" → "Binary Search Explanation"
    """
    # Take first 50 chars of objective
    name = objective[:50].strip()
    
    # Remove trailing punctuation/incomplete words
    if not name.endswith(('.', '!', '?')):
        # Find last complete word
        words = name.split()
        if len(words) > 1 and not objective[len(name):len(name)+1].strip():
            # Last word is complete
            pass
        elif len(words) > 1:
            # Last word is incomplete, remove it
            name = ' '.join(words[:-1])
    
    # Add complexity indicator if complex
    if complexity == "complex" and len(name) < 45:
        name = f"{name} (Multi-Stage)"
    
    # Ensure it's not too long
    if len(name) > 100:
        name = name[:97] + "..."
    
    return name

