"""
Intelligent Workflow Planner.

Uses LLMs to analyze user objectives and generate structured workflow plans.
The planner ONLY generates plans — execution is handled by the existing ExecutionEngine.
"""

import json
import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.llm import registry
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse
from backend.app.schemas.planner import ObjectiveAnalysisResponse, StagePlan


# System prompt for the planner LLM
PLANNER_SYSTEM_PROMPT = """You are an intelligent workflow planning engine for an AI orchestration platform.

Your task: Analyze a user's high-level objective and determine if it should be completed as one task or decomposed into multiple stages.

RULES:
1. Classify as "simple" if the objective can be completed in one step (exactly 1 stage).
2. Classify as "complex" if the objective requires multiple dependent stages (generate 3-5 essential stages).
3. Keep descriptions, instructions, and outputs compact and concise (1-2 sentences each, 15-60 words). Do NOT generate lengthy explanations.
4. Each stage must have a clear objective and valid dependencies (data flow, sequence requirements).
5. Use these stage_types: analysis, design, generation, testing, documentation, review, custom
6. Stage IDs must be lowercase with underscores (e.g., "problem_definition", "data_prep").
7. Dependencies must only reference preceding stage IDs defined earlier in the stages list.
8. DO NOT create circular dependencies or self-dependencies.
9. Set model_preference to null.

EXAMPLES:

Simple objective:
"Explain binary search in Python"
→ complexity: simple, reason: "Single explanatory task", stages: 1

Complex objective:
"Design a machine learning pipeline for retail demand forecasting"
→ complexity: complex, reason: "Requires multiple dependent stages", stages: 3-5 stages (e.g. data_prep -> feature_engineering -> model_training -> evaluation)

SCHEMA (respond with ONLY valid JSON matching this schema):
{
  "complexity": "simple" | "complex",
  "reason": "Brief reason for classification (10-200 chars)",
  "stages": [
    {
      "id": "stage_id",
      "name": "Stage Name",
      "description": "Brief summary of stage goal (10-200 chars)",
      "instruction": "Concise instruction for execution (10-300 chars)",
      "stage_type": "analysis" | "design" | "generation" | "testing" | "documentation" | "review" | "custom",
      "dependencies": ["stage_id1"],
      "expected_output": "Brief expected deliverable (10-200 chars)",
      "model_preference": null
    }
  ],
  "estimated_duration_minutes": number
}

CRITICAL: Return ONLY valid JSON. No markdown formatting, no code fences, no commentary outside the JSON."""


class WorkflowPlannerError(Exception):
    """Base exception for planner errors."""
    pass


class PlannerLLMError(WorkflowPlannerError):
    """LLM call failed."""
    pass


class PlannerValidationError(WorkflowPlannerError):
    """Generated plan failed validation."""
    pass


class WorkflowPlanner:
    """
    Intelligent workflow planner that analyzes objectives and generates structured plans.
    
    This planner ONLY generates workflow definitions. Execution is handled by the
    existing ExecutionEngine.
    """

    def __init__(self, db: AsyncSession, provider_name: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the planner.
        
        Args:
            db: Database session (for future use with planner history/analytics)
            provider_name: Optional LLM provider to use (default: first available)
            model: Optional specific model to use
        """
        self.db = db
        self.provider_name = provider_name
        self.model = model

    def _get_provider(self) -> BaseLLMProvider:
        """Get an available LLM provider for planning."""
        available = registry.list_providers()
        if not available:
            raise PlannerLLMError("No LLM providers available. Configure at least one API key.")
        
        if self.provider_name:
            if self.provider_name not in available:
                raise PlannerLLMError(
                    f"Provider '{self.provider_name}' not available. Available: {available}"
                )
            return registry.get(self.provider_name)
        
        # Use first available provider (Groq preferred for demo reliability)
        # Prefer order: groq (fast, reliable), gemini (free), openai, anthropic
        preference = ["groq", "gemini", "openai", "anthropic"]
        for pref in preference:
            if pref in available:
                return registry.get(pref)
        
        return registry.get(available[0])

    async def analyze_objective(self, objective: str) -> ObjectiveAnalysisResponse:
        """
        Analyze a user's objective and generate a workflow plan.
        
        Args:
            objective: User's high-level goal
            
        Returns:
            ObjectiveAnalysisResponse with complexity, reason, and stages
            
        Raises:
            PlannerLLMError: If LLM call fails
            PlannerValidationError: If generated plan is invalid
        """
        provider = self._get_provider()
        
        # Construct user prompt
        user_prompt = f"""Analyze this objective and generate a compact workflow plan:

OBJECTIVE:
{objective.strip()}

Remember:
- Keep all fields compact and concise (1-2 sentences each) so output fits within 800 tokens.
- For complex objectives, create 3-5 logical stages.
- Respond with ONLY valid raw JSON (no markdown formatting, no code blocks)."""

        # Call LLM
        try:
            response: LLMResponse = await provider.generate(
                prompt=user_prompt,
                model=self.model,
                temperature=0.3,  # Lower temperature for more consistent structure
                max_tokens=800,  # Strictly fit within Groq free tier limit (1000 OTPM)
                system_prompt=PLANNER_SYSTEM_PROMPT,
            )
        except Exception as e:
            raise PlannerLLMError(f"LLM call failed: {str(e)}") from e

        # Parse response
        content = response.content.strip()
        
        # Remove markdown code blocks if present (despite instructions)
        content = re.sub(r'^```(?:json)?\s*\n', '', content)
        content = re.sub(r'\n```\s*$', '', content)
        content = content.strip()
        
        # Parse JSON
        try:
            plan_dict = json.loads(content)
        except json.JSONDecodeError as e:
            raise PlannerValidationError(
                f"LLM response was not valid JSON: {str(e)}\nResponse: {content[:500]}"
            ) from e

        # Validate and construct response
        try:
            plan = ObjectiveAnalysisResponse(**plan_dict)
        except Exception as e:
            raise PlannerValidationError(
                f"LLM response did not match expected schema: {str(e)}\nResponse: {plan_dict}"
            ) from e

        # Additional validation
        self._validate_plan(plan)
        
        return plan

    def _validate_plan(self, plan: ObjectiveAnalysisResponse) -> None:
        """
        Validate a generated plan for correctness.
        
        Raises:
            PlannerValidationError: If plan is invalid
        """
        # Check stage count
        if plan.complexity == "simple" and len(plan.stages) > 1:
            raise PlannerValidationError(
                f"Simple complexity should have 1 stage, got {len(plan.stages)}"
            )
        
        if plan.complexity == "complex" and len(plan.stages) < 2:
            raise PlannerValidationError(
                f"Complex complexity should have multiple stages, got {len(plan.stages)}"
            )
        
        # Check for duplicate stage IDs
        stage_ids = [s.id for s in plan.stages]
        if len(stage_ids) != len(set(stage_ids)):
            duplicates = [sid for sid in stage_ids if stage_ids.count(sid) > 1]
            raise PlannerValidationError(f"Duplicate stage IDs: {duplicates}")
        
        # Check dependencies reference valid stages
        valid_ids = set(stage_ids)
        for stage in plan.stages:
            for dep_id in stage.dependencies:
                if dep_id not in valid_ids:
                    raise PlannerValidationError(
                        f"Stage '{stage.id}' depends on non-existent stage '{dep_id}'"
                    )
        
        # Check for circular dependencies
        cycle = self._detect_cycle(plan.stages)
        if cycle:
            raise PlannerValidationError(f"Circular dependency detected: {' → '.join(cycle)}")
        
        # Check for self-dependencies
        for stage in plan.stages:
            if stage.id in stage.dependencies:
                raise PlannerValidationError(f"Stage '{stage.id}' depends on itself")

    def _detect_cycle(self, stages: list[StagePlan]) -> Optional[list[str]]:
        """
        Detect cycles in stage dependencies using DFS.
        
        Returns:
            List of stage IDs in the cycle, or None if no cycle
        """
        # Build adjacency list
        graph: dict[str, list[str]] = {stage.id: stage.dependencies for stage in stages}
        
        # DFS with colors
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {sid: WHITE for sid in graph}
        parent = {sid: None for sid in graph}
        
        def dfs(node: str) -> Optional[list[str]]:
            color[node] = GRAY
            for neighbor in graph.get(node, []):
                if color[neighbor] == GRAY:
                    # Found cycle
                    cycle = [neighbor, node]
                    current = node
                    while parent.get(current) != neighbor and parent.get(current) is not None:
                        current = parent[current]
                        cycle.append(current)
                    return cycle
                elif color[neighbor] == WHITE:
                    parent[neighbor] = node
                    result = dfs(neighbor)
                    if result:
                        return result
            color[node] = BLACK
            return None
        
        for node_id in graph:
            if color[node_id] == WHITE:
                cycle = dfs(node_id)
                if cycle:
                    return cycle
        
        return None

