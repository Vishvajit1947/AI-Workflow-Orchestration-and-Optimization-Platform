"""API router aggregation — include all sub-routers here."""

from fastapi import APIRouter
from backend.app.api.workflows import router as workflow_router
from backend.app.api.stages import router as stage_router
from backend.app.api.execution import router as execution_router
from backend.app.api.cache import router as cache_router
from backend.app.api.models import router as models_router
from backend.app.api.routing import router as routing_router
from backend.app.api.analytics import router as analytics_router
from backend.app.api.planner import router as planner_router

api_router = APIRouter(prefix="/api")
api_router.include_router(workflow_router)
api_router.include_router(stage_router)
api_router.include_router(execution_router)
api_router.include_router(cache_router)
api_router.include_router(models_router)
api_router.include_router(routing_router)
api_router.include_router(analytics_router)
api_router.include_router(planner_router)
