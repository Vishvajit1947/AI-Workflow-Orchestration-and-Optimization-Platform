"""
Client for the sandbox runner service (see /runner).

Generated code never runs in this process. The runner is a separate service that alone
has access to Docker; for each component it creates a throwaway container, copies the
project in (no host folders are mounted), and runs allow-listed step *kinds* with CPU,
memory, process, time and output limits. Network is available to install steps only and
is cut off before anything from the project runs.

If the runner is not configured or not reachable, SandboxUnavailable is raised and the
build is reported as "unavailable"; it is never reported as a success.
"""
import uuid
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx

from backend.app.config import settings


class SandboxUnavailable(RuntimeError):
    """The isolated execution environment cannot be used right now."""


@dataclass
class StepResult:
    exit_code: Optional[int]
    output: str  # combined stdout/stderr, truncated by the runner
    duration_ms: int
    timed_out: bool = False
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class SandboxSession(Protocol):
    async def run_step(self, kind: str, cwd: str, module: Optional[str] = None) -> StepResult: ...
    async def close(self) -> None: ...


class Sandbox(Protocol):
    async def open(self, runtime: str, workspace: str) -> SandboxSession: ...


class _RunnerSession:
    def __init__(self, client: httpx.AsyncClient, sandbox_id: str):
        self.client, self.sandbox_id = client, sandbox_id

    async def run_step(self, kind: str, cwd: str, module: Optional[str] = None) -> StepResult:
        try:
            r = await self.client.post(f"/sandboxes/{self.sandbox_id}/steps",
                                       json={"kind": kind, "cwd": cwd, "module": module})
        except httpx.HTTPError as e:
            raise SandboxUnavailable(f"Sandbox runner stopped responding: {e}") from e
        if r.status_code != 200:
            raise SandboxUnavailable(f"Sandbox runner refused the step ({r.status_code}): {r.text[:300]}")
        body = r.json()
        return StepResult(exit_code=body.get("exit_code"), output=body.get("output", ""),
                          duration_ms=body.get("duration_ms", 0), timed_out=body.get("timed_out", False),
                          truncated=body.get("truncated", False))

    async def close(self) -> None:
        try:
            await self.client.delete(f"/sandboxes/{self.sandbox_id}")
        except httpx.HTTPError:
            pass  # the runner reaps abandoned sandboxes itself
        finally:
            await self.client.aclose()


class RunnerSandbox:
    """Talks to the runner service at settings.SANDBOX_RUNNER_URL."""

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = base_url if base_url is not None else settings.SANDBOX_RUNNER_URL
        self.token = token if token is not None else settings.SANDBOX_RUNNER_TOKEN

    async def open(self, runtime: str, workspace: str) -> SandboxSession:
        if not self.base_url:
            raise SandboxUnavailable("No sandbox runner is configured (SANDBOX_RUNNER_URL is empty)")
        # Steps can take minutes (npm install); the runner enforces its own per-step limits
        client = httpx.AsyncClient(base_url=self.base_url, headers={"X-Runner-Token": self.token or ""},
                                   timeout=httpx.Timeout(900.0, connect=10.0))
        try:
            r = await client.post("/sandboxes", json={"runtime": runtime, "workspace": workspace,
                                                      "request_id": str(uuid.uuid4())})
        except httpx.HTTPError as e:
            await client.aclose()
            raise SandboxUnavailable(f"Sandbox runner is not reachable at {self.base_url}: {e}") from e
        if r.status_code != 201:
            await client.aclose()
            raise SandboxUnavailable(f"Sandbox runner could not start a sandbox ({r.status_code}): {r.text[:300]}")
        return _RunnerSession(client, r.json()["id"])


def default_sandbox() -> Sandbox:
    return RunnerSandbox()
