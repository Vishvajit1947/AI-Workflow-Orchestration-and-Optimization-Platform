"""
Sandbox runner: executes generated projects in throwaway Docker containers.

This service is the only part of the platform with Docker access. The backend asks it to
(1) create a sandbox for one project component, (2) run allow-listed step kinds in it,
(3) delete it. It never runs a command string supplied by the caller.

Isolation per sandbox:
  - fresh container from a pinned image (python:3.11-slim / node:20-slim), non-root user
  - project files copied in with put_archive; no host folder is mounted
  - all capabilities dropped, no-new-privileges, CPU / memory / process limits
  - network only for install steps; disconnected (one-way) before any project code runs
  - per-step timeout (the container is killed when it is exceeded) and output cap
  - deleted after use; an idle-sandbox reaper removes anything left behind

Every request needs the shared X-Runner-Token; with no token configured, all requests
are refused (fail closed).
"""
import hmac
import io
import os
import re
import tarfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Optional

import docker
from docker.errors import DockerException, NotFound
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

PROJECTS_ROOT = Path(os.environ.get("PROJECTS_ROOT", "/var/projects")).resolve()
RUNNER_TOKEN = os.environ.get("RUNNER_TOKEN", "")
MEMORY = os.environ.get("SANDBOX_MEMORY", "1g")
NANO_CPUS = int(float(os.environ.get("SANDBOX_CPUS", "1")) * 1_000_000_000)
PIDS_LIMIT = int(os.environ.get("SANDBOX_PIDS", "256"))
MAX_OUTPUT_CHARS = int(os.environ.get("SANDBOX_MAX_OUTPUT_CHARS", "60000"))
MAX_SANDBOX_SECONDS = int(os.environ.get("SANDBOX_MAX_LIFETIME_SECONDS", "1800"))
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SANDBOX_LABEL = "ai-orchestrator.sandbox"
UID = "1000:1000"

IMAGES = {"python": "python:3.11-slim", "node": "node:20-slim"}

PIP = ["pip", "install", "--user", "--no-cache-dir", "--disable-pip-version-check"]


@dataclass(frozen=True)
class StepSpec:
    runtime: str
    argv: tuple
    network: bool
    timeout: int  # seconds, upper bound (a request may ask for less)


STEPS: dict[str, StepSpec] = {
    "pip_install": StepSpec("python", (*PIP, "-r", "requirements.txt"), True, 600),
    "pip_install_pytest": StepSpec("python", (*PIP, "pytest"), True, 300),
    "py_compile": StepSpec("python", ("python", "-m", "compileall", "-q", "."), False, 120),
    "py_import": StepSpec("python", (), False, 120),  # argv built from a validated module name
    "pytest": StepSpec("python", ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider"), False, 300),
    "npm_install": StepSpec("node", ("npm", "install", "--no-audit", "--no-fund", "--loglevel=error"), True, 600),
    "npm_build": StepSpec("node", ("npm", "run", "build"), False, 300),
    "npm_test": StepSpec("node", ("npm", "test"), False, 300),
}

_WORKSPACE = re.compile(r"^[0-9a-f-]{36}/[0-9a-f-]{36}$")
_MODULE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_CWD = re.compile(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$")
_SKIP_UPLOAD = {"node_modules", ".git", "__pycache__", ".venv", "venv"}
_ENV = {
    "HOME": "/tmp/home", "CI": "true", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1", "NPM_CONFIG_UPDATE_NOTIFIER": "false",
    "NPM_CONFIG_CACHE": "/tmp/home/.npm", "PATH": "/tmp/home/.local/bin:/usr/local/bin:/usr/bin:/bin",
}

app = FastAPI(title="Sandbox runner", docs_url=None, redoc_url=None, openapi_url=None)
_docker: Optional[docker.DockerClient] = None
_lock = threading.Lock()


def client() -> docker.DockerClient:
    global _docker
    if _docker is None:
        try:
            _docker = docker.from_env()
            _docker.ping()
        except DockerException as e:
            _docker = None
            raise HTTPException(503, f"Docker is not available to the runner: {e}")
    return _docker


@dataclass
class Sandbox:
    id: str
    runtime: str
    container_id: str
    created: float = field(default_factory=time.monotonic)
    network_open: bool = True
    dead: Optional[str] = None  # reason the sandbox can no longer run steps
    busy: bool = False


SANDBOXES: dict[str, Sandbox] = {}


def require_token(x_runner_token: str = Header(default="")) -> None:
    if not RUNNER_TOKEN or not hmac.compare_digest(x_runner_token, RUNNER_TOKEN):
        raise HTTPException(401, "Invalid runner token")


# ---------- workspace upload ----------

def _workspace_tar(workspace: str) -> bytes:
    """The project folder as a tar under 'workspace/', owned by the sandbox user, no symlinks."""
    if not _WORKSPACE.match(workspace):
        raise HTTPException(400, "Invalid workspace")
    root = (PROJECTS_ROOT / workspace).resolve()
    if PROJECTS_ROOT not in root.parents or not root.is_dir():
        raise HTTPException(404, "Workspace not found")
    buffer, total = io.BytesIO(), 0

    def owned(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = 1000
        info.uname = info.gname = ""
        return info

    with tarfile.open(fileobj=buffer, mode="w") as tar:
        top = tarfile.TarInfo("workspace")
        top.type, top.mode = tarfile.DIRTYPE, 0o755
        tar.addfile(owned(top))
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_UPLOAD and not os.path.islink(os.path.join(dirpath, d))]
            for d in dirnames:
                rel = PurePosixPath(Path(dirpath, d).relative_to(root).as_posix())
                info = tarfile.TarInfo(f"workspace/{rel}")
                info.type, info.mode = tarfile.DIRTYPE, 0o755
                tar.addfile(owned(info))
            for name in filenames:
                full = Path(dirpath, name)
                if full.is_symlink() or not full.is_file():
                    continue
                data = full.read_bytes()
                total += len(data)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Project is too large to run")
                info = tarfile.TarInfo(f"workspace/{full.relative_to(root).as_posix()}")
                info.size, info.mode = len(data), 0o644
                tar.addfile(owned(info), io.BytesIO(data))
    return buffer.getvalue()


# ---------- API ----------

class CreateSandbox(BaseModel):
    runtime: str
    workspace: str
    request_id: Optional[str] = None


class RunStep(BaseModel):
    kind: str
    cwd: str = ""
    module: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=1)


@app.get("/health")
def health(_: None = Depends(require_token)):
    c = client()
    images = {}
    for runtime, image in IMAGES.items():
        try:
            c.images.get(image)
            images[runtime] = "present"
        except NotFound:
            images[runtime] = "will be pulled on first use"
    return {"docker": True, "images": images, "active_sandboxes": len(SANDBOXES)}


@app.post("/sandboxes", status_code=201)
def create_sandbox(body: CreateSandbox, _: None = Depends(require_token)):
    if body.runtime not in IMAGES:
        raise HTTPException(400, f"Unsupported runtime: {body.runtime}")
    archive = _workspace_tar(body.workspace)
    c = client()
    image = IMAGES[body.runtime]
    try:
        try:
            c.images.get(image)
        except NotFound:
            c.images.pull(image)
        container = c.containers.create(
            image, command=["sleep", str(MAX_SANDBOX_SECONDS)], user=UID, working_dir="/workspace",
            environment=_ENV, mem_limit=MEMORY, memswap_limit=MEMORY, nano_cpus=NANO_CPUS,
            pids_limit=PIDS_LIMIT, cap_drop=["ALL"], security_opt=["no-new-privileges"],
            network_mode="bridge", init=True, labels={SANDBOX_LABEL: "1"},
        )
        container.put_archive("/", archive)
        container.start()
        container.exec_run(["mkdir", "-p", "/tmp/home"], user=UID)
    except DockerException as e:
        raise HTTPException(503, f"Could not start a sandbox: {e}")
    sandbox = Sandbox(id=str(uuid.uuid4()), runtime=body.runtime, container_id=container.id)
    with _lock:
        SANDBOXES[sandbox.id] = sandbox
    return {"id": sandbox.id}


def _argv(kind: str, spec: StepSpec, module: Optional[str]) -> list[str]:
    if kind != "py_import":
        return list(spec.argv)
    if not module or not _MODULE.match(module):
        raise HTTPException(400, "Invalid module name")
    return ["python", "-c", f"import importlib, sys; sys.path.insert(0, '.'); importlib.import_module('{module}')"]


def _tail(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return "[... output truncated ...]\n" + text[-MAX_OUTPUT_CHARS:], True


@app.post("/sandboxes/{sandbox_id}/steps")
def run_step(sandbox_id: str, body: RunStep, _: None = Depends(require_token)):
    sandbox = SANDBOXES.get(sandbox_id)
    if sandbox is None:
        raise HTTPException(404, "Sandbox not found")
    spec = STEPS.get(body.kind)
    if spec is None:
        raise HTTPException(400, f"Step kind not allowed: {body.kind}")
    if spec.runtime != sandbox.runtime:
        raise HTTPException(400, f"Step {body.kind} needs the {spec.runtime} runtime")
    cwd = body.cwd.strip("/")
    if cwd and (not _CWD.match(cwd) or ".." in cwd.split("/")):
        raise HTTPException(400, "Invalid working directory")
    argv = _argv(body.kind, spec, body.module)
    if sandbox.dead:
        return {"exit_code": None, "output": f"Sandbox unusable: {sandbox.dead}", "duration_ms": 0,
                "timed_out": False, "truncated": False}
    if spec.network and not sandbox.network_open:
        raise HTTPException(409, "Install steps must run before any project code")
    if sandbox.busy:
        raise HTTPException(409, "A step is already running in this sandbox")

    c = client()
    container = c.containers.get(sandbox.container_id)
    if not spec.network and sandbox.network_open:
        # One-way: from here on nothing in this sandbox can reach the network
        try:
            c.networks.get("bridge").disconnect(container, force=True)
        except DockerException as e:
            raise HTTPException(503, f"Could not isolate the sandbox network: {e}")
        sandbox.network_open = False

    timeout = min(body.timeout_seconds or spec.timeout, spec.timeout)
    sandbox.busy = True
    started = time.monotonic()
    chunks: list[bytes] = []
    size = 0
    try:
        exec_id = c.api.exec_create(container.id, argv, workdir=f"/workspace/{cwd}".rstrip("/"),
                                    user=UID, environment=_ENV)["Id"]
        stream = c.api.exec_start(exec_id, stream=True, demux=False)

        def pump():
            nonlocal size
            for chunk in stream:
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_OUTPUT_CHARS * 8:  # keep memory bounded; only the tail is returned
                    del chunks[: len(chunks) // 2]
                    size = sum(map(len, chunks))

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        reader.join(timeout)
        timed_out = reader.is_alive()
        if timed_out:
            sandbox.dead = f"step '{body.kind}' exceeded {timeout}s and the sandbox was stopped"
            container.kill()
            reader.join(10)
        exit_code = None if timed_out else c.api.exec_inspect(exec_id).get("ExitCode")
        if sandbox_id not in SANDBOXES:  # deleted (cancelled) while running
            exit_code, timed_out = None, False
            chunks.append(b"\n[cancelled]\n")
    except DockerException as e:
        sandbox.dead = f"docker error: {e}"
        return {"exit_code": None, "output": f"Sandbox error: {e}", "duration_ms": int((time.monotonic() - started) * 1000),
                "timed_out": False, "truncated": False}
    finally:
        sandbox.busy = False
    output, truncated = _tail(b"".join(chunks).decode("utf-8", errors="replace"))
    if timed_out:
        output += f"\n[timed out after {timeout}s]"
    return {"exit_code": exit_code, "output": output, "duration_ms": int((time.monotonic() - started) * 1000),
            "timed_out": timed_out, "truncated": truncated}


def _remove(sandbox: Sandbox) -> None:
    try:
        client().containers.get(sandbox.container_id).remove(force=True)
    except (DockerException, HTTPException):
        pass


@app.delete("/sandboxes/{sandbox_id}", status_code=204)
def delete_sandbox(sandbox_id: str, _: None = Depends(require_token)):
    with _lock:
        sandbox = SANDBOXES.pop(sandbox_id, None)
    if sandbox is not None:
        _remove(sandbox)  # also stops a step that is still running (cancellation)


def _reaper() -> None:
    while True:
        time.sleep(30)
        now = time.monotonic()
        with _lock:
            expired = [s for s in SANDBOXES.values() if now - s.created > MAX_SANDBOX_SECONDS]
            for s in expired:
                SANDBOXES.pop(s.id, None)
        for s in expired:
            _remove(s)


@app.on_event("startup")
def startup() -> None:
    # Containers from a previous runner process are orphans: remove them
    try:
        for container in docker.from_env().containers.list(all=True, filters={"label": SANDBOX_LABEL}):
            container.remove(force=True)
    except DockerException:
        pass
    threading.Thread(target=_reaper, daemon=True).start()
