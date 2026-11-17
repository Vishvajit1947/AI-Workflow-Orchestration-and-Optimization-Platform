"""
Standalone validation script for workspace security.
Run directly to verify security functions work correctly.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.workspace.security import WorkspaceSecurity
from app.services.workspace.exceptions import WorkspaceSecurityError


def test_validate_relative_path():
    """Test relative path validation."""
    print("\n=== Testing validate_relative_path ===")
    
    # Valid paths
    tests = [
        ("file.txt", True, "Simple filename"),
        ("src/app/main.py", True, "Nested path"),
        ("config.dev.json", True, "Dots in filename"),
        ("./src/./app.py", True, "Current directory refs"),
        
        # Invalid paths
        ("", False, "Empty path"),
        ("/etc/passwd", False, "Absolute path"),
        ("../../../etc/passwd", False, "Path traversal"),
        ("file\x00.txt", False, "Null byte"),
        ("file\nname.txt", False, "Newline"),
    ]
    
    passed = 0
    failed = 0
    
    for path, should_pass, description in tests:
        try:
            result = WorkspaceSecurity.validate_relative_path(path)
            if should_pass:
                print(f"✓ PASS: {description} - '{path}' → '{result}'")
                passed += 1
            else:
                print(f"✗ FAIL: {description} - '{path}' should have been rejected")
                failed += 1
        except WorkspaceSecurityError as e:
            if not should_pass:
                print(f"✓ PASS: {description} - '{path}' rejected: {e}")
                passed += 1
            else:
                print(f"✗ FAIL: {description} - '{path}' was incorrectly rejected: {e}")
                failed += 1
        except Exception as e:
            print(f"✗ FAIL: {description} - Unexpected error: {e}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_resolve_workspace_path():
    """Test workspace path resolution."""
    print("\n=== Testing resolve_workspace_path ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        # Create a test file
        test_file = workspace / "test.txt"
        test_file.write_text("content")
        
        # Create an outside file and symlink
        outside_file = workspace.parent / "outside.txt"
        outside_file.write_text("outside")
        
        link_path = workspace / "escape_link"
        try:
            link_path.symlink_to(outside_file)
        except (OSError, NotImplementedError):
            print("⚠ Symlink test skipped (not supported on this system)")
            link_path = None
        
        tests = [
            ("test.txt", True, False, "Simple file"),
            ("nested/file.py", True, False, "Nested path"),
            ("../../../etc/passwd", False, False, "Path traversal"),
            ("test.txt", True, True, "Existing file with must_exist"),
            ("nonexistent.txt", False, True, "Missing file with must_exist"),
        ]
        
        if link_path:
            tests.append(("escape_link", False, False, "Symlink escaping workspace"))
        
        passed = 0
        failed = 0
        
        for path, should_pass, must_exist, description in tests:
            try:
                result = WorkspaceSecurity.resolve_workspace_path(workspace, path, must_exist=must_exist)
                if should_pass:
                    print(f"✓ PASS: {description} - '{path}' → '{result}'")
                    passed += 1
                else:
                    print(f"✗ FAIL: {description} - '{path}' should have been rejected")
                    failed += 1
            except (WorkspaceSecurityError, FileNotFoundError) as e:
                if not should_pass:
                    print(f"✓ PASS: {description} - '{path}' rejected: {e}")
                    passed += 1
                else:
                    print(f"✗ FAIL: {description} - '{path}' was incorrectly rejected: {e}")
                    failed += 1
            except Exception as e:
                print(f"✗ FAIL: {description} - Unexpected error: {e}")
                failed += 1
        
        print(f"\nResults: {passed} passed, {failed} failed")
        return failed == 0


def test_sanitize_filename():
    """Test filename sanitization."""
    print("\n=== Testing sanitize_filename ===")
    
    tests = [
        ("document.txt", "document.txt", True, "Valid filename"),
        ("path/to/file.txt", "path_to_file.txt", True, "Directory separators"),
        ("path\\to\\file.txt", "path_to_file.txt", True, "Windows separators"),
        ("file\x00name.txt", "filename.txt", True, "Null byte"),
        ("...file.txt", "file.txt", True, "Leading dots"),
        ("file.txt   ", "file.txt", True, "Trailing spaces"),
        ("///", None, False, "Empty after sanitization"),
    ]
    
    passed = 0
    failed = 0
    
    for input_name, expected, should_pass, description in tests:
        try:
            result = WorkspaceSecurity.sanitize_filename(input_name)
            if should_pass:
                if result == expected:
                    print(f"✓ PASS: {description} - '{input_name}' → '{result}'")
                    passed += 1
                else:
                    print(f"✗ FAIL: {description} - Expected '{expected}', got '{result}'")
                    failed += 1
            else:
                print(f"✗ FAIL: {description} - '{input_name}' should have been rejected")
                failed += 1
        except WorkspaceSecurityError as e:
            if not should_pass:
                print(f"✓ PASS: {description} - '{input_name}' rejected: {e}")
                passed += 1
            else:
                print(f"✗ FAIL: {description} - '{input_name}' was incorrectly rejected: {e}")
                failed += 1
        except Exception as e:
            print(f"✗ FAIL: {description} - Unexpected error: {e}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all security tests."""
    print("=" * 60)
    print("WORKSPACE SECURITY VALIDATION")
    print("=" * 60)
    
    all_passed = True
    
    all_passed &= test_validate_relative_path()
    all_passed &= test_resolve_workspace_path()
    all_passed &= test_sanitize_filename()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
