"""
Pydantic schemas for output artifacts.

An artifact is a presentation of an existing stage result (a single code file, a
multi-file project, a document, ...). It never replaces the stage's text output: if an
artifact cannot be built or fails validation, callers use try_parse_artifact and fall
back to the plain result.
"""
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from backend.app.artifacts.limits import MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES
from backend.app.artifacts.validators import UnsafePathError, normalize_artifact_path

# Optional per-stage hint; stages without one keep the existing text-only behaviour
OutputMode = Literal["explanation", "code", "project", "document", "structured"]
ArtifactType = OutputMode

_LANGUAGE = re.compile(r"^[a-z0-9][a-z0-9+#._-]{0,39}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class ArtifactFile(BaseModel):
    """One file inside an artifact. `path` is stored in canonical relative form."""
    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Relative path inside the artifact, e.g. 'src/main.py'")
    content: str = Field(..., description="File contents")
    language: str = Field(default="text", description="Language tag, e.g. 'python', 'markdown'")

    @field_validator("path")
    @classmethod
    def _safe_path(cls, value: str) -> str:
        try:
            return normalize_artifact_path(value)
        except UnsafePathError as e:
            raise ValueError(str(e)) from e

    @field_validator("content")
    @classmethod
    def _content_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"File content exceeds {MAX_FILE_BYTES} bytes")
        return value

    @field_validator("language", mode="before")
    @classmethod
    def _language_tag(cls, value: object) -> str:
        if value is None or (isinstance(value, str) and not value.strip()):
            return "text"
        if not isinstance(value, str):
            raise ValueError("Language must be a string")
        tag = value.strip().lower()
        if not _LANGUAGE.match(tag):
            raise ValueError(f"Invalid language tag: {value!r}")
        return tag


class ArtifactConflict(BaseModel):
    """Two sources produced the same path; `kept_from` won, `overridden_from` lost."""
    model_config = ConfigDict(extra="forbid")

    path: str
    kept_from: str = Field(..., description="Source (e.g. stage name) whose file is in the artifact")
    overridden_from: str = Field(..., description="Source whose file was replaced")

    @field_validator("path")
    @classmethod
    def _safe_path(cls, value: str) -> str:
        try:
            return normalize_artifact_path(value)
        except UnsafePathError as e:
            raise ValueError(str(e)) from e


class Artifact(BaseModel):
    """A validated, virtual set of files built from a stage or workflow result."""
    model_config = ConfigDict(extra="forbid")

    artifact_type: ArtifactType
    name: str = Field(..., min_length=1, max_length=255, description="Display name, e.g. 'fastapi-crud'")
    files: list[ArtifactFile] = Field(default_factory=list, max_length=MAX_FILES)
    conflicts: list[ArtifactConflict] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        if _CONTROL_CHARS.search(value) or not value.strip():
            raise ValueError("Name must be non-blank and contain no control characters")
        return value.strip()

    @model_validator(mode="after")
    def _check_files(self) -> "Artifact":
        # Case-insensitive: "README.md" and "readme.md" overwrite each other on Windows/macOS
        seen: dict[str, str] = {}
        for f in self.files:
            key = f.path.lower()
            if key in seen:
                raise ValueError(f"Duplicate file path: '{f.path}' (conflicts with '{seen[key]}')")
            seen[key] = f.path
        # A path cannot be both a file and a directory ("src" and "src/main.py")
        for path in seen:
            parts = path.split("/")
            for i in range(1, len(parts)):
                prefix = "/".join(parts[:i])
                if prefix in seen:
                    raise ValueError(f"'{seen[prefix]}' is used as both a file and a directory")

        total = sum(len(f.content.encode("utf-8")) for f in self.files)
        if total > MAX_TOTAL_BYTES:
            raise ValueError(f"Artifact content exceeds {MAX_TOTAL_BYTES} bytes")

        if self.artifact_type == "code" and len(self.files) != 1:
            raise ValueError(f"A code artifact must contain exactly 1 file, got {len(self.files)}")
        if self.artifact_type == "project" and not self.files:
            raise ValueError("A project artifact must contain at least 1 file")
        return self


def try_parse_artifact(data: object) -> Optional[Artifact]:
    """Validate untrusted artifact data; None (meaning: use the plain text output) if invalid."""
    if data is None:
        return None
    try:
        return Artifact.model_validate(data)
    except (ValidationError, TypeError, ValueError):
        return None
