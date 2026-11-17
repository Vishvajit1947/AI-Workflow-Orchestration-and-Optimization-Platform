"""API router aggregation — include all sub-routers here.

Authentication is enforced here, per router, so a new endpoint is protected by default:
every router except /auth requires an authenticated, active user (401 otherwise).
Endpoints that also need to know *who* the user is declare
`current_user: User = Depends(get_current_active_user)`; FastAPI resolves the
dependency once per request, so this costs no extra query.

Public endpoints: /api/auth/{register,login,logout,forgot-password,reset-password},
/health and / (see main.py). The WebSocket at /ws/executions/{id} authenticates itself.
"""

from fastapi import APIRouter, Depends

from backend.app.core.dependencies import get_current_active_user
from backend.app.api.auth import router as auth_router
from backend.app.api.workflows import router as workflow_router
from backend.app.api.stages import router as stage_router
from backend.app.api.execution import router as execution_router
from backend.app.api.cache import router as cache_router
from backend.app.api.models import router as models_router
from backend.app.api.routing import router as routing_router
from backend.app.api.analytics import router as analytics_router
from backend.app.api.planner import router as planner_router
from backend.app.api.artifacts import router as artifacts_router

PROTECTED_ROUTERS = (
    workflow_router,
    stage_router,
    execution_router,
    cache_router,
    models_router,
    routing_router,
    analytics_router,
    planner_router,
    artifacts_router,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
for _router in PROTECTED_ROUTERS:
    api_router.include_router(_router, dependencies=[Depends(get_current_active_user)])
