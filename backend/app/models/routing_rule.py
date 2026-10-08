"""RoutingRule and RoutingDecision ORM models — per-stage-type routing config and the decision log."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Integer, Boolean, DateTime, Numeric, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class RoutingRule(Base):
    """How to pick a model for one stage type."""
    __tablename__ = "routing_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid(), default=uuid.uuid4)
    stage_type: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    priority_factor: Mapped[str] = mapped_column(String(50), default="balanced", server_default="balanced")  # cost, speed, quality, balanced

    # Constraints on candidate models
    max_cost_per_call: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)  # for a typical 1K in / 500 out call
    max_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_capability_score: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.80"), server_default="0.80")

    preferred_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="SET NULL"), nullable=True)
    fallback_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="SET NULL"), nullable=True)

    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    preferred_model = relationship("ModelProfile", foreign_keys=[preferred_model_id], lazy="selectin")
    fallback_model = relationship("ModelProfile", foreign_keys=[fallback_model_id], lazy="selectin")

    __table_args__ = (
        Index("idx_routing_rules_is_active", "is_active"),
    )


class RoutingDecision(Base):
    """One routing decision: which model a stage was sent to in an execution, and why."""
    __tablename__ = "routing_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid(), default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    stage_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stages.id", ondelete="CASCADE"), nullable=False)
    stage_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    selected_model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="SET NULL"), nullable=True)
    selected_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    selected_model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    selection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    priority_factor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    alternatives_considered: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    was_user_override: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    was_fallback: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_routing_decisions_execution_id", "execution_id"),
        Index("idx_routing_decisions_stage_type", "stage_type"),
    )
