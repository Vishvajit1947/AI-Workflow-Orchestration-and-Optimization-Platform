"""
Unit tests for workspace security utilities.

Tests path validation, sanitization, and boundary enforcement to ensure
protection against path traversal, symlink escapes, and other attacks.
"""

import os
import pytest
from pathlib import Path
from backend.app.services.workspace.security import WorkspaceSecurity
from backend.app.services.workspace.exceptions import WorkspaceSecurityError


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

    def test_valid_path_with_dots_in_filename(self):
        """Filename with dots should be allowed."""
        result = WorkspaceSecurity.validate_relative_path("config.dev.json")
        assert result == "config.dev.json"

    def test_reject_empty_path(self):
        """Empty path should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="cannot be empty"):
            WorkspaceSecurity.validate_relative_path("")

    def test_reject_whitespace_only(self):
        """Whitespace-only path should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="cannot be empty"):
            WorkspaceSecurity.validate_relative_path("   ")

    def test_reject_absolute_unix_path(self):
        """Absolute Unix paths should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="Absolute paths not allowed"):
            WorkspaceSecurity.validate_relative_path("/etc/passwd")

    def test_reject_absolute_windows_path(self):
        """Absolute Windows paths should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="Absolute paths not allowed"):
            WorkspaceSecurity.validate_relative_path("C:\\Windows\\System32")

    def test_reject_parent_directory_traversal(self):
        """Parent directory traversal should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="Path traversal detected"):
            WorkspaceSecurity.validate_relative_path("../../../etc/passwd")

    def test_reject_subtle_traversal(self):
        """Subtle traversal attempts should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="Path traversal detected"):
            WorkspaceSecurity.validate_relative_path("src/../../etc/passwd")

    def test_reject_null_byte(self):
        """Null byte injection should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="Invalid character"):
            WorkspaceSecurity.validate_relative_path("file\x00.txt")

    def test_reject_newline(self):
        """Newline in path should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="Invalid character"):
            WorkspaceSecurity.validate_relative_path("file\nname.txt")

    def test_reject_carriage_return(self):
        """Carriage return in path should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="Invalid character"):
            WorkspaceSecurity.validate_relative_path("file\rname.txt")

    def test_reject_excessive_length(self):
        """Excessively long paths should be rejected."""
        long_path = "a/" * 3000  # Exceeds MAX_PATH_LENGTH
        with pytest.raises(WorkspaceSecurityError, match="Path too long"):
            WorkspaceSecurity.validate_relative_path(long_path)

    def test_normalize_current_directory(self):
        """Current directory references should be normalized."""
        result = WorkspaceSecurity.validate_relative_path("./src/./app/./main.py")
        assert result == os.path.normpath("src/app/main.py")

    def test_normalize_redundant_separators(self):
        """Redundant path separators should be normalized."""
        result = WorkspaceSecurity.validate_relative_path("src//app///main.py")
        assert result == os.path.normpath("src/app/main.py")


class TestResolveWorkspacePath:
    """Tests for workspace path resolution with boundary enforcement."""

    def test_resolve_simple_file(self, tmp_path):
        """Simple file path should resolve within workspace."""
        result = WorkspaceSecurity.resolve_workspace_path(tmp_path, "file.txt")
        assert result == tmp_path / "file.txt"
        assert result.is_relative_to(tmp_path)

    def test_resolve_nested_file(self, tmp_path):
        """Nested file path should resolve within workspace."""
        result = WorkspaceSecurity.resolve_workspace_path(
            tmp_path, "src/app/main.py"
        )
        expected = tmp_path / "src" / "app" / "main.py"
        assert result == expected
        assert result.is_relative_to(tmp_path)

    def test_reject_traversal_attempt(self, tmp_path):
        """Path traversal should be blocked even after normalization."""
        with pytest.raises(WorkspaceSecurityError, match="Path traversal detected"):
            WorkspaceSecurity.resolve_workspace_path(tmp_path, "../../../etc/passwd")

    def test_reject_subtle_escape(self, tmp_path):
        """Subtle workspace escape attempts should be blocked."""
        with pytest.raises(WorkspaceSecurityError, match="Path traversal detected"):
            WorkspaceSecurity.resolve_workspace_path(
                tmp_path, "valid/../../../../../../etc/passwd"
            )

    def test_symlink_cannot_escape(self, tmp_path):
        """Symlinks pointing outside workspace should be detected."""
        # Create a symlink in workspace pointing outside
        link_path = tmp_path / "escape_link"
        target_path = tmp_path.parent / "outside.txt"
        target_path.write_text("outside workspace")
        
        link_path.symlink_to(target_path)

        # Attempting to resolve the symlink should fail boundary check
        with pytest.raises(WorkspaceSecurityError, match="escapes workspace boundary"):
            WorkspaceSecurity.resolve_workspace_path(tmp_path, "escape_link")

    def test_must_exist_raises_when_missing(self, tmp_path):
        """must_exist=True should raise FileNotFoundError for missing paths."""
        with pytest.raises(FileNotFoundError, match="does not exist"):
            WorkspaceSecurity.resolve_workspace_path(
                tmp_path, "nonexistent.txt", must_exist=True
            )

    def test_must_exist_passes_when_present(self, tmp_path):
        """must_exist=True should pass when file exists."""
        test_file = tmp_path / "exists.txt"
        test_file.write_text("content")

        result = WorkspaceSecurity.resolve_workspace_path(
            tmp_path, "exists.txt", must_exist=True
        )
        assert result == test_file


class TestValidateWorkspaceRoot:
    """Tests for workspace root validation."""

    def test_valid_workspace_root(self, tmp_path):
        """Valid workspace root should pass."""
        # tmp_path is safe and absolute
        WorkspaceSecurity.validate_workspace_root(tmp_path)

    def test_reject_relative_root(self):
        """Relative paths should be rejected as workspace roots."""
        with pytest.raises(WorkspaceSecurityError, match="must be absolute"):
            WorkspaceSecurity.validate_workspace_root(Path("relative/path"))

    def test_reject_system_root(self):
        """System root directory should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="system directory"):
            WorkspaceSecurity.validate_workspace_root(Path("/"))

    def test_reject_etc_directory(self):
        """System /etc directory should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="system directory"):
            WorkspaceSecurity.validate_workspace_root(Path("/etc"))

    def test_reject_usr_directory(self):
        """System /usr directory should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="system directory"):
            WorkspaceSecurity.validate_workspace_root(Path("/usr"))

    def test_reject_subdirectory_of_system(self):
        """Subdirectories of system paths should be rejected."""
        with pytest.raises(WorkspaceSecurityError, match="system directory"):
            WorkspaceSecurity.validate_workspace_root(Path("/etc/nginx"))


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

    def test_remove_windows_separators(self):
        """Windows directory separators should be replaced."""
        result = WorkspaceSecurity.sanitize_filename("path\\to\\file.txt")
        assert "\\" not in result
        assert result == "path_to_file.txt"

    def test_remove_null_bytes(self):
        """Null bytes should be removed."""
        result = WorkspaceSecurity.sanitize_filename("file\x00name.txt")
        assert "\x00" not in result
        assert result == "filename.txt"

    def test_strip_leading_dots(self):
        """Leading dots should be stripped."""
        result = WorkspaceSecurity.sanitize_filename("...file.txt")
        assert result == "file.txt"

    def test_strip_trailing_spaces(self):
        """Trailing spaces should be stripped."""
        result = WorkspaceSecurity.sanitize_filename("file.txt   ")
        assert result == "file.txt"

    def test_reject_empty_after_sanitization(self):
        """Filename that becomes empty should raise error."""
        with pytest.raises(WorkspaceSecurityError, match="empty after sanitization"):
            WorkspaceSecurity.sanitize_filename("///")

    def test_truncate_long_filename(self):
        """Long filenames should be truncated."""
        long_name = "a" * 300 + ".txt"
        result = WorkspaceSecurity.sanitize_filename(long_name, max_length=255)
        assert len(result) <= 255
        assert result.endswith(".txt")  # Extension preserved

    def test_truncate_without_extension(self):
        """Long filename without extension should be truncated."""
        long_name = "a" * 300
        result = WorkspaceSecurity.sanitize_filename(long_name, max_length=255)
        assert len(result) <= 255
