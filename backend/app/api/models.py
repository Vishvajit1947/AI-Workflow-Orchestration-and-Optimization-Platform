"""
Model Registry API endpoints.
All routes are prefixed with /api/models (set in router include).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.model_profile import ModelProfile
from backend.app.schemas.routing import ModelComparisonResponse, ModelProfileResponse, ModelProfileUpdate
from backend.app.services.llm import registry as provider_registry
from backend.app.services.router.model_registry import CAPABILITIES, ModelRegistry


router = APIRouter(prefix="/models", tags=["models"])


def _to_response(model: ModelProfile) -> ModelProfileResponse:
    response = ModelProfileResponse.model_validate(model)
    response.routable = model.is_available and model.provider in provider_registry.list_providers()
    return response


@router.get("", response_model=List[ModelProfileResponse])
async def list_models(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    capability: Optional[str] = Query(None, description="Only models scoring at least min_score for this capability"),
    min_score: float = Query(0.7, ge=0.0, le=1.0, description="Minimum capability score (with capability)"),
    include_unavailable: bool = Query(False, description="Include models marked unavailable"),
    db: AsyncSession = Depends(get_db),
):
    """List registered models, optionally filtered."""
    models = await ModelRegistry(db).list_models(provider=provider, available_only=not include_unavailable)
    if capability:
        models = [m for m in models if m.get_capability_score(capability) >= min_score]
    return [_to_response(m) for m in models]


@router.get("/compare", response_model=ModelComparisonResponse)
async def compare_models(
    capability: Optional[str] = Query(None, description="Restrict cheapest/fastest to models good at this capability"),
    min_score: float = Query(0.7, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """All available models plus the cheapest, fastest and most capable per capability."""
    registry = ModelRegistry(db)
    models = await registry.list_models()
    cheapest = await registry.get_cheapest_model(capability, min_score)
    fastest = await registry.get_fastest_model(capability, min_score)

    most_capable = {}
    for cap in CAPABILITIES:
        best = max(models, key=lambda m: m.get_capability_score(cap), default=None)
        if best:
            most_capable[cap] = best.model_name

    return ModelComparisonResponse(
        models=[_to_response(m) for m in models],
        cheapest=cheapest.model_name if cheapest else None,
        fastest=fastest.model_name if fastest else None,
        most_capable=most_capable,
    )


@router.get("/{provider}/{model_name}", response_model=ModelProfileResponse)
async def get_model(provider: str, model_name: str, db: AsyncSession = Depends(get_db)):
    model = await ModelRegistry(db).get_model(provider, model_name)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {provider}/{model_name} not found")
    return _to_response(model)


@router.patch("/{provider}/{model_name}", response_model=ModelProfileResponse)
async def update_model(provider: str, model_name: str, payload: ModelProfileUpdate,
                       db: AsyncSession = Depends(get_db)):
    """Edit a profile, e.g. mark it unavailable so the router skips it."""
    model = await ModelRegistry(db).get_model(provider, model_name)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {provider}/{model_name} not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(model, key, value)
    await db.flush()
    await db.refresh(model)
    return _to_response(model)
