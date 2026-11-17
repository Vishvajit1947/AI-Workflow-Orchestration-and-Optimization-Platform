"""
Local server-side workspace adapter.

Implements workspace operations on the server's filesystem under a
configured root directory with user isolation and security boundaries.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional

import aiofiles.os

from .exceptions import (
    WorkspaceError,
    WorkspaceNotFoundError,
    WorkspaceQuotaExceededError,
    FileOperationError,
)
from .file_operations import FileOperations
from .security import WorkspaceSecurity


class LocalServerWorkspaceAdapter:
    """
    Server-side filesystem workspace implementation.

    Creates workspaces under: {root}/{user_id}/{project_id}/
    """

    def __init__(
        self,
        workspace_root: str | Path,
        max_file_size_mb: int = 10,
        max_workspace_size_mb: int = 500,
    ):
        """
        Initialize local server workspace adapter.

        Args:
            workspace_root: Root directory for all workspaces
            max_file_size_mb: Maximum individual file size in MB
            max_workspace_size_mb: Maximum total workspace size in MB
        """
        self.workspace_root = Path(workspace_root).resolve()
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.max_workspace_size = max_workspace_size_mb * 1024 * 1024

        # Validate workspace root
        WorkspaceSecurity.validate_workspace_root(self.workspace_root)

    async def create_workspace(
        self, user_id: str, project_id: str, project_name: str
    ) -> Path:
        """
        Create a new workspace directory.

        Structure: {root}/{user_id}/{project_id}/

        Args:
            user_id: User UUID as string
            project_id: Project UUID as string
            project_name: Human-readable project name (for logging)

        Returns:
            Absolute path to created workspace

        Raises:
            WorkspaceError: If workspace creation fails
        """
        try:
            # Sanitize IDs
            safe_user_id = WorkspaceSecurity.sanitize_filename(user_id)
            safe_project_id = WorkspaceSecurity.sanitize_filename(project_id)

            # Create workspace path
            workspace_path = self.workspace_root / safe_user_id / safe_project_id

            # Create directory
            await FileOperations.ensure_directory(workspace_path)

            return workspace_path
        except Exception as e:
            raise WorkspaceError(
                f"Failed to create workspace for project {project_id}: {e}"
            ) from e

    async def workspace_exists(self, workspace_path: Path) -> bool:
        """
        Check if workspace directory exists.

        Args:
            workspace_path: Absolute workspace path

        Returns:
            True if workspace exists
        """
        try:
            return await aiofiles.os.path.exists(workspace_path) and await aiofiles.os.path.isdir(
                workspace_path
            )
        except Exception:
            return False

    async def delete_workspace(self, workspace_path: Path) -> None:
        """
        Delete entire workspace directory.

        Args:
            workspace_path: Absolute workspace path

        Raises:
            WorkspaceNotFoundError: If workspace doesn't exist
            FileOperationError: If deletion fails
        """
        if not await self.workspace_exists(workspace_path):
            raise WorkspaceNotFoundError(f"Workspace does not exist: {workspace_path}")

        try:
            await FileOperations.delete_path(workspace_path, recursive=True)
        except Exception as e:
            raise FileOperationError(
                f"Failed to delete workspace {workspace_path}: {e}"
            ) from e

    async def path_exists(self, workspace_path: Path, relative_path: str) -> bool:
        """
        Check if a file or directory exists within workspace.

        Args:
            workspace_path: Absolute workspace path
            relative_path: Path relative to workspace root

        Returns:
            True if path exists
        """
        try:
            target = WorkspaceSecurity.resolve_workspace_path(
                workspace_path, relative_path
            )
            return await aiofiles.os.path.exists(target)
        except Exception:
            return False

    async def is_directory(self, workspace_path: Path, relative_path: str) -> bool:
        """
        Check if path is a directory.

        Args:
            workspace_path: Absolute workspace path
            relative_path: Path relative to workspace root

        Returns:
            True if path exists and is a directory
        """
        try:
            target = WorkspaceSecurity.resolve_workspace_path(
                workspace_path, relative_path
            )
            return await aiofiles.os.path.isdir(target)
        except Exception:
            return False

    async def create_directory(
        self, workspace_path: Path, relative_path: str
    ) -> None:
        """
        Create directory, including any necessary parent directories.

        Args:
            workspace_path: Absolute workspace path
            relative_path: Directory path relative to workspace root

        Raises:
            WorkspaceSecurityError: If path validation fails
            FileOperationError: If directory creation fails
        """
        target = WorkspaceSecurity.resolve_workspace_path(
            workspace_path, relative_path
        )
        await FileOperations.ensure_directory(target)

    async def write_file(
        self,
        workspace_path: Path,
        relative_path: str,
        content: bytes | str,
        create_parents: bool = True,
    ) -> None:
        """
        Write content to a file, creating parent directories if needed.

        Args:
            workspace_path: Absolute workspace path
            relative_path: File path relative to workspace root
            content: File content (str for text, bytes for binary)
            create_parents: Create parent directories if they don't exist

        Raises:
            WorkspaceSecurityError: If path validation fails
            WorkspaceQuotaExceededError: If file size exceeds limits
            FileOperationError: If write fails
        """
        # Resolve and validate path
        target = WorkspaceSecurity.resolve_workspace_path(
            workspace_path, relative_path
        )

        # Create parent directories if needed
        if create_parents:
            await FileOperations.ensure_directory(target.parent)

        # Check workspace size limit
        current_size = await FileOperations.calculate_directory_size(workspace_path)
        if isinstance(content, str):
            new_file_size = len(content.encode("utf-8"))
        else:
            new_file_size = len(content)

        if current_size + new_file_size > self.max_workspace_size:
            raise WorkspaceQuotaExceededError(
                f"Workspace size would exceed limit: "
                f"{current_size + new_file_size} > {self.max_workspace_size}"
            )

        # Write file
        if isinstance(content, str):
            await FileOperations.write_text(target, content, max_size=self.max_file_size)
        else:
            await FileOperations.write_bytes(target, content, max_size=self.max_file_size)

    async def read_file(
        self, workspace_path: Path, relative_path: str, binary: bool = False
    ) -> bytes | str:
        """
        Read file content.

        Args:
            workspace_path: Absolute workspace path
            relative_path: File path relative to workspace root
            binary: If True, return bytes; if False, return str

        Returns:
            File content as bytes or string

        Raises:
            WorkspaceSecurityError: If path validation fails
            FileNotFoundError: If file doesn't exist
            FileOperationError: If read fails
        """
        target = WorkspaceSecurity.resolve_workspace_path(
            workspace_path, relative_path, must_exist=True
        )

        if binary:
            return await FileOperations.read_bytes(target)
        else:
            return await FileOperations.read_text(target)

    async def list_files(
        self, workspace_path: Path, relative_path: str = ""
    ) -> List[Dict[str, Any]]:
        """
        List files and directories in a directory.

        Args:
            workspace_path: Absolute workspace path
            relative_path: Directory path relative to workspace root (empty for root)

        Returns:
            List of file/directory metadata dictionaries

        Raises:
            WorkspaceSecurityError: If path validation fails
            FileNotFoundError: If directory doesn't exist
            FileOperationError: If listing fails
        """
        if relative_path:
            target = WorkspaceSecurity.resolve_workspace_path(
                workspace_path, relative_path, must_exist=True
            )
        else:
            target = workspace_path

        entries = await FileOperations.list_directory(target)

        # Convert absolute paths to relative paths
        for entry in entries:
            abs_path = Path(entry["path"])
            try:
                rel_path = abs_path.relative_to(workspace_path)
                entry["path"] = str(rel_path)
            except ValueError:
                # Path is outside workspace (shouldn't happen, but be safe)
                entry["path"] = entry["name"]

        return entries

    async def delete_path(
        self, workspace_path: Path, relative_path: str, recursive: bool = False
    ) -> None:
        """
        Delete a file or directory.

        Args:
            workspace_path: Absolute workspace path
            relative_path: Path relative to workspace root
            recursive: If True, delete directories recursively

        Raises:
            WorkspaceSecurityError: If path validation fails
            FileNotFoundError: If path doesn't exist
            FileOperationError: If deletion fails
        """
        target = WorkspaceSecurity.resolve_workspace_path(
            workspace_path, relative_path, must_exist=True
        )

        await FileOperations.delete_path(target, recursive=recursive)

    async def get_tree(
        self, workspace_path: Path, max_depth: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get complete directory tree structure.

        Args:
            workspace_path: Absolute workspace path
            max_depth: Maximum depth to traverse (None for unlimited)

        Returns:
            Tree structure as nested dict

        Raises:
            WorkspaceSecurityError: If path validation fails
            FileOperationError: If tree generation fails
        """
        tree = await FileOperations.build_tree(workspace_path, max_depth)

        # Convert absolute paths to relative
        def make_relative(node: dict, base: Path):
            abs_path = Path(node["path"])
            try:
                rel_path = abs_path.relative_to(base)
                node["path"] = str(rel_path) if str(rel_path) != "." else ""
            except ValueError:
                node["path"] = node["name"]

            if "children" in node:
                for child in node["children"]:
                    make_relative(child, base)

        make_relative(tree, workspace_path)
        return tree

    async def get_disk_usage(self, workspace_path: Path) -> int:
        """
        Calculate total disk usage of workspace in bytes.

        Args:
            workspace_path: Absolute workspace path

        Returns:
            Total size in bytes

        Raises:
            WorkspaceNotFoundError: If workspace doesn't exist
            FileOperationError: If calculation fails
        """
        if not await self.workspace_exists(workspace_path):
            raise WorkspaceNotFoundError(f"Workspace does not exist: {workspace_path}")

        return await FileOperations.calculate_directory_size(workspace_path)

    async def move_path(
        self,
        workspace_path: Path,
        source_path: str,
        destination_path: str,
    ) -> None:
        """
        Move/rename a file or directory within workspace.

        Args:
            workspace_path: Absolute workspace path
            source_path: Source path relative to workspace root
            destination_path: Destination path relative to workspace root

        Raises:
            WorkspaceSecurityError: If path validation fails
            FileNotFoundError: If source doesn't exist
            FileOperationError: If move fails
        """
        source = WorkspaceSecurity.resolve_workspace_path(
            workspace_path, source_path, must_exist=True
        )
        destination = WorkspaceSecurity.resolve_workspace_path(
            workspace_path, destination_path
        )

        # Ensure destination parent exists
        await FileOperations.ensure_directory(destination.parent)

        await FileOperations.move_path(source, destination)
