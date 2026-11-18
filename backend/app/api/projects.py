"""
Project Builder API: the caller's generated projects, their files, build history and ZIP.

Mounted behind authentication (see api/__init__.py); every lookup is scoped to the
caller through ProjectWorkspaceService, so another user's project is a 404.
"""
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.artifacts.document import ExportError
from backend.app.artifacts.service import language_for_path
from backend.app.artifacts.zip_generator import safe_filename
from backend.app.core.dependencies import get_current_active_user
from backend.app.database import get_db
from backend.app.models.project import Project, ProjectRun
from backend.app.models.user import User
from backend.app.services.project_builder.workspace import ProjectPathError, ProjectWorkspaceService

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectRunOut(BaseModel):
    id: uuid.UUID
    execution_id: Optional[uuid.UUID]
    status: str
    project_type: Optional[str]
    current_step: Optional[str]
    steps: list[dict]
    repairs: list[dict]
    warnings: list[str]
    error_summary: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    status: str
    project_type: Optional[str]
    workflow_id: Optional[uuid.UUID]
    execution_id: Optional[uuid.UUID]
    file_count: int
    created_at: datetime
    updated_at: datetime
    latest_run: Optional[ProjectRunOut] = None


class ProjectFileOut(BaseModel):
    path: str
    size: int
    language: str
    content: Optional[str]  # None for binary or oversized files


def _service(db: AsyncSession, user: User) -> ProjectWorkspaceService:
    return ProjectWorkspaceService(db, user.id)


async def _latest_run(db: AsyncSession, project_id: uuid.UUID) -> Optional[ProjectRun]:
    return (await db.execute(
        select(ProjectRun).where(ProjectRun.project_id == project_id)
        .order_by(ProjectRun.started_at.desc()).limit(1)
    )).scalar_one_or_none()


async def _out(db: AsyncSession, project: Project, with_run: bool) -> ProjectOut:
    run = await _latest_run(db, project.id) if with_run else None
    return ProjectOut(
        id=project.id, name=project.name, description=project.description, status=project.status,
        project_type=project.project_type, workflow_id=project.workflow_id, execution_id=project.execution_id,
        file_count=project.workspace.file_count if project.workspace else 0,
        created_at=project.created_at, updated_at=project.updated_at,
        latest_run=ProjectRunOut.model_validate(run) if run else None,
    )


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    workflow_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """The caller's projects, most recently updated first (optionally for one workflow)."""
    service = _service(db, current_user)
    projects = await service.list_projects(workflow_id)
    out = []
    for p in projects:
        out.append(await _out(db, await service.get_project(p.id), with_run=True))
    return out


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(get_current_active_user)):
    return await _out(db, await _service(db, current_user).get_project(project_id), with_run=True)


@router.get("/{project_id}/runs", response_model=list[ProjectRunOut])
async def list_runs(project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    current_user: User = Depends(get_current_active_user)):
    """Build history, newest first."""
    project = await _service(db, current_user).get_project(project_id)
    runs = (await db.execute(
        select(ProjectRun).where(ProjectRun.project_id == project.id).order_by(ProjectRun.started_at.desc())
    )).scalars().all()
    return [ProjectRunOut.model_validate(r) for r in runs]


@router.get("/{project_id}/files", response_model=list[ProjectFileOut])
async def list_files(project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     current_user: User = Depends(get_current_active_user)):
    """Every file in the workspace, with text contents, for the file explorer."""
    service = _service(db, current_user)
    project = await service.get_project(project_id)
    texts = await service.read_all(project)
    return [ProjectFileOut(path=f["path"], size=f["size"], language=language_for_path(f["path"]),
                           content=texts.get(f["path"]))
            for f in await service.list_files(project)]


@router.get("/{project_id}/files/content")
async def read_file(project_id: uuid.UUID, path: str = Query(...), db: AsyncSession = Depends(get_db),
                    current_user: User = Depends(get_current_active_user)):
    service = _service(db, current_user)
    project = await service.get_project(project_id)
    try:
        return {"path": path, "content": await service.read_file(project, path)}
    except ProjectPathError as e:
        raise HTTPException(status_code=400, detail=f"Invalid path: {e}")


@router.get("/{project_id}/download")
async def download(project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                   current_user: User = Depends(get_current_active_user)):
    """The project's current files as a ZIP (no regeneration needed)."""
    service = _service(db, current_user)
    project = await service.get_project(project_id)
    try:
        content = await service.export_zip(project)
    except ExportError as e:
        raise HTTPException(status_code=422, detail=f"Could not create ZIP: {e}")
    filename = f"{safe_filename(project.name, 'project')}.zip"
    return Response(content=content, media_type="application/zip", headers={
        "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}",
    })
