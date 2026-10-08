"""ExecutionRecord ORM model — tracks each stage's execution within a workflow run."""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, Integer, DateTime, Numeric, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base

class ExecutionRecord(Base):
    __tablename__ = "execution_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid(), default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    stage_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stages.id", ondelete="CASCADE"), nullable=True)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)  # groups all stages of one run
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, running, completed, failed, cached
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(default=False, server_default="false")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default="{}")

    # Relationships
    workflow = relationship("Workflow", back_populates="execution_records")
    stage = relationship("Stage", back_populates="execution_records")

    # Indexes
    __table_args__ = (
        Index("idx_execution_records_execution_id", "execution_id"),
        Index("idx_execution_records_workflow_id", "workflow_id"),
        Index("idx_execution_records_status", "status"),
        Index("idx_execution_records_created_at", "created_at"),
    )

    @property
    def duration_ms(self) -> int | None:
        """Calculate duration in milliseconds."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return (self.input_tokens or 0) + (self.output_tokens or 0)
