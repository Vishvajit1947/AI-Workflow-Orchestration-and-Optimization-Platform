"""
Lenient file extraction for the Project Builder.

Artifact mode is deliberately all-or-nothing (one bad fence rejects the whole artifact).
A project build instead wants every usable file, because the repair loop can recreate
what is missing. Real model output differs from the requested format in two common ways,
both handled here:

  - the answer is cut off by the output limit: complete files are kept, the unfinished
    last file is dropped with a warning;
  - files are labelled by a heading/line just before a plain fence (`## backend/main.py`,
    `**src/App.tsx**`, `File: requirements.txt`) instead of `path=` in the fence.

Every path still goes through the artifact path rules; unsafe or duplicate paths are
dropped with a warning, never written.
"""
import re
from typing import Optional

from backend.app.artifacts.limits import MAX_FILE_BYTES, MAX_FILES
from backend.app.artifacts.validators import UnsafePathError, normalize_artifact_path

_FENCE_OPEN = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_INFO_PATH = re.compile(r"""(?:^|\s)path=(?:"([^"]+)"|'([^']+)'|(\S+))""")
# A file-like token: folders/name.ext, or a well-known extension-less file name
_PATH_TOKEN = re.compile(
    r"(?<![\w/.-])((?:[\w@.-]+/)*(?:[\w@-][\w@.-]*\.[A-Za-z0-9]{1,8}|Dockerfile|Makefile|Procfile|\.gitignore|\.env\.example))(?![\w/])"
)
_LABEL_LOOKBACK = 3  # non-empty lines above a fence that may carry its file name


def _info_path(info: str) -> Optional[str]:
    """Path from the fence info string: `path=src/a.py`, or a bare path word (```python src/a.py)."""
    explicit = _INFO_PATH.search(info)
    if explicit:
        return next(g for g in explicit.groups() if g)
    words = info.split()
    candidates = words[1:] if len(words) > 1 else words
    for word in candidates:
        if ("/" in word or "." in word) and _PATH_TOKEN.fullmatch(word):
            return word
    return None


def _label_path(lines: list[str], fence_index: int) -> Optional[str]:
    """A file name written just above the fence (heading, bold, backticks or 'File:' line)."""
    seen = 0
    for k in range(fence_index - 1, -1, -1):
        line = lines[k].strip()
        if not line:
            continue
        if line in ("---", "***") or _FENCE_OPEN.match(lines[k]):
            break
        seen += 1
        if seen > _LABEL_LOOKBACK:
            break
        # Only short label-like lines, not prose that happens to mention a file
        if len(line) > 160:
            continue
        candidates = _PATH_TOKEN.findall(line.replace("**", " ").replace("`", " "))
        if candidates:
            return candidates[-1]
    return None


def extract_project_files(text: Optional[str]) -> tuple[list[dict], list[str]]:
    """([{"path", "content"}], warnings) from one stage's output, in document order."""
    if not text:
        return [], []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    files: dict[str, dict] = {}
    warnings: list[str] = []
    i = 0
    while i < len(lines):
        opening = _FENCE_OPEN.match(lines[i])
        if not opening or (opening["fence"][0] == "`" and "`" in opening["info"]):
            i += 1
            continue
        fence = opening["fence"]
        closing = re.compile(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*$")
        j = i + 1
        while j < len(lines) and not closing.match(lines[j]):
            j += 1
        path = _info_path(opening["info"]) or _label_path(lines, i)
        body = "\n".join(lines[i + 1:j])
        content = body + "\n" if body else ""
        i = j + 1
        if path is None:
            continue  # an ordinary code example, not a file
        if j >= len(lines):
            warnings.append(f"{path}: the output was cut off before this file ended, so it was left out")
            continue
        try:
            path = normalize_artifact_path(path)
        except UnsafePathError as e:
            warnings.append(f"{path}: unsafe path ignored ({e})")
            continue
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            warnings.append(f"{path}: larger than {MAX_FILE_BYTES} bytes, left out")
            continue
        if path.lower() in files:
            warnings.append(f"{path}: written twice in one stage; the later version is used")
        files[path.lower()] = {"path": path, "content": content}
    out = list(files.values())
    if len(out) > MAX_FILES:
        warnings.append(f"Only the first {MAX_FILES} files were kept")
        out = out[:MAX_FILES]
    return out, warnings


def merge_stage_files(stages: list[tuple[str, list[dict]]]) -> tuple[list[dict], list[str]]:
    """Combine stages' files in order; a later stage replaces an earlier stage's file at the same path."""
    merged: dict[str, dict] = {}
    owner: dict[str, str] = {}
    warnings: list[str] = []
    for label, files in stages:
        for f in files:
            key = f["path"].lower()
            if key in merged and merged[key]["content"] != f["content"]:
                warnings.append(f"{f['path']}: written by both {owner[key]} and {label}; {label}'s version is used")
            merged[key], owner[key] = f, label
    return list(merged.values()), warnings
