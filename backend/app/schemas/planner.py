"""
Pydantic schemas for Workflow Planner.

The planner analyzes user objectives and generates workflow plans.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ObjectiveAnalysisRequest(BaseModel):
    """Request to analyze a user's objective."""
    objective: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        examples=["Design a machine learning pipeline for retail demand forecasting."],
        description="The user's high-level objective or goal",
    )


class StagePlan(BaseModel):
    """A planned workflow stage."""
    id: str = Field(
        ...,
        pattern="^[a-z][a-z0-9_]{0,63}$",
        examples=["requirements", "architecture", "implementation"],
        description="Unique stage identifier (lowercase, underscores, alphanumeric)",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["Requirements Analysis", "System Architecture"],
        description="Human-readable stage name",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        examples=["Analyze project requirements and define clear specifications."],
        description="What this stage accomplishes",
    )
    instruction: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        examples=[
            "Analyze the user's objective and produce a structured requirements document with functional and non-functional requirements."
        ],
        description="Detailed instruction for the LLM executing this stage",
    )
    stage_type: str = Field(
        ...,
        pattern="^(analysis|design|generation|testing|documentation|review|custom)$",
        examples=["analysis", "design", "generation"],
        description="Type of stage (determines routing and model selection)",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        examples=[["requirements"], ["architecture", "database_design"]],
        description="List of stage IDs this stage depends on (must complete first)",
    )
    expected_output: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        examples=["A structured requirements document with priorities and constraints."],
        description="What output this stage should produce",
    )
    model_preference: Optional[str] = Field(
        None,
        examples=["gpt-4o", "gemini-2.5-pro"],
        description="Optional preferred model for this stage",
    )


class ObjectiveAnalysisResponse(BaseModel):
    """Response from analyzing an objective."""
    complexity: Literal["simple", "complex"] = Field(
        ...,
        examples=["complex"],
        description="Whether the objective requires decomposition",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        examples=[
            "This objective involves multiple dependent tasks: requirements, design, implementation, and testing."
        ],
        description="Why this complexity was chosen",
    )
    stages: list[StagePlan] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Planned workflow stages (1 for simple, multiple for complex)",
    )
    estimated_duration_minutes: Optional[int] = Field(
        None,
        ge=1,
        le=1440,
        examples=[30, 120],
        description="Estimated total execution time",
    )


class WorkflowGenerationRequest(BaseModel):
    """Request to generate a workflow from an approved plan."""
    objective: str = Field(..., min_length=10, max_length=5000)
    plan: ObjectiveAnalysisResponse = Field(
        ...,
        description="The approved plan (may have been edited by user)",
    )
    auto_execute: bool = Field(
        default=False,
        description="Whether to immediately execute after creation",
    )

