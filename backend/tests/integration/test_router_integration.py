"""
Router API tests: /api/models, /api/routing/*, and routing through POST /workflows/{id}/execute.
"""
import pytest
from sqlalchemy import select, func

from backend.app.models import RoutingDecision
from backend.tests.conftest import ALL_PROVIDERS
from backend.tests.integration.test_phase4_integration import make_workflow, stages_of

pytestmark = pytest.mark.integration


# ============================================================================
# /api/models
# ============================================================================

async def test_list_models_marks_routable(client, seeded_models, providers):
    providers("openai")
    response = await client.get("/api/models")
    assert response.status_code == 200
    models = response.json()
    assert len(models) == 8
    routable = {m["model_name"] for m in models if m["routable"]}
    assert routable == {"gpt-4o", "gpt-4o-mini"}


async def test_list_models_filters(client, seeded_models):
    response = await client.get("/api/models", params={"capability": "generation", "min_score": 0.9})
    assert {m["model_name"] for m in response.json()} == {"gpt-4o", "claude-sonnet-4-20250514", "gemini-2.0-flash-exp"}

    response = await client.get("/api/models", params={"provider": "groq"})
    assert len(response.json()) == 2


async def test_compare_models(client, seeded_models):
    body = (await client.get("/api/models/compare")).json()
    assert body["cheapest"] == "gemini-2.0-flash-exp"
    assert body["fastest"] == "llama-3.1-8b-instant"
    assert body["most_capable"]["generation"] == "claude-sonnet-4-20250514"
    assert body["most_capable"]["reasoning"] == "gpt-4o"


async def test_get_and_patch_model(client, seeded_models):
    response = await client.get("/api/models/openai/gpt-4o")
    assert response.status_code == 200
    assert response.json()["display_name"] == "GPT-4o"
    assert (await client.get("/api/models/openai/nope")).status_code == 404

    response = await client.patch("/api/models/openai/gpt-4o", json={"is_available": False})
    assert response.json()["is_available"] is False
    names = {m["model_name"] for m in (await client.get("/api/models")).json()}
    assert "gpt-4o" not in names
    names = {m["model_name"] for m in (await client.get("/api/models", params={"include_unavailable": True})).json()}
    assert "gpt-4o" in names


# ============================================================================
# /api/routing/rules
# ============================================================================

async def test_routing_rules_crud(client, seeded_models):
    mini_id = (await client.get("/api/models/openai/gpt-4o-mini")).json()["id"]

    response = await client.post("/api/routing/rules", json={
        "stage_type": "analysis", "priority_factor": "speed", "fallback_model_id": mini_id,
    })
    assert response.status_code == 201
    rule = response.json()
    assert rule["priority_factor"] == "speed"
    assert rule["fallback_model"]["model_name"] == "gpt-4o-mini"

    assert (await client.post("/api/routing/rules", json={"stage_type": "analysis"})).status_code == 409

    response = await client.put("/api/routing/rules/analysis", json={"priority_factor": "cost", "fallback_model_id": None})
    assert response.status_code == 200
    assert response.json()["priority_factor"] == "cost"
    assert response.json()["fallback_model"] is None

    assert len((await client.get("/api/routing/rules")).json()) == 1
    assert (await client.delete("/api/routing/rules/analysis")).status_code == 200
    assert (await client.get("/api/routing/rules/analysis")).status_code == 404


async def test_routing_rule_validation(client, seeded_models):
    bad_priority = await client.post("/api/routing/rules", json={"stage_type": "design", "priority_factor": "fastest"})
    assert bad_priority.status_code == 422
    unknown_model = await client.post("/api/routing/rules", json={
        "stage_type": "design", "preferred_model_id": "00000000-0000-0000-0000-000000000000",
    })
    assert unknown_model.status_code == 422
    assert (await client.put("/api/routing/rules/missing", json={"priority_factor": "cost"})).status_code == 404


# ============================================================================
# Routing via the execute endpoint
# ============================================================================

async def test_execute_endpoint_routes_and_reports(client, seeded_routing_rules, providers):
    db = seeded_routing_rules
    providers(*ALL_PROVIDERS)
    workflow = await make_workflow(db, ("Analyze", "analysis"), ("Code", "generation"))
    first, _ = await stages_of(db, workflow)

    response = await client.post(f"/api/workflows/{workflow.id}/execute", json={
        "use_cache": False,
        "routing_preferences": {str(first.id): "claude-3-5-haiku-20241022"},
    })
    assert response.status_code == 200, response.text
    execution_id = response.json()["execution_id"]

    stages = (await client.get(f"/api/executions/{execution_id}")).json()["stages"]
    assert stages[0]["model_used"] == "claude-3-5-haiku-20241022"
    assert stages[0]["was_routed"] and stages[0]["was_user_override"]
    assert stages[1]["model_used"] == "claude-sonnet-4-20250514"
    assert stages[1]["was_routed"] and not stages[1]["was_user_override"]
    assert "quality" in stages[1]["routing_reason"]

    decisions = (await client.get("/api/routing/decisions", params={"execution_id": execution_id})).json()
    assert {d["selected_model_name"] for d in decisions} == {"claude-3-5-haiku-20241022", "claude-sonnet-4-20250514"}


async def test_preview_does_not_log_decisions(client, seeded_routing_rules, providers):
    db = seeded_routing_rules
    providers("openai", "anthropic")
    workflow = await make_workflow(db, ("Code", "generation"), ("Tests", "testing"))

    response = await client.get(f"/api/routing/preview/{workflow.id}")
    assert response.status_code == 200
    assert [p["model_name"] for p in response.json()] == ["claude-sonnet-4-20250514", "gpt-4o-mini"]

    count = await db.scalar(select(func.count()).select_from(RoutingDecision))
    assert count == 0
    assert (await client.get("/api/routing/preview/00000000-0000-0000-0000-000000000000")).status_code == 404
