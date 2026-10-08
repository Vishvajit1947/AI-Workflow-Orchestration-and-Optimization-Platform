"""
Phase 4 Integration Tests — Stage-Aware Routing.

Covers the model registry, the routing engine (priorities, overrides, constraints,
fallbacks, decision logging) and routing inside real workflow executions.
LLM calls go to StubProviders registered under the real provider names.
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, func

from backend.app.models import Workflow, Stage, ExecutionRecord, ModelProfile, RoutingDecision
from backend.app.services.execution import ExecutionEngine
from backend.app.services.router.model_registry import (
    ModelRegistry, SEED_MODELS, capability_for_stage_type, seed_model_profiles,
)
from backend.app.services.router.routing_engine import RoutingEngine
from backend.app.services.router.routing_rules import RoutingRulesManager

from backend.tests.conftest import ALL_PROVIDERS

pytestmark = pytest.mark.integration


async def make_workflow(db, *stages: tuple[str, str | None], **stage_kwargs) -> Workflow:
    """Workflow with one stage per (name, stage_type), in order."""
    workflow = Workflow(name="Routing Test", objective="Exercise the router")
    db.add(workflow)
    await db.flush()
    for order, (name, stage_type) in enumerate(stages):
        db.add(Stage(workflow_id=workflow.id, name=name, instruction=f"Do {name}",
                     stage_order=order, stage_type=stage_type, **stage_kwargs))
    await db.commit()
    return workflow


async def stages_of(db, workflow: Workflow) -> list[Stage]:
    result = await db.execute(select(Stage).where(Stage.workflow_id == workflow.id).order_by(Stage.stage_order))
    return list(result.scalars().all())


async def decisions_for(db, execution_id: uuid.UUID) -> list[RoutingDecision]:
    result = await db.execute(
        select(RoutingDecision).where(RoutingDecision.execution_id == execution_id)
        .order_by(RoutingDecision.created_at)
    )
    return list(result.scalars().all())


async def route(db, stage: Stage, providers=ALL_PROVIDERS, **kwargs):
    return await RoutingEngine(db, available_providers=providers).select_model_for_stage(stage, uuid.uuid4(), **kwargs)


# ============================================================================
# Model Registry
# ============================================================================

async def test_seed_registers_all_models_idempotently(seeded_models):
    db = seeded_models
    await seed_model_profiles(db)  # second seed adds nothing

    models = await ModelRegistry(db).list_models()
    assert len(models) == len(SEED_MODELS) == 8
    assert {m.provider for m in models} == set(ALL_PROVIDERS)

    mini = await ModelRegistry(db).get_model("openai", "gpt-4o-mini")
    assert mini.display_name == "GPT-4o Mini"
    assert mini.cost_per_input_token == Decimal("0.00000015")
    assert mini.estimate_cost(1000, 500) == Decimal("0.00045")


async def test_seed_keeps_user_edits(seeded_models):
    db = seeded_models
    model = await ModelRegistry(db).get_model("openai", "gpt-4o")
    model.is_available = False
    await db.commit()

    await seed_model_profiles(db)
    await db.refresh(model)
    assert model.is_available is False
    assert "gpt-4o" not in [m.model_name for m in await ModelRegistry(db).list_models()]


async def test_registry_cheapest_and_fastest(seeded_models):
    registry = ModelRegistry(seeded_models)
    assert (await registry.get_cheapest_model()).model_name == "gemini-2.0-flash-exp"
    assert (await registry.get_fastest_model()).model_name == "llama-3.1-8b-instant"
    # The 8B model scores too low for analysis, so the 70B one is the fastest capable model
    assert (await registry.get_fastest_model("analysis", min_score=0.8)).model_name == "llama-3.3-70b-versatile"


async def test_registry_capability_filtering(seeded_models):
    models = await ModelRegistry(seeded_models).get_models_for_capability("generation", min_score=0.90)
    assert {m.model_name for m in models} == {"gpt-4o", "claude-sonnet-4-20250514", "gemini-2.0-flash-exp"}


def test_capability_for_stage_type():
    assert capability_for_stage_type("generation") == "generation"
    assert capability_for_stage_type("custom") == "reasoning"
    assert capability_for_stage_type(None) == "reasoning"


# ============================================================================
# Routing Engine: priorities and constraints
# ============================================================================

async def test_quality_priority_picks_most_capable(seeded_routing_rules):
    db = seeded_routing_rules
    [stage] = await stages_of(db, await make_workflow(db, ("Code", "generation")))
    model, reason = await route(db, stage)
    assert model.model_name == "claude-sonnet-4-20250514"
    assert "quality" in reason


async def test_cost_priority_picks_cheapest_within_budget(seeded_routing_rules):
    db = seeded_routing_rules
    [stage] = await stages_of(db, await make_workflow(db, ("Tests", "testing")))

    model, _ = await route(db, stage)
    assert model.model_name == "gemini-2.0-flash-exp"  # free

    # Without Gemini configured, the cheapest remaining candidate wins
    model, _ = await route(db, stage, providers={"openai", "anthropic"})
    assert model.model_name == "gpt-4o-mini"


async def test_speed_priority_picks_fastest_capable(seeded_routing_rules):
    db = seeded_routing_rules
    [stage] = await stages_of(db, await make_workflow(db, ("Misc", "custom")))
    model, reason = await route(db, stage)
    assert model.model_name == "llama-3.3-70b-versatile"  # 8B is faster but below min score
    assert "speed" in reason


async def test_balanced_priority_weighs_capability_cost_and_speed(seeded_routing_rules):
    db = seeded_routing_rules
    [stage] = await stages_of(db, await make_workflow(db, ("Analyze", "analysis")))
    engine = RoutingEngine(db, available_providers=ALL_PROVIDERS)
    model, _ = await engine.select_model_for_stage(stage, uuid.uuid4())

    # Free, fast and capable beats the top-scoring but expensive, slow models
    assert model.model_name == "gemini-2.0-flash-exp"
    alternatives = engine.last_decision.alternatives_considered
    assert len(alternatives) == 7  # every model except the 8B clears min score 0.85
    assert all(a["score"] >= 0.85 for a in alternatives)


async def test_max_cost_and_latency_constraints_filter_candidates(seeded_models):
    db = seeded_models
    await RoutingRulesManager(db).create_rule(
        stage_type="review", priority_factor="quality",
        min_capability_score=0.80, max_latency_ms=1000, max_cost_per_call=0.003,
    )
    await db.commit()
    [stage] = await stages_of(db, await make_workflow(db, ("Review", "review")))

    engine = RoutingEngine(db, available_providers=ALL_PROVIDERS)
    model, _ = await engine.select_model_for_stage(stage, uuid.uuid4())
    considered = {a["model"] for a in engine.last_decision.alternatives_considered}
    # Sonnet/GPT-4o/Gemini Pro are too slow or too expensive
    assert considered == {"gpt-4o-mini", "claude-3-5-haiku-20241022", "gemini-2.0-flash-exp", "llama-3.3-70b-versatile"}
    assert model.model_name == "gemini-2.0-flash-exp"  # best review score (0.87) among them


async def test_only_configured_providers_are_routed(seeded_routing_rules):
    db = seeded_routing_rules
    [stage] = await stages_of(db, await make_workflow(db, ("Code", "generation")))
    model, _ = await route(db, stage, providers={"groq"})
    assert model.provider == "groq"


async def test_unavailable_models_are_skipped(seeded_routing_rules):
    db = seeded_routing_rules
    sonnet = await ModelRegistry(db).get_model("anthropic", "claude-sonnet-4-20250514")
    sonnet.is_available = False
    await db.commit()

    [stage] = await stages_of(db, await make_workflow(db, ("Code", "generation")))
    model, _ = await route(db, stage)
    assert model.model_name == "gpt-4o"  # next best generation score


# ============================================================================
# Routing Engine: overrides, preferences, preferred models
# ============================================================================

async def test_user_override_beats_stage_preference_and_rules(seeded_routing_rules):
    db = seeded_routing_rules
    [stage] = await stages_of(db, await make_workflow(db, ("Code", "generation"), model_preference="gpt-4o"))
    engine = RoutingEngine(db, available_providers=ALL_PROVIDERS)
    model, reason = await engine.select_model_for_stage(stage, uuid.uuid4(), user_override="claude-3-5-haiku-20241022")

    assert model.model_name == "claude-3-5-haiku-20241022"
    assert "override" in reason.lower()
    assert engine.last_decision.was_user_override is True


async def test_stage_preference_beats_rules(seeded_routing_rules):
    db = seeded_routing_rules
    [stage] = await stages_of(db, await make_workflow(db, ("Code", "generation"), model_preference="gpt-4o-mini"))
    model, reason = await route(db, stage)
    assert model.model_name == "gpt-4o-mini"
    assert "preference" in reason.lower()


async def test_unroutable_override_falls_through_to_rules(seeded_routing_rules):
    db = seeded_routing_rules
    [stage] = await stages_of(db, await make_workflow(db, ("Code", "generation")))
    # Override names an unknown model, preference names a model whose provider isn't configured
    stage.model_preference = "gemini-1.5-pro"
    model, _ = await route(db, stage, providers={"openai", "anthropic"}, user_override="no-such-model")
    assert model.model_name == "claude-sonnet-4-20250514"


async def test_rule_preferred_model_is_used(seeded_models):
    db = seeded_models
    haiku = await ModelRegistry(db).get_model("anthropic", "claude-3-5-haiku-20241022")
    await RoutingRulesManager(db).create_rule(stage_type="design", preferred_model_id=haiku.id)
    await db.commit()
    [stage] = await stages_of(db, await make_workflow(db, ("Design", "design")))

    model, reason = await route(db, stage)
    assert model.id == haiku.id
    assert "preferred" in reason

    # Preferred model's provider not configured: normal routing instead
    model, _ = await route(db, stage, providers={"openai"})
    assert model.provider == "openai"


async def test_inactive_rule_is_ignored(seeded_models):
    db = seeded_models
    await RoutingRulesManager(db).create_rule(stage_type="testing", priority_factor="quality", is_active=False)
    await db.commit()
    [stage] = await stages_of(db, await make_workflow(db, ("Tests", "testing")))
    _, reason = await route(db, stage)
    assert "balanced" in reason  # default priority, not the inactive rule's "quality"


# ============================================================================
# Routing Engine: fallbacks and logging
# ============================================================================

async def test_fallback_to_rule_fallback_model(seeded_models):
    db = seeded_models
    mini = await ModelRegistry(db).get_model("openai", "gpt-4o-mini")
    await RoutingRulesManager(db).create_rule(
        stage_type="analysis", priority_factor="cost",
        max_cost_per_call=0.0, min_capability_score=0.99, fallback_model_id=mini.id,
    )
    await db.commit()
    [stage] = await stages_of(db, await make_workflow(db, ("Analyze", "analysis")))

    engine = RoutingEngine(db, available_providers=ALL_PROVIDERS)
    model, reason = await engine.select_model_for_stage(stage, uuid.uuid4())
    assert model.id == mini.id
    assert "fallback" in reason.lower()
    assert engine.last_decision.was_fallback is True


async def test_fallback_without_rule_fallback_uses_most_capable(seeded_models):
    db = seeded_models
    await RoutingRulesManager(db).create_rule(stage_type="analysis", min_capability_score=0.99)
    await db.commit()
    [stage] = await stages_of(db, await make_workflow(db, ("Analyze", "analysis")))

    model, reason = await route(db, stage, providers={"openai"})
    assert model.model_name == "gpt-4o"
    assert "fallback" in reason.lower()


async def test_empty_registry_returns_none_without_logging(db_session):
    [stage] = await stages_of(db_session, await make_workflow(db_session, ("Analyze", "analysis")))
    execution_id = uuid.uuid4()
    model, reason = await RoutingEngine(db_session).select_model_for_stage(stage, execution_id)
    assert model is None
    assert "No routable model" in reason
    assert await decisions_for(db_session, execution_id) == []


async def test_every_decision_is_logged(seeded_routing_rules):
    db = seeded_routing_rules
    stages = await stages_of(db, await make_workflow(db, ("A", "analysis"), ("B", "generation"), ("C", None)))
    engine = RoutingEngine(db, available_providers=ALL_PROVIDERS)
    execution_id = uuid.uuid4()
    for stage in stages:
        await engine.select_model_for_stage(stage, execution_id)
    await db.commit()

    decisions = await decisions_for(db, execution_id)
    assert [d.stage_id for d in decisions] == [s.id for s in stages]
    assert all(d.selected_model_id and d.selected_model_name and d.selection_reason for d in decisions)
    assert decisions[1].priority_factor == "quality"


# ============================================================================
# End-to-end: routing inside workflow execution
# ============================================================================

async def test_e2e_execution_routes_each_stage(seeded_routing_rules, providers):
    db = seeded_routing_rules
    stubs = providers(*ALL_PROVIDERS)
    workflow = await make_workflow(db, ("Analyze", "analysis"), ("Code", "generation"), ("Tests", "testing"))

    execution_id = await ExecutionEngine(db).execute_workflow(workflow.id, use_cache=False)
    await db.commit()

    decisions = await decisions_for(db, execution_id)
    assert [d.selected_model_name for d in decisions] == [
        "gemini-2.0-flash-exp", "claude-sonnet-4-20250514", "gemini-2.0-flash-exp",
    ]
    # Each routed model was actually called on its own provider
    assert stubs["gemini"].models_called == ["gemini-2.0-flash-exp", "gemini-2.0-flash-exp"]
    assert stubs["anthropic"].models_called == ["claude-sonnet-4-20250514"]
    assert stubs["openai"].models_called == []

    records = (await db.execute(
        select(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id)
        .order_by(ExecutionRecord.created_at)
    )).scalars().all()
    assert [r.model_used for r in records] == [d.selected_model_name for d in decisions]
    assert all(r.metadata_["routing"]["routed"] for r in records)
    assert records[1].metadata_["routing"]["decision_id"] == str(decisions[1].id)


async def test_e2e_routing_preferences_override_per_stage(seeded_routing_rules, providers):
    db = seeded_routing_rules
    stubs = providers(*ALL_PROVIDERS)
    workflow = await make_workflow(db, ("Analyze", "analysis"), ("Code", "generation"))
    first, second = await stages_of(db, workflow)

    execution_id = await ExecutionEngine(db).execute_workflow(
        workflow.id, use_cache=False, routing_preferences={str(first.id): "gpt-4o"},
    )
    await db.commit()

    decisions = await decisions_for(db, execution_id)
    assert decisions[0].was_user_override and decisions[0].selected_model_name == "gpt-4o"
    assert not decisions[1].was_user_override  # second stage routed normally
    assert stubs["openai"].models_called == ["gpt-4o"]


async def test_e2e_no_routable_model_uses_execution_default(seeded_routing_rules, providers, fake_provider):
    """Only the non-registry "fake" provider is configured: routing falls back to the defaults."""
    db = seeded_routing_rules
    # `providers` emptied the registry before fake_provider registered itself
    workflow = await make_workflow(db, ("Analyze", "analysis"))

    execution_id = await ExecutionEngine(db).execute_workflow(workflow.id, default_provider="fake", use_cache=False)
    await db.commit()

    [decision] = await decisions_for(db, execution_id)
    assert decision.was_fallback and decision.selected_provider == "fake"
    assert decision.selected_model_id is None
    [record] = (await db.execute(select(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id))).scalars().all()
    assert record.status == "completed" and record.provider == "fake"
    assert record.metadata_["routing"]["routed"] is False


async def test_e2e_use_routing_false_skips_router(seeded_routing_rules, providers):
    db = seeded_routing_rules
    stubs = providers(*ALL_PROVIDERS)
    workflow = await make_workflow(db, ("Code", "generation"))

    execution_id = await ExecutionEngine(db).execute_workflow(
        workflow.id, default_provider="groq", default_model="llama-3.1-8b-instant",
        use_cache=False, use_routing=False,
    )
    await db.commit()

    assert await decisions_for(db, execution_id) == []
    assert stubs["groq"].models_called == ["llama-3.1-8b-instant"]


async def test_e2e_cache_hits_bypass_routing(seeded_routing_rules, providers, mock_embeddings):
    db = seeded_routing_rules
    stubs = providers(*ALL_PROVIDERS)
    workflow = await make_workflow(db, ("Analyze", "analysis"), ("Code", "generation"))
    engine = ExecutionEngine(db)

    first = await engine.execute_workflow(workflow.id)
    await db.commit()
    calls_after_first = sum(len(s.models_called) for s in stubs.values())

    second = await engine.execute_workflow(workflow.id)
    await db.commit()

    assert len(await decisions_for(db, first)) == 2
    assert await decisions_for(db, second) == []  # both stages served from cache
    assert sum(len(s.models_called) for s in stubs.values()) == calls_after_first
    records = (await db.execute(select(ExecutionRecord).where(ExecutionRecord.execution_id == second))).scalars().all()
    assert all(r.cache_hit for r in records)


async def test_routing_cuts_cost_versus_single_premium_model(seeded_routing_rules, providers):
    """Routed execution's estimated cost vs. sending every stage to the premium model."""
    db = seeded_routing_rules
    providers(*ALL_PROVIDERS)
    workflow = await make_workflow(db, ("Analyze", "analysis"), ("Code", "generation"),
                                   ("Tests", "testing"), ("Docs", "documentation"))
    execution_id = await ExecutionEngine(db).execute_workflow(workflow.id, use_cache=False)
    await db.commit()

    decisions = await decisions_for(db, execution_id)
    profiles = {m.id: m for m in await ModelRegistry(db).list_models()}
    sonnet = await ModelRegistry(db).get_model("anthropic", "claude-sonnet-4-20250514")

    routed_cost = sum(profiles[d.selected_model_id].estimate_cost(1000, 500) for d in decisions)
    premium_cost = sonnet.estimate_cost(1000, 500) * len(decisions)
    assert routed_cost < premium_cost / 2
    # ...while the code stage still gets the top generation model
    assert decisions[1].selected_model_name == sonnet.model_name
