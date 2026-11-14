"""
In-memory ZIP export of a validated artifact.

Files go under one root folder named after the artifact, keeping their relative paths.
Every path is validated again here, so a ZIP can never contain absolute or traversal
entries even if an Artifact were built without the schema. Nothing touches the disk.
"""
import io
import re
import zipfile

from backend.app.artifacts.document import ExportError
from backend.app.artifacts.limits import MAX_FILES, MAX_TOTAL_BYTES
from backend.app.artifacts.schemas import Artifact
from backend.app.artifacts.validators import UnsafePathError, normalize_artifact_path

_FIXED_TIME = (2020, 1, 1, 0, 0, 0)  # stable timestamps: the same artifact gives the same bytes


def safe_filename(name: str, default: str = "artifact") -> str:
    """ASCII file/folder name for downloads: 'FastAPI CRUD!' → 'fastapi-crud'."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name or "").strip("-._").lower()[:80].strip("-._")
    return stem or default


def build_zip(artifact: Artifact) -> bytes:
    """ZIP bytes for an artifact with files. Raises ExportError if it cannot be packaged safely."""
    if not artifact.files:
        raise ExportError("This artifact has no files to download")
    if len(artifact.files) > MAX_FILES:
        raise ExportError(f"Too many files to package ({len(artifact.files)} > {MAX_FILES})")
    root = safe_filename(artifact.name, "project")
    seen: set[str] = set()
    total = 0
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for f in artifact.files:
            try:
                path = normalize_artifact_path(f.path)
            except UnsafePathError as e:
                raise ExportError(f"Unsafe file path '{f.path}': {e}") from e
            if path.lower() in seen:
                raise ExportError(f"Duplicate file path '{path}'")
            seen.add(path.lower())
            data = f.content.encode("utf-8")
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                raise ExportError(f"Artifact content exceeds {MAX_TOTAL_BYTES} bytes")
            info = zipfile.ZipInfo(f"{root}/{path}", date_time=_FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16  # regular, non-executable file
            archive.writestr(info, data)
    return buffer.getvalue()
