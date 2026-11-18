"""
Per-user project workspaces.

Files live on disk under {WORKSPACE_ROOT}/{user_id}/{project_id}/ (through the existing
LocalServerWorkspaceAdapter, which enforces path and size limits); the projects /
project_workspaces / project_files tables hold ownership and metadata.

Every method is scoped to `owner_id`: another user's project is a 404, exactly like a
project that does not exist. Paths are validated twice: with the artifact path rules
(relative, no '..', no reserved names) and by the adapter's boundary check.
"""
import asyncio
import hashlib
import os
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.artifacts.schemas import Artifact
from backend.app.artifacts.service import language_for_path
from backend.app.artifacts.validators import UnsafePathError, normalize_artifact_path
from backend.app.artifacts.zip_generator import build_zip
from backend.app.config import settings
from backend.app.core.ownership import not_found
from backend.app.models.project import Project, ProjectFile, ProjectWorkspace
from backend.app.services.workspace.local_server_adapter import LocalServerWorkspaceAdapter

# Folders created by installs/builds inside the sandbox never come back to the workspace,
# but skip them defensively when listing or exporting.
_SKIPPED_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".pytest_cache"}
_MAX_TEXT_BYTES = 1_000_000

_CONFIG_NAMES = {"package.json", "requirements.txt", "pyproject.toml", "tsconfig.json", ".gitignore",
                 ".env.example", "vite.config.ts", "vite.config.js", "dockerfile", "docker-compose.yml"}


class ProjectPathError(ValueError):
    """A file path that is not a safe path inside the project."""


def safe_project_path(path: str) -> str:
    try:
        return normalize_artifact_path(path)
    except UnsafePathError as e:
        raise ProjectPathError(str(e)) from e


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _file_type(path: str) -> str:
    name = path.rsplit("/", 1)[-1].lower()
    if name in _CONFIG_NAMES or name.endswith((".toml", ".ini", ".cfg", ".yml", ".yaml")):
        return "config"
    if name.endswith(".md"):
        return "docs"
    return "source"


_default_adapter: Optional[LocalServerWorkspaceAdapter] = None


def default_adapter() -> LocalServerWorkspaceAdapter:
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = LocalServerWorkspaceAdapter(
            settings.WORKSPACE_ROOT,
            max_file_size_mb=settings.MAX_FILE_SIZE_MB,
            max_workspace_size_mb=settings.MAX_WORKSPACE_SIZE_MB,
        )
    return _default_adapter


class ProjectWorkspaceService:
    def __init__(self, db: AsyncSession, owner_id: uuid.UUID,
                 adapter: Optional[LocalServerWorkspaceAdapter] = None):
        self.db = db
        self.owner_id = owner_id
        self.adapter = adapter or default_adapter()

    # ---------- projects ----------

    async def get_project(self, project_id: uuid.UUID) -> Project:
        project = (await self.db.execute(
            select(Project)
            .options(selectinload(Project.workspace))
            .where(Project.id == project_id, Project.user_id == self.owner_id)
        )).scalar_one_or_none()
        if project is None:
            raise not_found("Project")
        return project

    async def list_projects(self, workflow_id: Optional[uuid.UUID] = None) -> list[Project]:
        query = select(Project).where(Project.user_id == self.owner_id)
        if workflow_id:
            query = query.where(Project.workflow_id == workflow_id)
        return list((await self.db.execute(query.order_by(Project.updated_at.desc()))).scalars())

    async def project_for_workflow(self, workflow_id: uuid.UUID, name: str,
                                   description: Optional[str] = None) -> Project:
        """The workflow's project (one per workflow), creating it and its workspace if needed."""
        existing = (await self.db.execute(
            select(Project).options(selectinload(Project.workspace))
            .where(Project.workflow_id == workflow_id, Project.user_id == self.owner_id)
        )).scalar_one_or_none()
        if existing is not None:
            return existing
        project = Project(user_id=self.owner_id, name=name[:255], description=description,
                          workflow_id=workflow_id, status="initializing")
        self.db.add(project)
        await self.db.flush()
        path = await self.adapter.create_workspace(str(self.owner_id), str(project.id), project.name)
        project.workspace = ProjectWorkspace(project_id=project.id, workspace_path=str(path))
        await self.db.flush()
        return project

    def _root(self, project: Project) -> Path:
        if project.workspace is None:
            raise not_found("Project workspace")
        return Path(project.workspace.workspace_path)

    def relative_workspace(self, project: Project) -> str:
        """Workspace location relative to the workspace root, "{user_id}/{project_id}"."""
        return f"{self.owner_id}/{project.id}"

    # ---------- files ----------

    async def replace_files(self, project: Project, files: list[dict]) -> None:
        """Make the workspace contain exactly `files` ([{"path", "content"}]), recording metadata."""
        root = self._root(project)
        normalized = [(safe_project_path(f["path"]), f["content"]) for f in files]
        await asyncio.to_thread(_clear_directory, root)
        await self.db.execute(delete(ProjectFile).where(ProjectFile.workspace_id == project.workspace.id))
        for path, content in normalized:
            await self.adapter.write_file(root, path, content)
            self.db.add(ProjectFile(workspace_id=project.workspace.id, file_path=path, file_type=_file_type(path),
                                    size_bytes=len(content.encode("utf-8")), content_hash=_sha256(content)))
        await self._refresh_totals(project)

    async def read_file(self, project: Project, path: str) -> str:
        path = safe_project_path(path)
        try:
            return await self.adapter.read_file(self._root(project), path)
        except FileNotFoundError:
            raise not_found("File")

    async def file_exists(self, project: Project, path: str) -> bool:
        return await self.adapter.path_exists(self._root(project), safe_project_path(path))

    async def write_file(self, project: Project, path: str, content: str) -> str:
        """Create or overwrite one file; returns its SHA-256."""
        path = safe_project_path(path)
        await self.adapter.write_file(self._root(project), path, content)
        record = (await self.db.execute(
            select(ProjectFile).where(ProjectFile.workspace_id == project.workspace.id, ProjectFile.file_path == path)
        )).scalar_one_or_none()
        digest = _sha256(content)
        if record is None:
            self.db.add(ProjectFile(workspace_id=project.workspace.id, file_path=path, file_type=_file_type(path),
                                    size_bytes=len(content.encode("utf-8")), content_hash=digest))
        else:
            record.size_bytes, record.content_hash = len(content.encode("utf-8")), digest
        await self._refresh_totals(project)
        return digest

    async def delete_file(self, project: Project, path: str) -> None:
        path = safe_project_path(path)
        root = self._root(project)
        if not await self.adapter.path_exists(root, path):
            raise not_found("File")
        await self.adapter.delete_path(root, path)
        await self.db.execute(delete(ProjectFile).where(
            ProjectFile.workspace_id == project.workspace.id, ProjectFile.file_path == path))
        await self._refresh_totals(project)

    async def list_files(self, project: Project) -> list[dict]:
        """[{"path", "size"}] for every regular file, sorted by path."""
        return await asyncio.to_thread(_walk, self._root(project))

    async def read_all(self, project: Project) -> dict[str, str]:
        """{path: text} for every text file (binary or oversized files are skipped)."""
        root = self._root(project)
        out: dict[str, str] = {}
        for f in await self.list_files(project):
            if f["size"] > _MAX_TEXT_BYTES:
                continue
            try:
                out[f["path"]] = await self.adapter.read_file(root, f["path"])
            except Exception:  # binary or unreadable: not shown as text
                continue
        return out

    async def as_artifact(self, project: Project) -> Artifact:
        files = await self.read_all(project)
        return Artifact.model_validate({
            "artifact_type": "project",
            "name": project.name,
            "files": [{"path": p, "content": c, "language": language_for_path(p)} for p, c in sorted(files.items())],
        })

    async def export_zip(self, project: Project) -> bytes:
        """The workspace as a ZIP (same packaging as artifact downloads)."""
        return build_zip(await self.as_artifact(project))

    async def _refresh_totals(self, project: Project) -> None:
        files = await self.list_files(project)
        project.workspace.file_count = len(files)
        project.workspace.disk_usage_bytes = sum(f["size"] for f in files)
        await self.db.flush()


def _clear_directory(root: Path) -> None:
    """Remove everything inside `root` (not root itself); never follows symlinks."""
    import shutil
    for entry in os.scandir(root):
        if entry.is_symlink() or entry.is_file():
            os.unlink(entry.path)
        elif entry.is_dir():
            shutil.rmtree(entry.path)


def _walk(root: Path) -> list[dict]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIPPED_DIRS)
        for name in sorted(filenames):
            full = Path(dirpath) / name
            if full.is_symlink() or not full.is_file():
                continue
            out.append({"path": full.relative_to(root).as_posix(), "size": full.stat().st_size})
    return sorted(out, key=lambda f: f["path"])
