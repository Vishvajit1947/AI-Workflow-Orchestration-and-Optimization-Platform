"""
Workspace-related exceptions.

Clear error hierarchy for workspace operations with security, quota, and I/O errors.
"""


class WorkspaceError(Exception):
    """Base exception for all workspace-related errors."""
    pass


class WorkspaceNotFoundError(WorkspaceError):
    """Workspace does not exist or cannot be accessed."""
    pass


class WorkspaceSecurityError(WorkspaceError):
    """Security violation detected in workspace operation (path traversal, unauthorized access)."""
    pass


class WorkspaceQuotaExceededError(WorkspaceError):
    """Workspace quota exceeded (file size, total size, or file count)."""
    pass


class FileOperationError(WorkspaceError):
    """File operation failed (I/O error, permission denied, etc.)."""
    pass
