"""
Artifact service: builds artifacts from existing stage results.

Pure functions over text: no database, filesystem or LLM access. Inputs are never
modified, so the stored ExecutionRecord.result (and cached results) stay exactly as the
model produced them; artifacts are only a presentation of that text. Public functions
return None instead of raising, so an artifact problem can never fail a workflow.

File convention (stage prompts will document it in a later phase): a file is a fenced
code block whose info string carries a `path=` attribute.

    ```python path=src/main.py
    print("hello")
    ```

Fences without `path=` are ordinary code examples and are ignored. A file whose content
itself contains ``` fences must use a longer fence (````) or a ~~~ fence, as in CommonMark.
Validation is all-or-nothing: one bad file rejects the whole artifact.
"""
import re
from dataclasses import dataclass
from typing import Optional, get_args

from backend.app.artifacts.schemas import Artifact, OutputMode

_TEXT_MODES = {"explanation", "document"}
_SINGLE_FILE_MODES = {"code", "structured"}

# CommonMark fenced code block: up to 3 spaces, then 3+ backticks or tildes, then the info string
_FENCE_OPEN = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
# key=value (double-quoted, single-quoted or bare) or a plain word
_INFO_TOKEN = re.compile(
    r"""(?P<key>[A-Za-z][\w-]*)=(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>[^\s"']\S*))|(?P<word>\S+)"""
)

_EXTENSION_LANGUAGES = {
    "py": "python", "js": "javascript", "mjs": "javascript", "cjs": "javascript", "jsx": "jsx",
    "ts": "typescript", "tsx": "tsx", "cpp": "cpp", "cc": "cpp", "cxx": "cpp", "hpp": "cpp", "h": "c",
    "c": "c", "java": "java", "sql": "sql", "json": "json", "yaml": "yaml", "yml": "yaml",
    "md": "markdown", "txt": "text", "html": "html", "css": "css", "sh": "bash", "toml": "toml",
    "ini": "ini", "xml": "xml", "go": "go", "rs": "rust", "rb": "ruby", "csv": "csv",
}


class ArtifactParseError(ValueError):
    """The result declares files (path= fences) but they cannot be read reliably."""


@dataclass(frozen=True)
class ParsedFile:
    """A file fence as written in the output; the path is validated later by the schema."""
    path: str
    language: Optional[str]
    content: str


def _parse_info(info: str) -> tuple[Optional[str], Optional[str]]:
    """(language, path) from a fence info string; path is None for ordinary code blocks."""
    language: Optional[str] = None
    path: Optional[str] = None
    for index, token in enumerate(_INFO_TOKEN.finditer(info.strip())):
        if token["key"] is not None:
            if token["key"] != "path":
                continue
            if path is not None:
                raise ArtifactParseError("File fence has more than one path= attribute")
            value = next(v for v in (token["dq"], token["sq"], token["bare"]) if v is not None)
            if not value.strip():
                raise ArtifactParseError("File fence has an empty path= attribute")
            path = value
        elif token["word"].startswith("path="):
            raise ArtifactParseError(f"File fence has a malformed path attribute: {token['word']!r}")
        elif index == 0:
            language = token["word"]
    return language, path


def _strip_indent(line: str, indent: int) -> str:
    """Remove up to `indent` leading spaces, as CommonMark does for indented fences."""
    removable = len(line) - len(line.lstrip(" "))
    return line[min(indent, removable):]


def parse_file_fences(text: str) -> list[ParsedFile]:
    """
    Every `path=` fence in a Markdown result, in order.

    Raises ArtifactParseError if a file fence is malformed or never closed (typically a
    response cut off by the token limit), so a partial file is never presented as complete.
    """
    return _scan_fences(text)[0]


def _scan_fences(text: str) -> tuple[list[ParsedFile], list[tuple[Optional[str], str, bool]]]:
    """(path= files, other fences as (language, content, closed)), both in document order."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    files: list[ParsedFile] = []
    others: list[tuple[Optional[str], str, bool]] = []
    i = 0
    while i < len(lines):
        opening = _FENCE_OPEN.match(lines[i])
        if not opening:
            i += 1
            continue
        fence, info = opening["fence"], opening["info"]
        if fence[0] == "`" and "`" in info:
            i += 1  # not a fence in CommonMark (e.g. inline ```code```)
            continue
        closing = re.compile(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*$")
        body: list[str] = []
        j = i + 1
        while j < len(lines) and not closing.match(lines[j]):
            body.append(_strip_indent(lines[j], len(opening["indent"])))
            j += 1

        language, path = _parse_info(info)
        content = "\n".join(body) + "\n" if body else ""
        if path is not None:
            if j >= len(lines):
                raise ArtifactParseError(f"File fence for '{path}' is never closed (output may be truncated)")
            files.append(ParsedFile(path=path, language=language, content=content))
        else:
            others.append((language, content, j < len(lines)))
        i = j + 1
    return files, others


# Language tag → file extension, for a code block the model wrote without a path=
_LANGUAGE_EXTENSIONS = {
    "python": "py", "py": "py", "javascript": "js", "js": "js", "jsx": "jsx", "typescript": "ts", "ts": "ts",
    "tsx": "tsx", "cpp": "cpp", "c++": "cpp", "c": "c", "java": "java", "sql": "sql", "json": "json",
    "yaml": "yaml", "yml": "yaml", "markdown": "md", "md": "md", "html": "html", "css": "css",
    "bash": "sh", "sh": "sh", "shell": "sh", "go": "go", "rust": "rs", "rs": "rs", "ruby": "rb",
    "csharp": "cs", "c#": "cs", "cs": "cs", "kotlin": "kt", "php": "php", "toml": "toml", "xml": "xml",
    "csv": "csv",
}


def extension_for_language(language: Optional[str]) -> Optional[str]:
    """File extension for a language tag, None if unknown."""
    return _LANGUAGE_EXTENSIONS.get((language or "").strip().lower())


def _file_stem(name: str) -> str:
    """'Binary Search Implementation' → 'binary_search_implementation'."""
    stem = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60].strip("_")
    return stem or "main"


def _unlabeled_single_file(others: list[tuple[Optional[str], str, bool]], name: str) -> Optional[dict]:
    """
    Secondary fallback for code/structured stages whose model ignored the path= convention:
    exactly one closed code block in a known language becomes `<stage name>.<ext>`.
    Several blocks are ambiguous (they may be examples), so nothing is inferred.
    """
    if len(others) != 1:
        return None
    language, content, closed = others[0]
    extension = extension_for_language(language)
    if not closed or extension is None or not content.strip():
        return None
    return {"path": f"{_file_stem(name)}.{extension}", "content": content, "language": language}


def language_for_path(path: str) -> str:
    """Language tag from a file extension, 'text' if unknown."""
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    extension = name.rsplit(".", 1)[-1].lower() if "." in name.lstrip(".") else ""
    return _EXTENSION_LANGUAGES.get(extension, "text")


def _build_stage_artifact(result: Optional[str], output_mode: Optional[str], name: str) -> Optional[Artifact]:
    if output_mode not in get_args(OutputMode):
        return None  # no (or unknown) output mode: existing text-only behaviour
    if not result or not result.strip():
        return None
    name = name.strip() if name and name.strip() else "artifact"

    if output_mode in _TEXT_MODES:
        return Artifact(artifact_type=output_mode, name=name)

    parsed, others = _scan_fences(result)
    files = [
        {"path": f.path, "content": f.content, "language": f.language or language_for_path(f.path)}
        for f in parsed
    ]
    if not files and output_mode in _SINGLE_FILE_MODES:
        fallback = _unlabeled_single_file(others, name)
        files = [fallback] if fallback else []
    if not files:
        return None
    # A single-file mode that returned several files becomes a project, keeping every file
    single = output_mode in _SINGLE_FILE_MODES and len(files) == 1
    artifact = Artifact.model_validate({
        "artifact_type": output_mode if single else "project",
        "name": name,
        "files": files,
    })
    if single:
        artifact = artifact.model_copy(update={"name": artifact.files[0].path.rsplit("/", 1)[-1]})
    return artifact


def build_stage_artifact(result: Optional[str], output_mode: Optional[str], name: str) -> Optional[Artifact]:
    """
    The artifact for one stage result, or None to use the plain text output.

    - no/unknown output_mode → None (existing behaviour, nothing inferred)
    - explanation / document → a file-less artifact of that type (for PDF/TXT export)
    - code / structured → that type for one file, a project for several
    - project → a project
    Any parse or validation problem → None.
    """
    try:
        return _build_stage_artifact(result, output_mode, name)
    except Exception as e:
        print(f"[ARTIFACT WARN] Stage '{name}': artifact not built, using text output: {e}")
        return None


def record_artifact(record) -> Optional[Artifact]:
    """Artifact for a completed ExecutionRecord (stage loaded), using its stage's output_mode; never raises."""
    try:
        stage = record.stage
        if record.status != "completed" or stage is None:
            return None
        mode = (stage.config or {}).get("output_mode")
    except Exception as e:
        print(f"[ARTIFACT WARN] Could not read stage settings for record {getattr(record, 'id', '?')}: {e}")
        return None
    return build_stage_artifact(record.result, mode, stage.name)


def _aggregate_artifacts(sources: list[tuple[str, Optional[Artifact]]], name: str) -> Optional[Artifact]:
    contributing = [(label, a) for label, a in sources if a is not None and a.files]
    if len(contributing) < 2:
        return None  # a single file-producing stage already has its own artifact

    merged: dict[str, tuple[str, dict]] = {}  # lower-cased path -> (source label, file)
    conflicts: list[dict] = []
    for label, artifact in contributing:
        for f in artifact.files:
            key = f.path.lower()
            previous = merged.get(key)
            if previous is not None:
                previous_label, previous_file = previous
                if previous_file["path"] == f.path and previous_file["content"] == f.content:
                    continue  # identical file: nothing is overwritten
                conflicts.append({"path": f.path, "kept_from": label, "overridden_from": previous_label})
            merged[key] = (label, f.model_dump())

    return Artifact.model_validate({
        "artifact_type": "project",
        "name": name.strip() if name and name.strip() else "project",
        "files": [f for _, f in merged.values()],
        "conflicts": conflicts,
    })


def aggregate_artifacts(sources: list[tuple[str, Optional[Artifact]]], name: str) -> Optional[Artifact]:
    """
    One project combining the files of several stage artifacts, or None.

    `sources` is (label, artifact) in stage order. Built only when at least two stages
    produced files. When stages produce the same path the later stage wins and the
    override is recorded in `conflicts`; the earlier version stays in its stage's own
    artifact. If the merged project fails validation (e.g. a size limit, or one stage's
    file is another's folder) the result is None.
    """
    try:
        return _aggregate_artifacts(sources, name)
    except Exception as e:
        print(f"[ARTIFACT WARN] Workflow '{name}': combined artifact not built: {e}")
        return None
