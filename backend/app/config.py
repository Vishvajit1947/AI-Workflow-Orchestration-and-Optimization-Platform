"""
Application configuration via Pydantic BaseSettings.
Reads from environment variables and/or a .env file at the project root.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """All application settings. Loaded from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- App ----------
    APP_NAME: str = "AI Workflow Orchestration Platform"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    SECRET_KEY: str = "change-me-in-production"
    BACKEND_PORT: int = 8000

    # ---------- Database ----------
    DATABASE_URL: str = "postgresql+asyncpg://orchestrator:orchestrator_dev@localhost:5432/ai_orchestrator"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://orchestrator:orchestrator_dev@localhost:5432/ai_orchestrator"

    # ---------- Redis ----------
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---------- CORS ----------
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    # ---------- LLM API Keys ----------
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # ---------- Embedding ----------
    EMBEDDING_PROVIDER: str = "openai"  # "openai" or "local"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536  # text-embedding-3-small dimension
    LOCAL_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # sentence-transformers model

    # ---------- Semantic Cache ----------
    CACHE_SIMILARITY_THRESHOLD: float = 0.92
    CACHE_TTL_SECONDS: int = 86400  # 24 hours default
    CACHE_ENABLE_WORKFLOW_VALIDATION: bool = True

    # ---------- Execution Engine ----------
    MAX_RETRIES: int = 3                     # attempts per model before falling back
    RETRY_BACKOFF_BASE: int = 2
    RETRY_BACKOFF_INITIAL_SECONDS: float = 1.0  # wait before retry n = initial * base**(n-1)
    RATE_LIMIT_BACKOFF_SECONDS: float = 30.0    # wait after a rate-limit error
    STAGE_TIMEOUT_SECONDS: int = 120            # per LLM attempt
    CIRCUIT_BREAKER_THRESHOLD: int = 5          # consecutive failures that open a provider's circuit
    CIRCUIT_BREAKER_TIMEOUT: int = 60           # seconds before an open circuit lets a trial call through
    MAX_PARALLEL_STAGES: int = 4                # concurrent stages per execution

    # ---------- Authentication ----------
    SESSION_SECRET_KEY: str = "change-me-in-production"
    SESSION_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60

    # ---------- SMTP (Email) ----------
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@example.com"
    SMTP_FROM_NAME: str = "AI Orchestrator"

    # ---------- Frontend URL ----------
    FRONTEND_URL: str = "http://localhost:5173"

    # ---------- Workspace & Project Builder ----------
    WORKSPACE_ROOT: str = "/var/projects"
    MAX_FILE_SIZE_MB: int = 10
    MAX_WORKSPACE_SIZE_MB: int = 500
    MAX_FILES_PER_WORKSPACE: int = 1000
    ALLOWED_FILE_EXTENSIONS: str = ".py,.js,.ts,.tsx,.jsx,.json,.yaml,.yml,.md,.txt,.html,.css,.sh,.toml,.ini,.xml,.go,.rs,.rb,.csv,.sql"

    # ---------- Project Builder sandbox ----------
    # The runner service that executes generated projects in isolated containers.
    # Empty URL = no sandbox: builds are reported as "unavailable", never as succeeded.
    SANDBOX_RUNNER_URL: str = ""
    SANDBOX_RUNNER_TOKEN: str = ""
    PROJECT_MAX_REPAIR_ATTEMPTS: int = 3


# Singleton instance — import this everywhere
settings = Settings()
