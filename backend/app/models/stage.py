"""
Stage and StageDependency ORM models.
A Stage is a single step within a Workflow.
StageDependency tracks which stages must complete before another can start.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Stage(Base):
    __tablename__ = "stages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    # Valid types: analysis, design, generation, testing, documentation, review, custom
    model_preference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    config: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    status: Mapped[str] = mapped_column(
        String(50), default="pending", server_default="pending"
    )
    # Valid statuses: pending, running, completed, failed, skipped, cached

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship(
        "Workflow", back_populates="stages"
    )

    # Dependencies: stages that THIS stage depends on (must complete before this one)
    dependencies: Mapped[list["StageDependency"]] = relationship(
        "StageDependency",
        foreign_keys="StageDependency.stage_id",
        back_populates="stage",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Dependents: stages that depend ON this stage
    dependents: Mapped[list["StageDependency"]] = relationship(
        "StageDependency",
        foreign_keys="StageDependency.depends_on_stage_id",
        back_populates="depends_on_stage",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    execution_records: Mapped[list["ExecutionRecord"]] = relationship(
        "ExecutionRecord",
        back_populates="stage",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Stage(id={self.id}, name='{self.name}', order={self.stage_order})>"


# Import needed for type hints in Stage relationships
from backend.app.models.workflow import Workflow  # noqa: E402


class StageDependency(Base):
    __tablename__ = "stage_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stages.id", ondelete="CASCADE"),
        nullable=False,
    )
    depends_on_stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stages.id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(
        String(50), default="sequential", server_default="sequential"
    )
    # Valid types: sequential, merge

    # Relationships
    stage: Mapped["Stage"] = relationship(
        "Stage",
        foreign_keys=[stage_id],
        back_populates="dependencies",
    )
    depends_on_stage: Mapped["Stage"] = relationship(
        "Stage",
        foreign_keys=[depends_on_stage_id],
        back_populates="dependents",
    )

    __table_args__ = (
        UniqueConstraint("stage_id", "depends_on_stage_id", name="uq_stage_dependency"),
    )

    def __repr__(self) -> str:
        return f"<StageDependency(stage={self.stage_id} depends_on={self.depends_on_stage_id})>"
