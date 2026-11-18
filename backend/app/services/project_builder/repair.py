"""
LLM diagnosis and repair of a failed build step.

The model sees the failed step (label, command, exit code, the tail of its output), the
project's file list and the files most likely involved, and must answer with a short
diagnosis followed by complete replacement files in the same fenced `path=` format the
artifact parser already understands. Its answer is untrusted input:

  - paths are normalised with the artifact path rules (relative, no '..', no reserved
    names) and may not point into dependency or VCS folders;
  - at most MAX_FILES_PER_FIX files, each within the artifact size limits;
  - nothing is written here: the build service applies a validated Fix and records the
    previous contents.
"""
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from backend.app.services.project_builder.extraction import extract_project_files

MAX_FILES_PER_FIX = 5
# Sized for small free-tier rate limits: e.g. Groq's 8,000 tokens per minute counts the input
# plus the 4,096 tokens reserved for the answer, so the whole prompt must stay under ~3,500 tokens.
MAX_CONTEXT_CHARS = 8_000
MAX_LOG_CHARS = 2_500
_FORBIDDEN_PARTS = {"node_modules", ".git", "__pycache__", ".venv", "venv"}
_ALWAYS_RELEVANT = ("requirements.txt", "package.json", "pyproject.toml", "tsconfig.json",
                    "vite.config.ts", "vite.config.js", "main.py", "app.py")

SYSTEM_PROMPT = (
    "You are a senior engineer fixing a generated software project so that it installs, builds "
    "and passes its tests. You are given the failing step, its output and the relevant files.\n"
    "Answer in exactly this format:\n"
    "DIAGNOSIS: one short paragraph naming the root cause.\n"
    "Then every file you change, complete (never a diff, never '...'), as a fenced code block whose "
    "info string has the language and the path relative to the project root, e.g. ```python path=backend/main.py . "
    "If a file itself contains ``` fences, use a four-backtick fence.\n"
    f"Rules: change at most {MAX_FILES_PER_FIX} files; change only what the error requires; keep the "
    "project's intent; for a missing dependency add it (with a known-good version) to the dependency "
    "manifest instead of rewriting code; never add files under node_modules or .git; do not weaken or "
    "delete tests just to make them pass. If nothing in the project can fix the error, give only the DIAGNOSIS."
)


@dataclass
class Fix:
    diagnosis: str
    files: dict[str, str] = field(default_factory=dict)  # validated path -> new content
    rejected: list[str] = field(default_factory=list)  # why proposed changes were refused
    model: Optional[str] = None


LLMCall = Callable[[str, str], Awaitable[tuple[str, Optional[str]]]]  # (prompt, system) -> (text, model)


def _relevant_files(files: dict[str, str], output: str, cwd: str) -> list[str]:
    """Files named in the error output first, then manifests/entry points, then the rest of the component."""
    mentioned = [p for p in files if p in output or p.rsplit("/", 1)[-1] in output]
    component = [p for p in files if not cwd or p.startswith(cwd + "/")]
    essential = [p for p in component if p.rsplit("/", 1)[-1] in _ALWAYS_RELEVANT]
    ordered: list[str] = []
    for p in mentioned + essential + sorted(component, key=len):
        if p not in ordered:
            ordered.append(p)
    return ordered


def build_prompt(files: dict[str, str], step: dict, previous_attempts: list[dict]) -> str:
    output = step.get("output") or ""
    log = output[-MAX_LOG_CHARS:]
    parts = [
        f"FAILED STEP: {step['label']} (component: {step.get('component') or '(root)'})",
        f"COMMAND: {step['command']}   (run in: /{step.get('cwd') or ''})",
        f"EXIT CODE: {step.get('exit_code')}{'  (timed out)' if step.get('timed_out') else ''}",
        f"OUTPUT (last {len(log)} characters):\n{log}",
        "PROJECT FILES:\n" + "\n".join(sorted(files)),
    ]
    if previous_attempts:
        parts.append("EARLIER FIX ATTEMPTS THAT DID NOT RESOLVE THE FAILURE:\n" + "\n".join(
            f"- attempt {a['attempt']}: {a.get('diagnosis', '')[:400]} (changed: "
            f"{', '.join(f['path'] for f in a.get('files', [])) or 'nothing'})" for a in previous_attempts))
    budget = MAX_CONTEXT_CHARS
    shown = []
    for path in _relevant_files(files, output, step.get("cwd") or ""):
        content = files[path]
        if len(content) > budget:
            continue
        budget -= len(content)
        fence = "````" if "```" in content else "```"
        shown.append(f"{fence}text path={path}\n{content}\n{fence}")
    parts.append("RELEVANT FILES:\n" + "\n\n".join(shown))
    return "\n\n".join(parts)


def parse_fix(text: str) -> Fix:
    """Diagnosis and validated file changes from the model's answer (never raises).

    Uses the same lenient extraction as project generation, so `path=` fences and files
    labelled by a heading are both accepted; anything unusable is reported in `rejected`.
    """
    # The diagnosis ends where the first file starts (a fence, heading or bold file label)
    match = re.search(r"DIAGNOSIS:\s*(.+?)(?:\n\s*(?:#{1,6}\s|\*\*|`{3,}|~{3,})|\Z)", text, re.S)
    diagnosis = (match.group(1) if match else text.split("```")[0]).strip()[:2000] or "No diagnosis given."
    fix = Fix(diagnosis=diagnosis)
    files, warnings = extract_project_files(text)
    fix.rejected.extend(warnings)
    for f in files:
        if any(part in _FORBIDDEN_PARTS for part in f["path"].split("/")):
            fix.rejected.append(f"{f['path']}: changes under dependency or VCS folders are not allowed")
            continue
        if len(fix.files) >= MAX_FILES_PER_FIX:
            fix.rejected.append(f"{f['path']}: more than {MAX_FILES_PER_FIX} files changed; ignored")
            continue
        fix.files[f["path"]] = f["content"]
    return fix


async def propose_fix(llm: LLMCall, files: dict[str, str], step: dict, previous_attempts: list[dict]) -> Fix:
    text, model = await llm(build_prompt(files, step, previous_attempts), SYSTEM_PROMPT)
    fix = parse_fix(text)
    fix.model = model
    return fix
