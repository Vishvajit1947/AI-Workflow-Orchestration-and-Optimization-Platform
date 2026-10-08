"""
Routing API endpoints: routing rules CRUD, routing decision log, routing preview.
All routes are prefixed with /api/routing (set in router include).
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import get_db
from backend.app.models.model_profile import ModelProfile
from backend.app.models.routing_rule import RoutingDecision
from backend.app.models.workflow import Workflow
from backend.app.schemas.common import MessageResponse
from backend.app.schemas.routing import (
    RoutingDecisionResponse, RoutingPreviewItem,
    RoutingRuleCreate, RoutingRuleResponse, RoutingRuleUpdate,
)
from backend.app.services.llm import registry as provider_registry
from backend.app.services.router.routing_engine import RoutingEngine
from backend.app.services.router.routing_rules import RoutingRulesManager


router = APIRouter(prefix="/routing", tags=["routing"])


async def _check_model_ids(db: AsyncSession, *model_ids: Optional[uuid.UUID]) -> None:
    for model_id in model_ids:
        if model_id is not None and await db.get(ModelProfile, model_id) is None:
            raise HTTPException(status_code=422, detail=f"Model profile {model_id} not found")


@router.get("/rules", response_model=List[RoutingRuleResponse])
async def list_rules(active_only: bool = Query(False), db: AsyncSession = Depends(get_db)):
    return await RoutingRulesManager(db).list_rules(active_only=active_only)


@router.get("/rules/{stage_type}", response_model=RoutingRuleResponse)
async def get_rule(stage_type: str, db: AsyncSession = Depends(get_db)):
    rule = await RoutingRulesManager(db).get_rule(stage_type)
    if not rule:
        raise HTTPException(status_code=404, detail=f"No routing rule for stage type '{stage_type}'")
    return rule


@router.post("/rules", response_model=RoutingRuleResponse, status_code=201)
async def create_rule(payload: RoutingRuleCreate, db: AsyncSession = Depends(get_db)):
    manager = RoutingRulesManager(db)
    if await manager.get_rule(payload.stage_type):
        raise HTTPException(status_code=409, detail=f"A routing rule for '{payload.stage_type}' already exists")
    await _check_model_ids(db, payload.preferred_model_id, payload.fallback_model_id)
    return await manager.create_rule(**payload.model_dump())


@router.put("/rules/{stage_type}", response_model=RoutingRuleResponse)
async def update_rule(stage_type: str, payload: RoutingRuleUpdate, db: AsyncSession = Depends(get_db)):
    updates = payload.model_dump(exclude_unset=True)
    for key in ("priority_factor", "min_capability_score", "is_active"):
        if key in updates and updates[key] is None:
            raise HTTPException(status_code=422, detail=f"{key} cannot be null")
    await _check_model_ids(db, updates.get("preferred_model_id"), updates.get("fallback_model_id"))
    rule = await RoutingRulesManager(db).update_rule(stage_type, **updates)
    if not rule:
        raise HTTPException(status_code=404, detail=f"No routing rule for stage type '{stage_type}'")
    return rule


@router.delete("/rules/{stage_type}", response_model=MessageResponse)
async def delete_rule(stage_type: str, db: AsyncSession = Depends(get_db)):
    if not await RoutingRulesManager(db).delete_rule(stage_type):
        raise HTTPException(status_code=404, detail=f"No routing rule for stage type '{stage_type}'")
    return MessageResponse(message=f"Routing rule for '{stage_type}' deleted")


@router.get("/decisions", response_model=List[RoutingDecisionResponse])
async def list_decisions(
    execution_id: Optional[uuid.UUID] = Query(None),
    stage_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Routing decision log, newest first."""
    query = select(RoutingDecision).order_by(RoutingDecision.created_at.desc()).limit(limit)
    if execution_id:
        query = query.where(RoutingDecision.execution_id == execution_id)
    if stage_type:
        query = query.where(RoutingDecision.stage_type == stage_type)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/preview/{workflow_id}", response_model=List[RoutingPreviewItem])
async def preview_routing(workflow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Which model each stage would be routed to right now. Nothing is logged."""
    result = await db.execute(
        select(Workflow).options(selectinload(Workflow.stages)).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    engine = RoutingEngine(db, available_providers=provider_registry.list_providers())
    preview = []
    savepoint = await db.begin_nested()
    try:
        for stage in sorted(workflow.stages, key=lambda s: s.stage_order):
            model, reason = await engine.select_model_for_stage(stage, uuid.uuid4())
            preview.append(RoutingPreviewItem(
                stage_id=stage.id, stage_name=stage.name, stage_type=stage.stage_type,
                provider=model.provider if model else None,
                model_name=model.model_name if model else None,
                reason=reason,
            ))
    finally:
        # Discard the decisions the engine logged
        await savepoint.rollback()
    return preview
