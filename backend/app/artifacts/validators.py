"""
Path safety for artifact files.

Artifact paths come from LLM output, so every path is treated as untrusted. A path is
accepted only if it is a plain relative path that cannot escape the artifact root when
written to disk or extracted from a ZIP on any OS. Nothing here touches the filesystem.
"""
import re

from backend.app.artifacts.limits import MAX_PATH_DEPTH, MAX_PATH_LENGTH, MAX_SEGMENT_LENGTH

# Device names Windows refuses as file names, with or without an extension (e.g. "nul.txt")
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
# Characters Windows forbids in file names (":" also covers drive letters and NTFS streams)
_WINDOWS_FORBIDDEN = re.compile(r'[<>:"|?*]')


class UnsafePathError(ValueError):
    """An artifact path that could escape the artifact root or is not portable."""


def normalize_artifact_path(path: str) -> str:
    """
    Validate an artifact file path and return it in canonical form ("src/main.py").

    Backslashes are treated as separators and "." / empty segments are dropped.
    Raises UnsafePathError for absolute, drive, UNC or traversal paths, control
    characters (including null bytes), Windows-forbidden names, or oversized paths.
    """
    if not isinstance(path, str):
        raise UnsafePathError("Path must be a string")
    if not path or not path.strip():
        raise UnsafePathError("Path is empty")
    if _CONTROL_CHARS.search(path):
        raise UnsafePathError("Path contains control characters")
    if len(path) > MAX_PATH_LENGTH:
        raise UnsafePathError(f"Path is longer than {MAX_PATH_LENGTH} characters")

    unified = path.replace("\\", "/")
    if unified.startswith("/"):
        raise UnsafePathError("Absolute and UNC paths are not allowed")
    if _WINDOWS_FORBIDDEN.search(unified):
        raise UnsafePathError('Path contains a character not allowed in file names (<>:"|?*)')
    if unified.endswith("/"):
        raise UnsafePathError("Path must name a file, not a directory")

    segments = [s for s in unified.split("/") if s not in ("", ".")]
    if not segments:
        raise UnsafePathError("Path has no file name")
    if len(segments) > MAX_PATH_DEPTH:
        raise UnsafePathError(f"Path is nested deeper than {MAX_PATH_DEPTH} levels")

    for segment in segments:
        if segment == "..":
            raise UnsafePathError("Path traversal ('..') is not allowed")
        if len(segment) > MAX_SEGMENT_LENGTH:
            raise UnsafePathError(f"Path segment is longer than {MAX_SEGMENT_LENGTH} characters")
        if segment != segment.strip() or segment.endswith("."):
            # Windows silently trims these, so "a." and "a" would collide on extraction
            raise UnsafePathError(f"Path segment '{segment}' has leading/trailing spaces or a trailing dot")
        if segment.split(".", 1)[0].lower() in _WINDOWS_RESERVED:
            raise UnsafePathError(f"'{segment}' is a reserved device name on Windows")

    return "/".join(segments)


def is_safe_artifact_path(path: str) -> bool:
    """True if normalize_artifact_path would accept the path."""
    try:
        normalize_artifact_path(path)
        return True
    except UnsafePathError:
        return False
