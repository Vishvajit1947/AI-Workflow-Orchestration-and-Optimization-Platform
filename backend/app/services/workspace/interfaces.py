"""
Workspace adapter interface.

Defines the protocol for workspace implementations, enabling:
- Server-side filesystem (current implementation)
- Local agent on user's machine (future)
- Cloud storage backends (future)
"""

from pathlib import Path
from typing import Protocol, List, Dict, Any, Optional


class WorkspaceAdapter(Protocol):
    """
    Protocol defining workspace operations.

    All implementations must support these operations for creating, reading,
    writing, and managing files within isolated workspaces.
    """

    async def create_workspace(
        self, user_id: str, project_id: str, project_name: str
    ) -> Path:
        """
        Create a new workspace directory.

        Args:
            user_id: User UUID as string
            project_id: Project UUID as string
            project_name: Human-readable project name

        Returns:
            Absolute path to created workspace

        Raises:
            WorkspaceError: If workspace creation fails
        """
        ...

    async def workspace_exists(self, workspace_path: Path) -> bool:
        """
        Check if workspace directory exists.

        Args:
            workspace_path: Absolute workspace path

        Returns:
            True if workspace exists
        """
        ...

    async def delete_workspace(self, workspace_path: Path) -> None:
        """
        Delete entire workspace directory.

        Args:
            workspace_path: Absolute workspace path

        Raises:
            WorkspaceNotFoundError: If workspace doesn't exist
            FileOperationError: If deletion fails
        """
        ...

    async def path_exists(
        self, workspace_path: Path, relative_path: str
    ) -> bool:
        """
        Check if a file or directory exists within workspace.

        Args:
            workspace_path: Absolute workspace path
            relative_path: Path relative to workspace root

        Returns:
            True if path exists
        """
        ...

    async def is_directory(
        self, workspace_path: Path, relative_path: str
    ) -> bool:
        """
        Check if path is a directory.

        Args:
            workspace_path: Absolute workspace path
            relative_path: Path relative to workspace root

        Returns:
            True if path exists and is a directory
        """
        ...

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
        ...

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
        ...

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
        ...

    async def list_files(
        self, workspace_path: Path, relative_path: str = ""
    ) -> List[Dict[str, Any]]:
        """
        List files and directories in a directory.

        Args:
            workspace_path: Absolute workspace path
            relative_path: Directory path relative to workspace root (empty for root)

        Returns:
            List of file/directory metadata dictionaries with keys:
            - name: str
            - path: str (relative to workspace)
            - is_directory: bool
            - size_bytes: int (0 for directories)
            - created_at: datetime (if available)
            - updated_at: datetime (if available)

        Raises:
            WorkspaceSecurityError: If path validation fails
            FileNotFoundError: If directory doesn't exist
            FileOperationError: If listing fails
        """
        ...

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
        ...

    async def get_tree(
        self, workspace_path: Path, max_depth: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get complete directory tree structure.

        Args:
            workspace_path: Absolute workspace path
            max_depth: Maximum depth to traverse (None for unlimited)

        Returns:
            Tree structure as nested dict:
            {
                "name": str,
                "path": str,
                "is_directory": bool,
                "size_bytes": int,
                "children": List[Dict] (for directories)
            }

        Raises:
            WorkspaceSecurityError: If path validation fails
            FileOperationError: If tree generation fails
        """
        ...

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
        ...

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
        ...
