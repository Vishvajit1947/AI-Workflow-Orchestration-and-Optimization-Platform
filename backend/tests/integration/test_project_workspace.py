"""Project workspaces: file operations, metadata, ZIP export, user isolation, path safety."""
import io
import uuid
import zipfile

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from backend.app.models import ProjectFile, Workflow
from backend.app.services.project_builder.workspace import ProjectPathError, ProjectWorkspaceService
from backend.app.services.workspace.local_server_adapter import LocalServerWorkspaceAdapter
from backend.tests.conftest import create_user_with_session


@pytest.fixture
def adapter(tmp_path):
    return LocalServerWorkspaceAdapter(tmp_path / "projects")


@pytest.fixture
async def owned(db_session, test_user, adapter):
    workflow = Workflow(name="Student system")
    db_session.add(workflow)
    await db_session.flush()
    service = ProjectWorkspaceService(db_session, test_user.id, adapter)
    project = await service.project_for_workflow(workflow.id, "Student system")
    await service.replace_files(project, [
        {"path": "backend/main.py", "content": "print('hi')\n"},
        {"path": "backend/requirements.txt", "content": "fastapi\n"},
        {"path": "README.md", "content": "# Student system\n"},
    ])
    await db_session.commit()
    return service, project, workflow


async def test_workspace_is_created_under_user_and_project(owned, adapter, test_user):
    service, project, _ = owned
    root = adapter.workspace_root / str(test_user.id) / str(project.id)
    assert project.workspace.workspace_path == str(root)
    assert (root / "backend" / "main.py").read_text() == "print('hi')\n"


async def test_files_can_be_listed_read_updated_and_deleted(owned, db_session):
    service, project, _ = owned
    assert [f["path"] for f in await service.list_files(project)] == [
        "README.md", "backend/main.py", "backend/requirements.txt"]
    assert await service.read_file(project, "backend/main.py") == "print('hi')\n"

    await service.write_file(project, "backend/main.py", "print('fixed')\n")
    await service.write_file(project, "backend/routes/students.py", "ROUTES = []\n")
    assert await service.read_file(project, "backend/main.py") == "print('fixed')\n"
    await service.delete_file(project, "README.md")
    with pytest.raises(HTTPException) as e:
        await service.read_file(project, "README.md")
    assert e.value.status_code == 404

    paths = sorted((await db_session.execute(
        select(ProjectFile.file_path).where(ProjectFile.workspace_id == project.workspace.id))).scalars())
    assert paths == ["backend/main.py", "backend/requirements.txt", "backend/routes/students.py"]
    assert project.workspace.file_count == 3


async def test_replace_files_removes_stale_files(owned):
    service, project, _ = owned
    await service.replace_files(project, [{"path": "only.py", "content": "x = 1\n"}])
    assert [f["path"] for f in await service.list_files(project)] == ["only.py"]


@pytest.mark.parametrize("bad", ["../escape.py", "/etc/passwd", "a/../../b.py", "C:/x.py", "a\\..\\b.py", ""])
async def test_path_traversal_is_rejected(owned, bad, adapter):
    service, project, _ = owned
    with pytest.raises(ProjectPathError):
        await service.write_file(project, bad, "x")
    with pytest.raises(ProjectPathError):
        await service.read_file(project, bad)
    assert not (adapter.workspace_root.parent / "escape.py").exists()


async def test_zip_contains_the_workspace_files(owned):
    service, project, _ = owned
    archive = zipfile.ZipFile(io.BytesIO(await service.export_zip(project)))
    assert sorted(archive.namelist()) == [
        "student-system/README.md", "student-system/backend/main.py", "student-system/backend/requirements.txt"]
    assert archive.read("student-system/backend/main.py") == b"print('hi')\n"


async def test_other_users_cannot_reach_the_project(owned, db_session, adapter):
    _, project, workflow = owned
    other, _ = await create_user_with_session(db_session, f"other-{uuid.uuid4().hex[:6]}@example.com")
    other_service = ProjectWorkspaceService(db_session, other.id, adapter)
    with pytest.raises(HTTPException) as e:
        await other_service.get_project(project.id)
    assert e.value.status_code == 404
    assert await other_service.list_projects() == []
    assert await other_service.list_projects(workflow_id=workflow.id) == []


async def test_one_project_per_workflow(owned):
    service, project, workflow = owned
    again = await service.project_for_workflow(workflow.id, "ignored")
    assert again.id == project.id
