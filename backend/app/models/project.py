"""
Project ORM model.

Represents user projects that can have generated code,
workspaces, and file tracking.
"""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'python', 'nodejs', 'react', etc.
    status: Mapped[str] = mapped_column(
        String(50), default="initializing", server_default="initializing"
    )
    # Status: initializing, active, archived, failed

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")  # type: ignore
    workspace: Mapped["ProjectWorkspace"] = relationship(  # type: ignore
        "ProjectWorkspace",
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,  # One-to-one relationship
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"


class ProjectWorkspace(Base):
    __tablename__ = "project_workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    workspace_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    disk_usage_bytes: Mapped[int] = mapped_column(
        default=0, server_default="0"
    )
    file_count: Mapped[int] = mapped_column(default=0, server_default="0")
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="workspace")  # type: ignore
    files: Mapped[list["ProjectFile"]] = relationship(  # type: ignore
        "ProjectFile",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ProjectWorkspace(id={self.id}, project_id={self.project_id})>"


class ProjectFile(Base):
    __tablename__ = "project_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Relative to workspace root
    file_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # 'source', 'config', 'dependency', 'generated'
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # SHA-256

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    workspace: Mapped["ProjectWorkspace"] = relationship(  # type: ignore
        "ProjectWorkspace", back_populates="files"
    )

    def __repr__(self) -> str:
        return f"<ProjectFile(id={self.id}, path='{self.file_path}')>"
