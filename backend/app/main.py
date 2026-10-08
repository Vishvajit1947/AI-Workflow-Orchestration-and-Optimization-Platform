"""
FastAPI application entry point.
- CORS middleware
- Lifespan: connect/disconnect database
- Health check endpoint
- Router includes (added in later MTs)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.database import engine, async_session_factory
from backend.app.services.router import seed_model_profiles, seed_default_routing_rules
from backend.app.services.execution.runner import fail_interrupted_workflows


async def seed_routing_data():
    """Insert any missing seed model profiles and default routing rules (never overwrites)."""
    try:
        async with async_session_factory() as db:
            await seed_model_profiles(db)
            await seed_default_routing_rules(db)
        print("[OK] Model registry and routing rules seeded")
    except Exception as e:
        print(f"[WARN] Routing seed skipped (run `alembic upgrade head`?): {e}")


async def recover_interrupted_executions():
    """Executions run in-process, so any workflow left running/paused by a previous process is dead."""
    try:
        async with async_session_factory() as db:
            count = await fail_interrupted_workflows(db)
        if count:
            print(f"[OK] Marked {count} interrupted workflow(s) as failed")
    except Exception as e:
        print(f"[WARN] Could not reset interrupted workflows: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: verify DB connection. Shutdown: dispose engine."""
    # Startup
    try:
        async with engine.begin() as conn:
            # Simple connectivity check — does not create tables (Alembic handles that)
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        print(f"[OK] {settings.APP_NAME} started - {settings.ENVIRONMENT} mode")
        print(f"[OK] Database connection verified")
    except Exception as e:
        print(f"[WARN] {settings.APP_NAME} started - {settings.ENVIRONMENT} mode")
        print(f"[WARN] Database connection failed: {e}")
        print(f"[WARN] Server will run but database operations will fail")
    await seed_routing_data()
    await recover_interrupted_executions()
    yield
    # Shutdown
    await engine.dispose()
    print(f"[SHUTDOWN] {settings.APP_NAME} shut down")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Manages and optimizes multi-stage AI workflows using multiple LLMs. "
        "Provides workflow orchestration, semantic caching, stage-aware routing, "
        "parallel execution, and performance analytics."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Health Check ----------
@app.get("/health", tags=["Health"])
async def health_check():
    """Returns OK if the service is running."""
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint — redirects to docs."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health",
    }


# ---------- Router Includes ----------
from backend.app.api import api_router
from backend.app.api.websocket import router as websocket_router
app.include_router(api_router)
app.include_router(websocket_router)
