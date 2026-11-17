"""
Workspace management services.

Provides filesystem abstraction for project workspaces with security boundaries,
user isolation, and support for multiple backend implementations.
"""

from .exceptions import (
    WorkspaceError,
    WorkspaceNotFoundError,
    WorkspaceSecurityError,
    WorkspaceQuotaExceededError,
    FileOperationError,
)
from .interfaces import WorkspaceAdapter

__all__ = [
    "WorkspaceError",
    "WorkspaceNotFoundError",
    "WorkspaceSecurityError",
    "WorkspaceQuotaExceededError",
    "FileOperationError",
    "WorkspaceAdapter",
]
