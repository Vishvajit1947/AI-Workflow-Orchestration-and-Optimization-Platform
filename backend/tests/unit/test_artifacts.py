"""Unit tests for artifact schemas and path validation (no database, no LLM)."""
import pytest
from pydantic import ValidationError

from backend.app.artifacts import (
    Artifact, ArtifactFile, UnsafePathError, is_safe_artifact_path, normalize_artifact_path,
    try_parse_artifact,
)
from backend.app.artifacts.schemas import MAX_FILE_BYTES, MAX_TOTAL_BYTES


class TestPathValidation:
    @pytest.mark.parametrize("path, expected", [
        ("main.py", "main.py"),
        ("src/main.py", "src/main.py"),
        ("backend/app/routes/users.py", "backend/app/routes/users.py"),
        ("./src/main.py", "src/main.py"),
        ("src//main.py", "src/main.py"),
        ("src\\utils\\helpers.py", "src/utils/helpers.py"),
        (".gitignore", ".gitignore"),
        ("..hidden", "..hidden"),
        ("my file.txt", "my file.txt"),
        ("src/ünïcode.py", "src/ünïcode.py"),
    ])
    def test_accepts_and_normalizes_relative_paths(self, path, expected):
        assert normalize_artifact_path(path) == expected
        assert is_safe_artifact_path(path)

    @pytest.mark.parametrize("path", [
        "../main.py",
        "../../main.py",
        "src/../../etc/passwd",
        "src/..",
        "..\\..\\windows\\system32",
        "src\\..\\..\\x.py",
    ])
    def test_rejects_traversal(self, path):
        with pytest.raises(UnsafePathError):
            normalize_artifact_path(path)

    @pytest.mark.parametrize("path", [
        "/etc/passwd",
        "/main.py",
        "\\main.py",
        "C:\\Users\\me\\file.py",
        "C:/Users/me/file.py",
        "c:file.py",
        "\\\\server\\share\\file.py",
        "//server/share/file.py",
        "\\\\?\\C:\\file.py",
    ])
    def test_rejects_absolute_drive_and_unc_paths(self, path):
        with pytest.raises(UnsafePathError):
            normalize_artifact_path(path)

    @pytest.mark.parametrize("path", [
        "main\x00.py",
        "src/main.py\x00.txt",
        "src/\nmain.py",
        "src/\tmain.py",
        "main\x7f.py",
    ])
    def test_rejects_null_bytes_and_control_characters(self, path):
        with pytest.raises(UnsafePathError):
            normalize_artifact_path(path)

    @pytest.mark.parametrize("path", [
        "", "   ", ".", "./", "src/", "src/./",
        "file:stream.py", "a<b.py", "what?.py", "star*.py", 'q"uote.py', "pipe|.py",
        "CON", "nul.txt", "src/com1.py", "LPT9.md",
        "trailing.", "src/dir./x.py", " lead.py", "trail.py ",
        "a/" * 20 + "x.py",
        "x" * 101,
        "a/" + "b" * 300,
    ])
    def test_rejects_empty_directory_unportable_and_oversized_paths(self, path):
        with pytest.raises(UnsafePathError):
            normalize_artifact_path(path)
        assert not is_safe_artifact_path(path)

    def test_rejects_non_string(self):
        with pytest.raises(UnsafePathError):
            normalize_artifact_path(None)  # type: ignore[arg-type]
        assert not is_safe_artifact_path(123)  # type: ignore[arg-type]


class TestArtifactFile:
    def test_path_is_normalized_and_language_lowercased(self):
        f = ArtifactFile(path=".\\src\\main.py", content="print(1)", language=" Python ")
        assert f.path == "src/main.py"
        assert f.language == "python"

    def test_language_defaults_to_text(self):
        assert ArtifactFile(path="notes", content="").language == "text"
        assert ArtifactFile(path="notes", content="", language=None).language == "text"
        assert ArtifactFile(path="notes", content="", language="  ").language == "text"

    @pytest.mark.parametrize("language", ["c++", "c#", "objective-c", "tsx", "yaml"])
    def test_accepts_common_language_tags(self, language):
        assert ArtifactFile(path="f", content="", language=language).language == language

    @pytest.mark.parametrize("language", ["py thon", "<script>", "x" * 41, 42])
    def test_rejects_invalid_language_tags(self, language):
        with pytest.raises(ValidationError):
            ArtifactFile(path="f", content="", language=language)

    def test_rejects_unsafe_path(self):
        with pytest.raises(ValidationError, match="traversal"):
            ArtifactFile(path="../../main.py", content="x")

    def test_rejects_oversized_content(self):
        with pytest.raises(ValidationError, match="exceeds"):
            ArtifactFile(path="big.txt", content="x" * (MAX_FILE_BYTES + 1))

    def test_rejects_unknown_fields(self):
        with pytest.raises(ValidationError):
            ArtifactFile(path="a.py", content="", executable=True)


class TestArtifact:
    def test_explanation_artifact_needs_no_files(self):
        a = Artifact(artifact_type="explanation", name="Binary Trees")
        assert a.files == [] and a.conflicts == []

    def test_single_code_file(self):
        a = Artifact.model_validate({
            "artifact_type": "code",
            "name": "binary_search.py",
            "files": [{"path": "binary_search.py", "content": "def search(): ...", "language": "python"}],
        })
        assert a.files[0].path == "binary_search.py"
        assert a.files[0].language == "python"

    @pytest.mark.parametrize("count", [0, 2])
    def test_code_artifact_requires_exactly_one_file(self, count):
        files = [{"path": f"f{i}.py", "content": ""} for i in range(count)]
        with pytest.raises(ValidationError, match="exactly 1 file"):
            Artifact(artifact_type="code", name="x", files=files)

    def test_multi_file_project_with_nested_folders(self):
        a = Artifact.model_validate({
            "artifact_type": "project",
            "name": "fastapi-crud",
            "files": [
                {"path": "backend/main.py", "content": "app = 1", "language": "python"},
                {"path": "backend/models.py", "content": "", "language": "python"},
                {"path": "backend/routes/users.py", "content": "", "language": "python"},
                {"path": "requirements.txt", "content": "fastapi", "language": "text"},
                {"path": "README.md", "content": "# CRUD", "language": "markdown"},
            ],
        })
        assert [f.path for f in a.files] == [
            "backend/main.py", "backend/models.py", "backend/routes/users.py", "requirements.txt", "README.md",
        ]

    def test_project_requires_files(self):
        with pytest.raises(ValidationError, match="at least 1 file"):
            Artifact(artifact_type="project", name="empty")

    @pytest.mark.parametrize("paths", [
        ["src/main.py", "src/main.py"],
        ["src/main.py", "./src/main.py"],
        ["src/main.py", "src\\main.py"],
        ["README.md", "readme.md"],
    ])
    def test_rejects_duplicate_paths(self, paths):
        files = [{"path": p, "content": ""} for p in paths]
        with pytest.raises(ValidationError, match="Duplicate file path"):
            Artifact(artifact_type="project", name="dup", files=files)

    def test_rejects_path_used_as_file_and_directory(self):
        files = [{"path": "src", "content": ""}, {"path": "src/main.py", "content": ""}]
        with pytest.raises(ValidationError, match="both a file and a directory"):
            Artifact(artifact_type="project", name="clash", files=files)

    def test_rejects_traversal_inside_project(self):
        files = [{"path": "ok.py", "content": ""}, {"path": "../../evil.py", "content": ""}]
        with pytest.raises(ValidationError):
            Artifact(artifact_type="project", name="p", files=files)

    def test_rejects_total_size_over_limit(self):
        chunk = "x" * MAX_FILE_BYTES
        files = [{"path": f"f{i}.txt", "content": chunk} for i in range(MAX_TOTAL_BYTES // MAX_FILE_BYTES + 1)]
        with pytest.raises(ValidationError, match="Artifact content exceeds"):
            Artifact(artifact_type="project", name="huge", files=files)

    @pytest.mark.parametrize("name", ["", "   ", "bad\x00name", "line\nbreak"])
    def test_rejects_bad_names(self, name):
        with pytest.raises(ValidationError):
            Artifact(artifact_type="explanation", name=name)

    def test_conflicts_are_recorded_with_safe_paths(self):
        a = Artifact.model_validate({
            "artifact_type": "project",
            "name": "p",
            "files": [{"path": "README.md", "content": "v2"}],
            "conflicts": [{"path": "./README.md", "kept_from": "Documentation", "overridden_from": "Implementation"}],
        })
        assert a.conflicts[0].path == "README.md"
        with pytest.raises(ValidationError):
            Artifact.model_validate({
                "artifact_type": "project", "name": "p",
                "files": [{"path": "a.py", "content": ""}],
                "conflicts": [{"path": "../a.py", "kept_from": "x", "overridden_from": "y"}],
            })


class TestTryParseArtifact:
    def test_valid_data_parses(self):
        a = try_parse_artifact({"artifact_type": "document", "name": "Report"})
        assert isinstance(a, Artifact)

    @pytest.mark.parametrize("data", [
        None,
        "not a dict",
        42,
        [],
        {},
        {"artifact_type": "binary", "name": "x"},
        {"artifact_type": "project", "name": "x", "files": "src/main.py"},
        {"artifact_type": "project", "name": "x", "files": [{"path": "/etc/passwd", "content": ""}]},
        {"artifact_type": "project", "name": "x", "files": [{"path": "a.py"}]},
        {"artifact_type": "code", "name": "x", "files": [{"path": "a.py", "content": ""}], "run": True},
    ])
    def test_malformed_data_falls_back_to_none(self, data):
        assert try_parse_artifact(data) is None
