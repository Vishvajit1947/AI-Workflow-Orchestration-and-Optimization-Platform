"""
The build / repair loop for one project, persisted as a ProjectRun.

    write files -> for each component: fresh sandbox -> install / build / test steps
    a step fails -> LLM diagnosis + validated fix -> apply (previous contents kept) -> rebuild
    ... until every step passes or the repair limit is reached.

Outcomes are only ever what actually happened: "succeeded" requires every step of every
component to exit 0 in this run; a sandbox that cannot be used gives "unavailable"; the
repair limit gives "failed" with the remaining error.

All database work goes through `self.lock` because the build runs as a stage of the
execution engine, which shares one session between concurrently running stages.
"""
import asyncio
import contextlib
import hashlib
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from backend.app.config import settings
from backend.app.models.project import Project, ProjectRun
from backend.app.services.project_builder.repair import LLMCall, propose_fix
from backend.app.services.project_builder.sandbox import Sandbox, SandboxUnavailable, StepResult
from backend.app.services.project_builder.structure import ProjectStructure, analyze_structure
from backend.app.services.project_builder.workspace import ProjectWorkspaceService

MAX_STORED_OUTPUT = 20_000
MAX_STORED_PREVIOUS = 100_000

Progress = Callable[[str], Awaitable[None]]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectBuildService:
    def __init__(self, workspace: ProjectWorkspaceService, sandbox: Sandbox, llm: Optional[LLMCall], *,
                 lock: Optional[asyncio.Lock] = None, commit: Optional[Callable[[], Awaitable[None]]] = None,
                 progress: Optional[Progress] = None, is_cancelled: Callable[[], bool] = lambda: False,
                 max_repairs: Optional[int] = None):
        self.ws = workspace
        self.sandbox = sandbox
        self.llm = llm
        self.lock = lock or asyncio.Lock()
        self._commit = commit
        self._progress = progress
        self.is_cancelled = is_cancelled
        self.max_repairs = settings.PROJECT_MAX_REPAIR_ATTEMPTS if max_repairs is None else max_repairs
        self.extra_warnings: list[str] = []

    # ---------- persistence helpers ----------

    async def _save(self) -> None:
        async with self.lock:
            await self.ws.db.flush()
            if self._commit:
                await self._commit()

    async def _report(self, run: ProjectRun, text: str) -> None:
        run.current_step = text[:255]
        await self._save()
        if self._progress:
            await self._progress(text)

    async def _finish(self, project: Project, run: ProjectRun, status: str, error: Optional[str] = None) -> ProjectRun:
        run.status = status
        run.error_summary = error
        run.current_step = None
        run.completed_at = _now()
        project.status = status
        await self._save()
        return run

    # ---------- entry points ----------

    async def build(self, project: Project, files: list[dict], execution_id=None,
                    warnings: Optional[list[str]] = None) -> ProjectRun:
        """Write `files` ([{"path", "content"}]) into the project's workspace, then build it.
        `warnings` (e.g. files that could not be extracted) are kept with the run."""
        self.extra_warnings = list(warnings or [])
        async with self.lock:
            await self.ws.replace_files(project, files)
            project.execution_id = execution_id
            project.status = "building"
            run = ProjectRun(project_id=project.id, execution_id=execution_id, status="running")
            self.ws.db.add(run)
        await self._save()
        try:
            return await self._build(project, run)
        except asyncio.CancelledError:
            # Record the cancellation even though this task is being cancelled
            with contextlib.suppress(Exception):
                await asyncio.shield(self._finish(project, run, "cancelled", "Cancelled by user"))
            raise

    async def _build(self, project: Project, run: ProjectRun) -> ProjectRun:
        async with self.lock:
            files = await self.ws.read_all(project)
        structure = analyze_structure(files)
        run.project_type = project.project_type = structure.project_type
        run.warnings = self.extra_warnings + structure.warnings
        if not structure.components:
            return await self._finish(project, run, "failed",
                                      "No runnable component was generated (no package.json, requirements.txt, "
                                      "pyproject.toml or Python files).")

        for attempt in range(self.max_repairs + 1):
            try:
                failed = await self._run_components(project, run, structure, attempt)
            except SandboxUnavailable as e:
                return await self._finish(project, run, "unavailable",
                                          f"The project could not be executed: {e}. It was not run, so it is "
                                          "not marked as working.")
            # Checked first: a cancelled run stops early without a failed step, which must
            # never be mistaken for "every step passed"
            if self.is_cancelled():
                return await self._finish(project, run, "cancelled", "Cancelled by user")
            if failed is None:
                return await self._finish(project, run, "succeeded")
            summary = (f"{failed['label']} failed in {failed['component']} "
                       f"(exit code {failed['exit_code']}{', timed out' if failed['timed_out'] else ''}).\n\n"
                       f"{failed['output'][-1500:]}")
            if attempt == self.max_repairs:
                return await self._finish(project, run, "failed",
                                          f"Still failing after {self.max_repairs} automatic repair attempt(s). {summary}")
            if self.llm is None:
                return await self._finish(project, run, "failed", f"No model available to repair the project. {summary}")

            files, structure, fixed = await self._repair(project, run, files, failed, attempt + 1)
            # A fix can change what the project is (e.g. adding fastapi to requirements.txt)
            run.project_type = project.project_type = structure.project_type
            run.warnings = self.extra_warnings + structure.warnings
            if not fixed:
                return await self._finish(project, run, "failed",
                                          f"The AI could not propose a fix for this error. {summary}")
        return run  # not reached

    # ---------- execution ----------

    async def _run_components(self, project: Project, run: ProjectRun, structure: ProjectStructure,
                              attempt: int) -> Optional[dict]:
        """Run every step of every component; returns the first failed step record, else None."""
        workspace = self.ws.relative_workspace(project)
        for component in structure.components:
            if self.is_cancelled():
                return None
            await self._report(run, f"Starting {component.runtime} sandbox for {component.name}")
            session = await self.sandbox.open(component.runtime, workspace)
            try:
                for step in component.steps:
                    if self.is_cancelled():
                        return None
                    await self._report(run, f"{step.label} ({component.name})")
                    result: StepResult = await session.run_step(step.kind, step.cwd, step.module)
                    record = {
                        "attempt": attempt, "component": component.name, "kind": step.kind,
                        "label": step.label, "command": step.command, "cwd": step.cwd,
                        "status": "passed" if result.ok else "failed", "exit_code": result.exit_code,
                        "duration_ms": result.duration_ms, "timed_out": result.timed_out,
                        "output": result.output[-MAX_STORED_OUTPUT:],
                    }
                    run.steps = [*run.steps, record]  # reassign so the JSONB change is saved
                    await self._save()
                    if not result.ok:
                        return record
            finally:
                await session.close()
        return None

    # ---------- repair ----------

    async def _repair(self, project: Project, run: ProjectRun, files: dict[str, str], failed: dict,
                      attempt: int) -> tuple[dict[str, str], ProjectStructure, bool]:
        await self._report(run, f"Analyzing the error (repair attempt {attempt} of {self.max_repairs})")
        record = {"attempt": attempt, "failed_step": f"{failed['label']} ({failed['component']})",
                  "diagnosis": "", "files": [], "model": None, "error": None}
        try:
            fix = await propose_fix(self.llm, files, failed, run.repairs)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # the repair model failed; report it, never crash the build
            record["error"] = f"Repair model call failed: {e}"
            run.repairs = [*run.repairs, record]
            await self._save()
            return files, analyze_structure(files), False

        record["diagnosis"], record["model"] = fix.diagnosis, fix.model
        if fix.rejected:
            record["error"] = "; ".join(fix.rejected)[:1000]
        if fix.files:
            await self._report(run, f"Applying fix to {len(fix.files)} file(s) (repair attempt {attempt})")
            async with self.lock:
                for path, content in fix.files.items():
                    previous = files.get(path)
                    await self.ws.write_file(project, path, content)
                    record["files"].append({
                        "path": path,
                        "action": "modified" if previous is not None else "created",
                        "previous_sha256": _sha(previous) if previous is not None else None,
                        "previous_content": previous if previous is not None and len(previous) <= MAX_STORED_PREVIOUS else None,
                        "new_sha256": _sha(content),
                    })
            files = {**files, **fix.files}
        run.repairs = [*run.repairs, record]
        await self._save()
        return files, analyze_structure(files), bool(fix.files)


def summarize(run: ProjectRun, project: Project) -> str:
    """Markdown summary used as the build stage's output."""
    headline = {
        "succeeded": "Project built and verified: every install, build and test step passed.",
        "failed": "Project build failed.",
        "unavailable": "Project was generated but could not be executed.",
        "cancelled": "Project build was cancelled.",
    }.get(run.status, f"Project build {run.status}.")
    lines = [f"## {project.name}", "", headline, "", f"- Project type: {run.project_type or 'unknown'}"]
    last_attempt = max((s["attempt"] for s in run.steps), default=0)
    for s in (s for s in run.steps if s["attempt"] == last_attempt):
        mark = "PASS" if s["status"] == "passed" else "FAIL"
        lines.append(f"- {mark} {s['label']} ({s['component']}): `{s['command']}`")
    if run.repairs:
        lines += ["", f"Automatic repairs: {len(run.repairs)}"]
        for r in run.repairs:
            changed = ", ".join(f["path"] for f in r["files"]) or "no files changed"
            lines.append(f"- Attempt {r['attempt']}: {r['diagnosis'][:300]} ({changed})")
    if run.warnings:
        lines += ["", "Warnings:"] + [f"- {w}" for w in run.warnings]
    if run.error_summary:
        lines += ["", "Remaining error:", "```", run.error_summary[-2000:], "```"]
    return "\n".join(lines)
