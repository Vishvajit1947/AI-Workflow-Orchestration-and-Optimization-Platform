"""
Routing Engine.
Selects the model for each stage from user overrides, stage preferences,
routing rules and the model registry, and logs every decision.

Selection order:
  1. user override for this execution (routing_preferences)
  2. stage.model_preference
  3. the stage type's routing rule: preferred model
  4. best candidate under the rule's constraints, by its priority factor
  5. fallback: the rule's fallback model, else the most capable routable model
A model is only chosen if it is available and its provider is registered
(has an API key), so a routed call can always be dispatched.
"""
import uuid
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.model_profile import ModelProfile
from backend.app.models.routing_rule import RoutingRule, RoutingDecision
from backend.app.models.stage import Stage
from backend.app.services.router.model_registry import ModelRegistry, capability_for_stage_type

PRIORITY_FACTORS = ("cost", "speed", "quality", "balanced")
DEFAULT_PRIORITY = "balanced"
DEFAULT_MIN_SCORE = 0.70

# Token counts of a "typical" call, used to check max_cost_per_call
TYPICAL_INPUT_TOKENS = 1000
TYPICAL_OUTPUT_TOKENS = 500

# Balanced priority: weights of normalized capability, cheapness and speed
BALANCED_WEIGHTS = {"capability": 0.5, "cost": 0.25, "speed": 0.25}


def _normalize(value: float, low: float, high: float) -> float:
    """Map value into 0..1 over [low, high]; 1.0 when all candidates are equal."""
    return (value - low) / (high - low) if high > low else 1.0


class RoutingEngine:
    """Picks a model per stage and records why."""

    def __init__(self, db: AsyncSession, available_providers: Optional[Iterable[str]] = None):
        """
        available_providers: provider names that can actually be called. None means
        every provider is considered callable (useful for tests and previews).
        """
        self.db = db
        self.registry = ModelRegistry(db)
        self.available_providers = set(available_providers) if available_providers is not None else None
        self.last_decision: Optional[RoutingDecision] = None

    def is_routable(self, model: Optional[ModelProfile]) -> bool:
        return bool(
            model is not None and model.is_available and
            (self.available_providers is None or model.provider in self.available_providers)
        )

    async def select_model_for_stage(self, stage: Stage, execution_id: uuid.UUID,
                                     user_override: Optional[str] = None
                                     ) -> tuple[Optional[ModelProfile], str]:
        """
        Select and log the model for a stage. Returns (profile, reason); profile is
        None (and nothing is logged) when no routable model exists at all.
        """
        capability = capability_for_stage_type(stage.stage_type)

        if user_override:
            model = await self._get_routable_by_name(user_override)
            if model:
                reason = f"User override: {model.model_name}"
                await self.log_decision(execution_id, stage, model.provider, model.model_name, reason,
                                        model=model, was_user_override=True)
                return model, reason

        if stage.model_preference:
            model = await self._get_routable_by_name(stage.model_preference)
            if model:
                reason = f"Stage preference: {model.model_name}"
                await self.log_decision(execution_id, stage, model.provider, model.model_name, reason, model=model)
                return model, reason

        rule = await self._get_routing_rule(stage.stage_type)
        priority = rule.priority_factor if rule and rule.priority_factor in PRIORITY_FACTORS else DEFAULT_PRIORITY

        if rule and self.is_routable(rule.preferred_model):
            model = rule.preferred_model
            reason = f"Routing rule preferred model for {stage.stage_type}: {model.model_name}"
            await self.log_decision(execution_id, stage, model.provider, model.model_name, reason,
                                    model=model, priority_factor=priority)
            return model, reason

        candidates = await self._get_candidate_models(capability, rule)
        alternatives = [self._describe(m, capability) for m in candidates]

        if candidates:
            model = self._apply_priority_selection(candidates, priority, capability)
            reason = (f"Routing: {priority} priority for {capability}, "
                      f"score={model.get_capability_score(capability):.2f}, "
                      f"{len(candidates)} candidate(s)")
            await self.log_decision(execution_id, stage, model.provider, model.model_name, reason,
                                    model=model, priority_factor=priority, alternatives=alternatives)
            return model, reason

        # No candidate met the constraints
        if rule and self.is_routable(rule.fallback_model):
            model = rule.fallback_model
            reason = f"Fallback: rule fallback model {model.model_name}, no candidate met the constraints"
        else:
            routable = [m for m in await self.registry.list_models() if self.is_routable(m)]
            model = max(routable, key=lambda m: m.get_capability_score(capability), default=None)
            if model is None:
                return None, "No routable model: registry empty or no provider configured"
            reason = f"Fallback: most capable routable model {model.model_name}, no candidate met the constraints"

        await self.log_decision(execution_id, stage, model.provider, model.model_name, reason,
                                model=model, priority_factor=priority, was_fallback=True,
                                alternatives=alternatives)
        return model, reason

    async def select_fallback_model(self, stage: Stage, execution_id: uuid.UUID,
                                    exclude: set[tuple[str, str]], failure: str
                                    ) -> Optional[ModelProfile]:
        """
        Pick a replacement after a model failed at call time: the rule's fallback model,
        else the most capable routable model. Models in `exclude` ((provider, model_name))
        are skipped. Logs the decision; returns None if nothing is left.
        """
        capability = capability_for_stage_type(stage.stage_type)
        rule = await self._get_routing_rule(stage.stage_type)
        ranked = sorted(await self.registry.list_models(), key=lambda m: -m.get_capability_score(capability))
        preferred = [rule.fallback_model] if rule and rule.fallback_model else []

        for model in preferred + ranked:
            if self.is_routable(model) and (model.provider, model.model_name) not in exclude:
                reason = f"Fallback after failure: {failure}"[:500]
                await self.log_decision(execution_id, stage, model.provider, model.model_name, reason,
                                        model=model, was_fallback=True)
                return model
        return None

    async def _get_candidate_models(self, capability: str,
                                    rule: Optional[RoutingRule]) -> list[ModelProfile]:
        """Routable models that satisfy the rule's capability, cost and latency constraints."""
        min_score = float(rule.min_capability_score) if rule and rule.min_capability_score is not None else DEFAULT_MIN_SCORE
        candidates = []
        for model in await self.registry.list_models():
            if not self.is_routable(model):
                continue
            if model.get_capability_score(capability) < min_score:
                continue
            if rule and rule.max_cost_per_call is not None:
                if model.estimate_cost(TYPICAL_INPUT_TOKENS, TYPICAL_OUTPUT_TOKENS) > rule.max_cost_per_call:
                    continue
            if rule and rule.max_latency_ms is not None:
                if model.avg_latency_ms is None or model.avg_latency_ms > rule.max_latency_ms:
                    continue
            candidates.append(model)
        return candidates

    def _apply_priority_selection(self, candidates: list[ModelProfile], priority: str,
                                  capability: str) -> ModelProfile:
        """Pick one candidate. Ties break toward higher capability."""
        def score(m: ModelProfile) -> float:
            return m.get_capability_score(capability)

        def latency(m: ModelProfile) -> float:
            return m.avg_latency_ms if m.avg_latency_ms is not None else float("inf")

        if priority == "cost":
            return min(candidates, key=lambda m: (m.avg_cost_per_token, -score(m)))
        if priority == "speed":
            return min(candidates, key=lambda m: (latency(m), -score(m)))
        if priority == "quality":
            return max(candidates, key=lambda m: (score(m), -m.avg_cost_per_token))

        # balanced: weighted sum of capability, cheapness and speed, each normalized across candidates
        scores = [score(m) for m in candidates]
        costs = [float(m.avg_cost_per_token) for m in candidates]
        known_latencies = [m.avg_latency_ms for m in candidates if m.avg_latency_ms is not None]
        worst_latency = max(known_latencies, default=0)
        latencies = [m.avg_latency_ms if m.avg_latency_ms is not None else worst_latency for m in candidates]

        def balanced(i: int) -> float:
            return (
                BALANCED_WEIGHTS["capability"] * _normalize(scores[i], min(scores), max(scores))
                + BALANCED_WEIGHTS["cost"] * (1 - _normalize(costs[i], min(costs), max(costs)))
                + BALANCED_WEIGHTS["speed"] * (1 - _normalize(latencies[i], min(latencies), max(latencies)))
            )

        best = max(range(len(candidates)), key=lambda i: (balanced(i), scores[i]))
        return candidates[best]

    async def _get_routing_rule(self, stage_type: Optional[str]) -> Optional[RoutingRule]:
        if not stage_type:
            return None
        result = await self.db.execute(
            select(RoutingRule).where(RoutingRule.stage_type == stage_type, RoutingRule.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def _get_routable_by_name(self, model_name: str) -> Optional[ModelProfile]:
        """First routable profile with this model name (names can repeat across providers)."""
        result = await self.db.execute(select(ModelProfile).where(ModelProfile.model_name == model_name))
        return next((m for m in result.scalars().all() if self.is_routable(m)), None)

    @staticmethod
    def _describe(model: ModelProfile, capability: str) -> dict:
        return {
            "model": model.model_name,
            "provider": model.provider,
            "score": model.get_capability_score(capability),
            "cost_per_call": float(model.estimate_cost(TYPICAL_INPUT_TOKENS, TYPICAL_OUTPUT_TOKENS)),
            "avg_latency_ms": model.avg_latency_ms,
        }

    async def log_decision(self, execution_id: uuid.UUID, stage: Stage, provider: str, model_name: str,
                           reason: str, model: Optional[ModelProfile] = None,
                           priority_factor: Optional[str] = None, was_user_override: bool = False,
                           was_fallback: bool = False, alternatives: Optional[list[dict]] = None
                           ) -> RoutingDecision:
        """Record a routing decision. `model` is None when the pick isn't a registry profile."""
        decision = RoutingDecision(
            execution_id=execution_id,
            stage_id=stage.id,
            stage_type=stage.stage_type,
            selected_model_id=model.id if model else None,
            selected_provider=provider,
            selected_model_name=model_name,
            selection_reason=reason[:500],
            priority_factor=priority_factor,
            was_user_override=was_user_override,
            was_fallback=was_fallback,
            alternatives_considered=alternatives or [],
        )
        self.db.add(decision)
        await self.db.flush()
        self.last_decision = decision
        return decision
