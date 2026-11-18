"""
Workspace security utilities.

Path validation, sanitization, and boundary enforcement to prevent:
- Path traversal attacks (../)
- Symlink escapes
- Null byte injection
- Absolute path access
"""

import os
from pathlib import Path, PurePosixPath
from typing import Optional

from .exceptions import WorkspaceSecurityError


class WorkspaceSecurity:
    """Security utilities for workspace path validation and enforcement."""

    # Maximum allowed path length (filesystem and security limit)
    MAX_PATH_LENGTH = 4096

    # Characters that should never appear in paths
    FORBIDDEN_CHARS = {"\x00", "\n", "\r"}

    # Path components that are rejected
    FORBIDDEN_COMPONENTS = {".", "..", ""}

    @staticmethod
    def validate_relative_path(path: str) -> str:
        """
        Validate and normalize a relative path.

        Args:
            path: Relative path to validate

        Returns:
            Normalized relative path

        Raises:
            WorkspaceSecurityError: If path is invalid or dangerous
        """
        if not path or not path.strip():
            raise WorkspaceSecurityError("Path cannot be empty")

        # 1. Reject absolute paths
        if os.path.isabs(path):
            raise WorkspaceSecurityError(
                f"Absolute paths not allowed: {path}"
            )

        # 2. Check for forbidden characters
        for char in WorkspaceSecurity.FORBIDDEN_CHARS:
            if char in path:
                raise WorkspaceSecurityError(
                    f"Invalid character in path: {repr(char)}"
                )

        # 3. Normalize path (resolve .., ., etc.)
        normalized = os.path.normpath(path)

        # 4. Reject paths that escape workspace
        if normalized.startswith("..") or normalized.startswith(os.sep):
            raise WorkspaceSecurityError(
                f"Path traversal detected: {path}"
            )

        # 5. Check path length
        if len(normalized) > WorkspaceSecurity.MAX_PATH_LENGTH:
            raise WorkspaceSecurityError(
                f"Path too long: {len(normalized)} > {WorkspaceSecurity.MAX_PATH_LENGTH}"
            )

        # 6. Reject dangerous path components
        components = normalized.split(os.sep)
        for component in components:
            if component in WorkspaceSecurity.FORBIDDEN_COMPONENTS:
                continue  # Already normalized, but double-check
            # Reject paths with only dots (., .., ..., etc.)
            if component and all(c == "." for c in component):
                raise WorkspaceSecurityError(
                    f"Invalid path component: {component}"
                )

        return normalized

    @staticmethod
    def resolve_workspace_path(
        workspace_root: Path,
        relative_path: str,
        must_exist: bool = False,
    ) -> Path:
        """
        Resolve relative path within workspace and enforce boundaries.

        Args:
            workspace_root: Absolute workspace root directory
            relative_path: Relative path within workspace
            must_exist: If True, raise error if path doesn't exist

        Returns:
            Absolute resolved path within workspace

        Raises:
            WorkspaceSecurityError: If path escapes workspace or fails validation
            FileNotFoundError: If must_exist=True and path doesn't exist
        """
        # Validate input path
        validated = WorkspaceSecurity.validate_relative_path(relative_path)

        # Resolve absolute path
        target = (workspace_root / validated).resolve()

        # Ensure resolved path is still within workspace
        # Use resolve() on both to handle symlinks consistently
        try:
            target.relative_to(workspace_root.resolve())
        except ValueError:
            raise WorkspaceSecurityError(
                f"Path escapes workspace boundary: {relative_path}"
            )

        # Check existence if required
        if must_exist and not target.exists():
            raise FileNotFoundError(f"Path does not exist: {relative_path}")

        return target

    @staticmethod
    def validate_workspace_root(root: Path) -> None:
        """
        Validate that a workspace root is safe and accessible.

        Args:
            root: Proposed workspace root path

        Raises:
            WorkspaceSecurityError: If root is invalid or dangerous
        """
        # System locations, compared as POSIX paths so the check behaves the same on every
        # OS. "/" itself is rejected, but not everything under it (that is every path).
        posix = PurePosixPath(root.as_posix())
        if posix == PurePosixPath("/"):
            raise WorkspaceSecurityError(f"Workspace root cannot be a system directory: {root}")
        for danger in ("/etc", "/usr", "/bin", "/sbin", "/boot", "/sys", "/proc", "/dev"):
            if posix == PurePosixPath(danger) or PurePosixPath(danger) in posix.parents:
                raise WorkspaceSecurityError(f"Workspace root cannot be in system directory: {root}")

        if not root.is_absolute():
            raise WorkspaceSecurityError(
                f"Workspace root must be absolute: {root}"
            )

        # Repeat the check after resolving symlinks (e.g. a link that points into /etc)
        resolved = PurePosixPath(root.resolve().as_posix())
        for danger in ("/etc", "/usr", "/bin", "/sbin", "/boot", "/sys", "/proc", "/dev"):
            if resolved == PurePosixPath(danger) or PurePosixPath(danger) in resolved.parents:
                raise WorkspaceSecurityError(f"Workspace root cannot be in system directory: {root}")

    @staticmethod
    def sanitize_filename(filename: str, max_length: int = 255) -> str:
        """
        Sanitize a filename by removing/replacing dangerous characters.

        Args:
            filename: Original filename
            max_length: Maximum allowed length

        Returns:
            Sanitized filename

        Raises:
            WorkspaceSecurityError: If filename is invalid
        """
        if not filename or not filename.strip():
            raise WorkspaceSecurityError("Filename cannot be empty")

        # Remove directory separators
        sanitized = filename.replace(os.sep, "_").replace("/", "_").replace("\\", "_")

        # Remove forbidden characters
        for char in WorkspaceSecurity.FORBIDDEN_CHARS:
            sanitized = sanitized.replace(char, "")

        # Remove underscores that came from separator-only names
        if all(c in ("_", " ", ".") for c in sanitized):
            sanitized = ""

        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip(". ")

        if not sanitized:
            raise WorkspaceSecurityError(
                f"Filename becomes empty after sanitization: {filename}"
            )

        # Truncate if too long
        if len(sanitized) > max_length:
            # Preserve extension if possible
            parts = sanitized.rsplit(".", 1)
            if len(parts) == 2:
                name, ext = parts
                name = name[: max_length - len(ext) - 1]
                sanitized = f"{name}.{ext}"
            else:
                sanitized = sanitized[:max_length]

        return sanitized
