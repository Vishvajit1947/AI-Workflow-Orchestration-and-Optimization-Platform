"""ModelProfile ORM model — catalog entry for an LLM with capability scores, pricing and latency."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Integer, Boolean, DateTime, Numeric, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base

# Score assumed for a capability the profile doesn't list
DEFAULT_CAPABILITY_SCORE = 0.5


class ModelProfile(Base):
    __tablename__ = "model_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid(), default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # matches LLM provider_name: openai, anthropic, gemini, groq
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Capability scores 0.0-1.0, keyed by stage type (analysis, design, generation, ...) plus "reasoning"
    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    max_context_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Pricing per single token (USD)
    cost_per_input_token: Mapped[Decimal] = mapped_column(Numeric(12, 10), nullable=False)
    cost_per_output_token: Mapped[Decimal] = mapped_column(Numeric(12, 10), nullable=False)

    avg_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    supports_function_calling: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    strengths: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    limitations: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_model_profiles_provider", "provider"),
        Index("idx_model_profiles_is_available", "is_available"),
        Index("idx_model_profiles_provider_model", "provider", "model_name", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ModelProfile(provider={self.provider}, model={self.model_name})>"

    def get_capability_score(self, capability: str) -> float:
        """Score for a capability, DEFAULT_CAPABILITY_SCORE if the profile doesn't list it."""
        return float((self.capabilities or {}).get(capability, DEFAULT_CAPABILITY_SCORE))

    @property
    def avg_cost_per_token(self) -> Decimal:
        return (self.cost_per_input_token + self.cost_per_output_token) / 2

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        """Estimated USD cost for a call with the given token counts."""
        return Decimal(input_tokens) * self.cost_per_input_token + Decimal(output_tokens) * self.cost_per_output_token
