"""
Output-format instructions for stages that should produce files.

Only stages whose config has output_mode code / project / structured get the extra
instructions; every other stage keeps the original system prompt byte for byte.
"""
from typing import Optional

_FILE_FORMAT = (
    "\n\nOUTPUT FORMAT: Write each file as a fenced code block whose info string gives the "
    "language and the file's relative path, for example ```python path=src/main.py . "
    "Use relative paths with forward slashes (never absolute paths or '..'). Give each file once, "
    "complete, with no placeholders. If a file itself contains ``` fences (such as a README), "
    "wrap that file in a four-backtick fence: ````markdown path=README.md . "
    "Short explanations may appear outside the file blocks."
)
_MODE_HINTS = {
    "code": " Produce a single file unless the task genuinely needs more.",
    "structured": " Produce the requested data file (JSON, YAML, CSV, ...).",
    "project": " Produce every file the project needs, in a sensible folder structure.",
}


def stage_system_prompt(base: str, output_mode: Optional[str]) -> str:
    """The system prompt for a stage: `base` unchanged unless the stage should produce files."""
    hint = _MODE_HINTS.get(output_mode or "")
    return base + _FILE_FORMAT + hint if hint else base
