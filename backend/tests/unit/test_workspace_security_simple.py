"""
Standalone unit tests for workspace security (no app dependencies).

Tests path validation, sanitization, and boundary enforcement.
"""

import os
import sys
import pytest
from pathlib import Path

# Add backend to path for direct imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.workspace.security import WorkspaceSecurity
from app.services.workspace.exceptions import WorkspaceSecurityError


class TestValidateRelativePath:
    """Tests for relative path validation."""

    def test_valid_simple_path(self):
        """Simple filename should pass validation."""
        result = WorkspaceSecurity.validate_relative_path("file.txt")
        assert result == "file.txt"

    def test_valid_nested_path(self):
        """Nested directory structure should pass validation."""
        result = WorkspaceSecurity.validate_relative_path("src/app/main.py")
        assert result == os.path.normpath("src/app/main.py")

    def test_reject_empty_path(self):
        """Empty path should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="cannot be empty"):
            WorkspaceSecurity.validate_relative_path("")

    def test_reject_absolute_path(self):
        """Absolute paths should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="Absolute paths not allowed"):
            WorkspaceSecurity.validate_relative_path("/etc/passwd")

    def test_reject_parent_directory_traversal(self):
        """Parent directory traversal should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="Path traversal detected"):
            WorkspaceSecurity.validate_relative_path("../../../etc/passwd")

    def test_reject_null_byte(self):
        """Null byte injection should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="Invalid character"):
            WorkspaceSecurity.validate_relative_path("file\x00.txt")

    def test_normalize_current_directory(self):
        """Current directory references should be normalized."""
        result = WorkspaceSecurity.validate_relative_path("./src/./app/./main.py")
        assert result == os.path.normpath("src/app/main.py")


class TestResolveWorkspacePath:
    """Tests for workspace path resolution with boundary enforcement."""

    def test_resolve_simple_file(self, tmp_path):
        """Simple file path should resolve within workspace."""
        result = WorkspaceSecurity.resolve_workspace_path(tmp_path, "file.txt")
        assert result == tmp_path / "file.txt"

    def test_reject_traversal_attempt(self, tmp_path):
        """Path traversal should be blocked."""
        with pytest.raises(WorkspaceSecurityError, match="Path traversal detected"):
            WorkspaceSecurity.resolve_workspace_path(tmp_path, "../../../etc/passwd")

    def test_must_exist_raises_when_missing(self, tmp_path):
        """must_exist=True should raise FileNotFoundError for missing paths."""
        with pytest.raises(FileNotFoundError, match="does not exist"):
            WorkspaceSecurity.resolve_workspace_path(
                tmp_path, "nonexistent.txt", must_exist=True
            )


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_valid_filename_unchanged(self):
        """Valid filename should remain unchanged."""
        result = WorkspaceSecurity.sanitize_filename("document.txt")
        assert result == "document.txt"

    def test_remove_directory_separators(self):
        """Directory separators should be replaced with underscores."""
        result = WorkspaceSecurity.sanitize_filename("path/to/file.txt")
        assert "/" not in result
        assert result == "path_to_file.txt"

    def test_reject_empty_after_sanitization(self):
        """Filename that becomes empty should raise error."""
        with pytest.raises(WorkspaceSecurityError, match="empty after sanitization"):
            WorkspaceSecurity.sanitize_filename("///")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
