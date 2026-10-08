"""
Routing Rules Management.
CRUD for per-stage-type routing rules plus default rule seeding.
"""
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.routing_rule import RoutingRule
from backend.app.services.router.model_registry import ModelRegistry


class RoutingRulesManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_rule(self, stage_type: str, priority_factor: str = "balanced",
                          max_cost_per_call: Optional[float] = None,
                          max_latency_ms: Optional[int] = None,
                          min_capability_score: float = 0.80,
                          preferred_model_id: Optional[uuid.UUID] = None,
                          fallback_model_id: Optional[uuid.UUID] = None,
                          is_active: bool = True, config: Optional[dict] = None) -> RoutingRule:
        rule = RoutingRule(
            stage_type=stage_type,
            priority_factor=priority_factor,
            max_cost_per_call=Decimal(str(max_cost_per_call)) if max_cost_per_call is not None else None,
            max_latency_ms=max_latency_ms,
            min_capability_score=Decimal(str(min_capability_score)),
            preferred_model_id=preferred_model_id,
            fallback_model_id=fallback_model_id,
            is_active=is_active,
            config=config or {},
        )
        self.db.add(rule)
        await self.db.flush()
        return await self.get_rule(stage_type)

    async def get_rule(self, stage_type: str) -> Optional[RoutingRule]:
        result = await self.db.execute(
            select(RoutingRule).where(RoutingRule.stage_type == stage_type).execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_rules(self, active_only: bool = False) -> list[RoutingRule]:
        query = select(RoutingRule).order_by(RoutingRule.stage_type)
        if active_only:
            query = query.where(RoutingRule.is_active.is_(True))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_rule(self, stage_type: str, **updates) -> Optional[RoutingRule]:
        rule = await self.get_rule(stage_type)
        if not rule:
            return None
        for key, value in updates.items():
            if key in ("max_cost_per_call", "min_capability_score") and value is not None:
                value = Decimal(str(value))
            setattr(rule, key, value)
        await self.db.flush()
        # Reload so the preferred/fallback relationships reflect changed ids
        return await self.get_rule(stage_type)

    async def delete_rule(self, stage_type: str) -> bool:
        rule = await self.get_rule(stage_type)
        if not rule:
            return False
        await self.db.delete(rule)
        await self.db.flush()
        return True


async def seed_default_routing_rules(db: AsyncSession) -> None:
    """Create a default rule for each built-in stage type that doesn't have one yet."""
    manager = RoutingRulesManager(db)
    registry = ModelRegistry(db)

    gpt4o_mini = await registry.get_model("openai", "gpt-4o-mini")
    claude_haiku = await registry.get_model("anthropic", "claude-3-5-haiku-20241022")
    fallback_id = gpt4o_mini.id if gpt4o_mini else None
    fast_fallback_id = claude_haiku.id if claude_haiku else fallback_id

    defaults = [
        # Analysis and design: good quality at sensible cost and speed
        dict(stage_type="analysis", priority_factor="balanced", min_capability_score=0.85, fallback_model_id=fallback_id),
        dict(stage_type="design", priority_factor="balanced", min_capability_score=0.85, fallback_model_id=fallback_id),
        # Code generation and review: correctness matters most
        dict(stage_type="generation", priority_factor="quality", min_capability_score=0.85, fallback_model_id=fallback_id),
        dict(stage_type="review", priority_factor="quality", min_capability_score=0.85, fallback_model_id=fallback_id),
        # Tests and docs: cheap is good enough
        dict(stage_type="testing", priority_factor="cost", min_capability_score=0.80,
             max_cost_per_call=0.005, fallback_model_id=fallback_id),
        dict(stage_type="documentation", priority_factor="cost", min_capability_score=0.80, fallback_model_id=fallback_id),
        # Custom stages: fastest acceptable model
        dict(stage_type="custom", priority_factor="speed", min_capability_score=0.80, fallback_model_id=fast_fallback_id),
    ]
    for spec in defaults:
        if not await manager.get_rule(spec["stage_type"]):
            await manager.create_rule(**spec)
    await db.commit()
