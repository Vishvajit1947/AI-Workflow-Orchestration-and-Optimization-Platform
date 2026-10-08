"""
Cache Entry ORM model.
Stores LLM results with vector embeddings for semantic similarity search.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, Integer, DateTime, ForeignKey,
    Boolean, Numeric, Index, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from backend.app.database import Base


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=func.gen_random_uuid(), default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stages.id", ondelete="CASCADE"), nullable=True
    )
    stage_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    input_embedding: Mapped[list] = mapped_column(Vector(1536), nullable=False)

    result: Mapped[str] = mapped_column(Text, nullable=False)
    result_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    dependency_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    similarity_threshold: Mapped[float] = mapped_column(
        Numeric(4, 3), server_default="0.92", default=0.92
    )

    is_valid: Mapped[bool] = mapped_column(Boolean, server_default="true", default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # NOTE: Vector index is created manually in the Alembic migration because
    # SQLAlchemy's Index() does not reliably support ivfflat with postgresql_ops.
    __table_args__ = (
        Index("idx_cache_entries_stage_type", "stage_type"),
        Index("idx_cache_entries_is_valid", "is_valid"),
        Index("idx_cache_entries_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<CacheEntry(id={self.id}, stage_type={self.stage_type}, hits={self.hit_count})>"
