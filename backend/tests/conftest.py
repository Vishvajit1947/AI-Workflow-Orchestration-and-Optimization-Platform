"""Pytest configuration and fixtures"""
import pytest
import pytest_asyncio
import asyncio
import hashlib
import math
import os
import random
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from backend.app.database import Base, get_db
from backend.app.main import app
# Import ALL models so Base.metadata.create_all() creates all tables
from backend.app.models import (
    Workflow, Stage, StageDependency,
    WorkflowContext, ExecutionRecord, CacheEntry,
    ModelProfile, RoutingRule, RoutingDecision
)
from backend.app.services.llm import registry
from backend.app.services.llm.base import BaseLLMProvider, LLMResponse
import uuid

# Separate test database: the engine fixture runs drop_all on teardown,
# so pointing it at the dev database would wipe the migrated schema.
# Uses same PostgreSQL instance (port 5433 to avoid conflict with local PostgreSQL)
# with different database name
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://orchestrator:orchestrator_dev@localhost:5433/ai_orchestrator_test",
)


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Create a test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Create a test database session"""
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def client(engine, db_session):
    """Create a test HTTP client with overridden database dependency"""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_workflow(db_session):
    """Create a sample workflow for testing"""
    workflow = Workflow(
        id=uuid.uuid4(),
        name="Test Workflow",
        description="A workflow for testing",
        objective="Test objective",
        status="active"
    )
    db_session.add(workflow)
    await db_session.commit()
    await db_session.refresh(workflow)
    return workflow


@pytest_asyncio.fixture
async def sample_stage(db_session, sample_workflow):
    """Create a sample stage for testing"""
    stage = Stage(
        id=uuid.uuid4(),
        workflow_id=sample_workflow.id,
        name="Test Stage",
        instruction="Do something useful",
        stage_order=0,
        model_preference="gpt-4",
        status="pending"
    )
    db_session.add(stage)
    await db_session.commit()
    await db_session.refresh(stage)
    return stage


@pytest_asyncio.fixture
async def sample_workflow_with_stages(db_session):
    """Create a sample 3-stage workflow for integration testing"""
    workflow = Workflow(
        id=uuid.uuid4(),
        name="Integration Test Workflow",
        description="Integration test workflow",
        objective="Test context flow and execution",
        status="draft"
    )
    db_session.add(workflow)
    await db_session.flush()

    # Stage 1: Analysis
    stage1 = Stage(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        name="Analyze Requirements",
        instruction="List 3 key requirements for a todo app.",
        stage_order=0,
        stage_type="analysis",
        model_preference=None,
        status="pending"
    )
    # Stage 2: Design
    stage2 = Stage(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        name="Design Architecture",
        instruction="Based on the requirements, propose a simple architecture.",
        stage_order=1,
        stage_type="design",
        model_preference=None,
        status="pending"
    )
    # Stage 3: Generate Code
    stage3 = Stage(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        name="Generate API Schema",
        instruction="Create a REST API schema for the todo app.",
        stage_order=2,
        stage_type="generation",
        model_preference=None,
        status="pending"
    )

    db_session.add_all([stage1, stage2, stage3])
    await db_session.commit()
    await db_session.refresh(workflow)

    return workflow


@pytest.fixture
def mock_llm_response():
    """Mock LLM response factory for testing"""
    from backend.app.services.llm.base import LLMResponse
    
    def _create_response(content: str, model: str = "gpt-4o-mini") -> LLMResponse:
        return LLMResponse(
            content=content,
            model=model,
            provider="openai",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            latency_ms=500,
            estimated_cost=0.0001
        )
    
    return _create_response



# ---------------------------------------------------------------------------
# Cache / execution fixtures (Phase 3)
# ---------------------------------------------------------------------------

EMBEDDING_SERVICE_PATH = "backend.app.services.cache.semantic_cache.get_embedding_service"
CACHE_EMBEDDING_DIM = 1536


class FakeProvider(BaseLLMProvider):
    """
    Deterministic LLM provider registered as "fake": output depends on the prompt
    and `version`. `delay_s` simulates network latency for timing benchmarks.
    """
    provider_name = "fake"

    def __init__(self, delay_s: float = 0.0):
        self.calls = 0
        self.version = 1
        self.delay_s = delay_s

    async def generate(self, prompt: str, model: Optional[str] = None,
                       temperature: float = 0.7, max_tokens: int = 4096,
                       system_prompt: Optional[str] = None) -> LLMResponse:
        self.calls += 1
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        digest = hashlib.sha256(prompt.encode()).hexdigest()[:12]
        return LLMResponse(
            content=f"v{self.version} output for {digest}",
            model="fake-model", provider="fake",
            input_tokens=100, output_tokens=50, total_tokens=150,
            latency_ms=int(self.delay_s * 1000) or 500, estimated_cost=0.0001,
        )

    def get_available_models(self) -> list[dict]:
        return [{"name": "fake-model"}]

    def get_default_model(self) -> str:
        return "fake-model"


def text_hash_embedding(text: str, dim: int = CACHE_EMBEDDING_DIM) -> list[float]:
    """Deterministic unit vector: identical text → identical vector, different text → ~orthogonal."""
    rng = random.Random(hashlib.sha256(text.encode()).digest())
    v = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


@pytest.fixture
def fake_provider():
    """Register a FakeProvider for the test; use default_provider="fake" when executing."""
    provider = FakeProvider()
    registry.register(provider)
    yield provider
    registry._providers.pop(provider.provider_name, None)


@pytest.fixture
def mock_embeddings():
    """Patch the cache's embedding service with deterministic text-hash embeddings."""
    svc = MagicMock()
    svc.generate_embedding = AsyncMock(side_effect=lambda text: text_hash_embedding(text))
    with patch(EMBEDDING_SERVICE_PATH, MagicMock(return_value=svc)):
        yield svc


@pytest.fixture(scope="session")
def local_embedding_service():
    """Real sentence-transformers embedding service (all-MiniLM-L6-v2, 384-dim). Loaded once."""
    from backend.app.services.embedding_service import EmbeddingService
    try:
        return EmbeddingService(provider="local")
    except Exception as e:  # model not downloadable / not cached
        pytest.skip(f"Local embedding model unavailable: {e}")


@pytest.fixture
def semantic_embeddings(local_embedding_service):
    """
    Patch the cache's embedding service with REAL semantic embeddings from the local
    model, zero-padded from 384 to 1536 dims to fit the vector(1536) column.
    Zero-padding leaves dot products and norms unchanged, so cosine similarity in
    pgvector equals the model's own cosine similarity.
    """
    async def embed(text: str) -> list[float]:
        vec = await local_embedding_service.generate_embedding(text)
        return list(vec) + [0.0] * (CACHE_EMBEDDING_DIM - len(vec))

    svc = MagicMock()
    svc.generate_embedding = AsyncMock(side_effect=embed)
    with patch(EMBEDDING_SERVICE_PATH, MagicMock(return_value=svc)):
        yield svc


# ---------------------------------------------------------------------------
# Routing fixtures (Phase 4)
# ---------------------------------------------------------------------------

class StubProvider(BaseLLMProvider):
    """
    LLM provider stub registered under a real provider name (openai, anthropic, ...)
    so routed calls can be dispatched. Echoes the requested model and records it.
    """

    def __init__(self, name: str):
        self.provider_name = name
        self.models_called: list[str] = []

    async def generate(self, prompt: str, model: Optional[str] = None,
                       temperature: float = 0.7, max_tokens: int = 4096,
                       system_prompt: Optional[str] = None) -> LLMResponse:
        self.models_called.append(model)
        digest = hashlib.sha256(prompt.encode()).hexdigest()[:12]
        return LLMResponse(
            content=f"{self.provider_name}/{model} output for {digest}",
            model=model, provider=self.provider_name,
            input_tokens=100, output_tokens=50, total_tokens=150,
            latency_ms=300, estimated_cost=0.0001,
        )

    def get_available_models(self) -> list[dict]:
        return []

    def get_default_model(self) -> str:
        return f"{self.provider_name}-default"


@pytest.fixture
def providers():
    """
    Empty the provider registry for the test and restore it afterwards.
    Call providers("openai", "anthropic") to register StubProviders; returns {name: stub}.
    """
    saved = dict(registry._providers)
    registry._providers.clear()

    def register(*names: str) -> dict[str, StubProvider]:
        stubs = {name: StubProvider(name) for name in names}
        for stub in stubs.values():
            registry.register(stub)
        return stubs

    yield register
    registry._providers.clear()
    registry._providers.update(saved)


ALL_PROVIDERS = ("openai", "anthropic", "gemini", "groq")


@pytest_asyncio.fixture
async def seeded_models(db_session):
    """Seed the model registry."""
    from backend.app.services.router.model_registry import seed_model_profiles
    await seed_model_profiles(db_session)
    return db_session


@pytest_asyncio.fixture
async def seeded_routing_rules(seeded_models):
    """Seed model registry plus default routing rules."""
    from backend.app.services.router.routing_rules import seed_default_routing_rules
    await seed_default_routing_rules(seeded_models)
    return seeded_models


# ---------------------------------------------------------------------------
# Execution isolation (Phase 5)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_execution_state():
    """Provider health and live-execution state are process-global: start each test clean."""
    from backend.app.services.execution.error_handler import circuit_breaker
    from backend.app.services.execution.tracker import tracker
    circuit_breaker.reset()
    tracker.executions.clear()
    yield
    circuit_breaker.reset()
    tracker.executions.clear()
