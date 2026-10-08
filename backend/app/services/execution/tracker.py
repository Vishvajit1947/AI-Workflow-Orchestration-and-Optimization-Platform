"""
In-memory tracker for live executions: per-stage status, progress, pause/resume/cancel
control, and event publishing to WebSocket clients.

State lives in this process only; finished executions are kept for a while so late
clients can still fetch their final snapshot. Persistent results are in execution_records.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.app.services.websocket.execution_ws import manager as ws_manager

FINISHED_STAGE_STATUSES = {"completed", "failed", "skipped", "cancelled"}
ACTIVE_STATUSES = {"queued", "running", "paused"}
MAX_FINISHED_EXECUTIONS = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionControl:
    """Pause/resume/cancel flags the execution engine polls; `changed` wakes it up."""

    def __init__(self):
        self.paused = False
        self.cancelled = False
        self.changed = asyncio.Event()

    def pause(self) -> None:
        self.paused = True
        self.changed.set()

    def resume(self) -> None:
        self.paused = False
        self.changed.set()

    def cancel(self) -> None:
        self.cancelled = True
        self.paused = False
        self.changed.set()

    async def wait_for_change(self) -> None:
        await self.changed.wait()
        self.changed.clear()


class LiveExecution:
    def __init__(self, execution_id: uuid.UUID, workflow_id: uuid.UUID, workflow_name: str):
        self.execution_id = execution_id
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.status = "queued"  # queued, running, paused, completed, failed, cancelled
        self.parallel = True
        self.error: Optional[str] = None
        self.stages: dict[str, dict] = {}
        self.dag: Optional[dict] = None
        self.started_at = _now()
        self.completed_at: Optional[str] = None
        self.control = ExecutionControl()
        self.task: Optional[asyncio.Task] = None  # background task, if any

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def progress(self) -> float:
        if not self.stages:
            return 0.0
        done = sum(1 for s in self.stages.values() if s["status"] in FINISHED_STAGE_STATUSES)
        return round(done / len(self.stages), 4)

    def snapshot(self) -> dict:
        return {
            "execution_id": str(self.execution_id),
            "workflow_id": str(self.workflow_id),
            "workflow_name": self.workflow_name,
            "status": self.status,
            "parallel": self.parallel,
            "progress": self.progress,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "stages": sorted(self.stages.values(), key=lambda s: (s["level"], s["stage_order"], s["name"])),
            "dag": self.dag,
        }


class ExecutionTracker:
    def __init__(self):
        self.executions: dict[uuid.UUID, LiveExecution] = {}

    def get(self, execution_id: uuid.UUID) -> Optional[LiveExecution]:
        return self.executions.get(execution_id)

    def find_active(self, workflow_id: uuid.UUID) -> Optional[LiveExecution]:
        return next((e for e in self.executions.values() if e.workflow_id == workflow_id and e.is_active), None)

    def register(self, execution_id: uuid.UUID, workflow_id: uuid.UUID, workflow_name: str) -> LiveExecution:
        """Get or create the live record (the API registers before the engine starts)."""
        live = self.executions.get(execution_id)
        if live is None:
            live = LiveExecution(execution_id, workflow_id, workflow_name)
            self.executions[execution_id] = live
            self._prune()
        return live

    async def start(self, execution_id: uuid.UUID, workflow_id: uuid.UUID, workflow_name: str,
                    stages: list, dag: dict, parallel: bool) -> LiveExecution:
        live = self.register(execution_id, workflow_id, workflow_name)
        levels = {n["stage_id"]: n["level"] for n in dag["nodes"]}
        live.parallel = parallel
        live.dag = dag
        live.stages = {
            str(s.id): {
                "stage_id": str(s.id), "name": s.name, "stage_order": s.stage_order,
                "stage_type": s.stage_type, "level": levels.get(str(s.id), 0), "status": "pending",
                "provider": None, "model": None, "cache_hit": False, "error": None,
                "started_at": None, "completed_at": None,
            }
            for s in stages
        }
        live.status = "paused" if live.control.paused else "running"
        await self._publish(live, {"type": "snapshot", **live.snapshot()})
        return live

    async def update_stage(self, execution_id: uuid.UUID, stage_id: uuid.UUID, **fields) -> None:
        live = self.executions.get(execution_id)
        if live is None or str(stage_id) not in live.stages:
            return
        stage = live.stages[str(stage_id)]
        if fields.get("status") == "running" and not stage["started_at"]:
            stage["started_at"] = _now()
        if fields.get("status") in FINISHED_STAGE_STATUSES:
            stage["completed_at"] = _now()
        stage.update(fields)
        await self._publish(live, {"type": "stage_update", "stage": dict(stage), "progress": live.progress})

    async def set_status(self, execution_id: uuid.UUID, status: str, error: Optional[str] = None) -> None:
        live = self.executions.get(execution_id)
        if live is None or live.status == status:
            return
        live.status = status
        if error:
            live.error = error
        if status not in ACTIVE_STATUSES:
            live.completed_at = _now()
        await self._publish(live, {"type": "execution_status", "status": status,
                                   "progress": live.progress, "error": live.error})

    # ---------- control (called by the API) ----------

    async def pause(self, execution_id: uuid.UUID) -> LiveExecution:
        live = self._require_active(execution_id)
        live.control.pause()
        await self.set_status(execution_id, "paused")
        return live

    async def resume(self, execution_id: uuid.UUID) -> LiveExecution:
        live = self._require_active(execution_id)
        live.control.resume()
        await self.set_status(execution_id, "running")
        return live

    async def cancel(self, execution_id: uuid.UUID) -> LiveExecution:
        live = self._require_active(execution_id)
        live.control.cancel()
        await self._publish(live, {"type": "execution_status", "status": "cancelling", "progress": live.progress})
        return live

    def _require_active(self, execution_id: uuid.UUID) -> LiveExecution:
        live = self.executions.get(execution_id)
        if live is None:
            raise KeyError(execution_id)
        if not live.is_active:
            raise RuntimeError(f"Execution is already {live.status}")
        return live

    async def _publish(self, live: LiveExecution, message: dict) -> None:
        await ws_manager.broadcast(str(live.execution_id), {"execution_id": str(live.execution_id), **message})

    def _prune(self) -> None:
        finished = [e for e in self.executions.values() if not e.is_active]
        for old in finished[:max(0, len(finished) - MAX_FINISHED_EXECUTIONS)]:
            del self.executions[old.execution_id]


tracker = ExecutionTracker()
