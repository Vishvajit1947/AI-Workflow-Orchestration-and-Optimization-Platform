"""
End-to-end test for the Groq-powered Workflow Planner.

Calls the real Groq API, so it is skipped unless GROQ_API_KEY is configured.
Run with:  python -m pytest backend/tests/e2e -c backend/pytest.ini --rootdir backend
or directly: python -m backend.tests.e2e.test_planner_live   (from the repo root)
"""
import asyncio

import pytest

from backend.app.config import settings
from backend.app.database import async_session_factory
from backend.app.services.workflow_planner import WorkflowPlanner

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not settings.GROQ_API_KEY, reason="needs a real GROQ_API_KEY"),
]


async def test_simple_objective():
    """Test simple objective classification."""
    print("\n=== Test 1: Simple Objective ===")
    objective = "Explain what machine learning is."
    
    async with async_session_factory() as db:
        planner = WorkflowPlanner(db)
        result = await planner.analyze_objective(objective)
        
        assert result.complexity == "simple", f"Expected simple, got {result.complexity}"
        assert len(result.stages) == 1, f"Expected 1 stage, got {len(result.stages)}"
        print(f"✓ Complexity: {result.complexity}")
        print(f"✓ Stages: {len(result.stages)}")
        print(f"✓ Reason: {result.reason}")
        return True


async def test_complex_objective():
    """Test complex objective with multiple stages."""
    print("\n=== Test 2: Complex Objective ===")
    objective = "Design a machine learning pipeline for retail demand forecasting."
    
    async with async_session_factory() as db:
        planner = WorkflowPlanner(db)
        result = await planner.analyze_objective(objective)
        
        assert result.complexity == "complex", f"Expected complex, got {result.complexity}"
        assert len(result.stages) >= 3, f"Expected 3+ stages, got {len(result.stages)}"
        
        # Verify stage structure
        stage_ids = [s.id for s in result.stages]
        assert len(stage_ids) == len(set(stage_ids)), "Duplicate stage IDs found"
        
        # Verify dependencies
        for stage in result.stages:
            for dep in stage.dependencies:
                assert dep in stage_ids, f"Invalid dependency: {dep}"
        
        print(f"✓ Complexity: {result.complexity}")
        print(f"✓ Stages: {len(result.stages)}")
        print(f"✓ Stage IDs: {', '.join(stage_ids)}")
        print(f"✓ Reason: {result.reason[:100]}...")
        return True


async def test_groq_provider_used():
    """Verify Groq provider is being used."""
    print("\n=== Test 3: Groq Provider Verification ===")
    
    async with async_session_factory() as db:
        planner = WorkflowPlanner(db)
        provider = planner._get_provider()
        
        assert provider.provider_name == "groq", f"Expected groq, got {provider.provider_name}"
        print(f"✓ Provider: {provider.provider_name}")
        print(f"✓ Default model: {provider.get_default_model()}")
        return True


async def main():
    """Run all tests."""
    print("="*60)
    print("GROQ WORKFLOW PLANNER END-TO-END TEST")
    print("="*60)
    
    results = {}
    
    try:
        results["groq_provider"] = await test_groq_provider_used()
    except Exception as e:
        print(f"✗ FAILED: {e}")
        results["groq_provider"] = False
    
    try:
        results["simple_objective"] = await test_simple_objective()
    except Exception as e:
        print(f"✗ FAILED: {e}")
        results["simple_objective"] = False
    
    try:
        results["complex_objective"] = await test_complex_objective()
    except Exception as e:
        print(f"✗ FAILED: {e}")
        results["complex_objective"] = False
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(results.values())
    print("\n" + ("="*60))
    print(f"OVERALL: {'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")
    print("="*60)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
