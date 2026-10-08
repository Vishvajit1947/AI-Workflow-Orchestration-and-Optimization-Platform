"""
WebSocket endpoint for live execution status.

On connect the client receives a {"type": "snapshot"} of the execution (if this
server knows it), then "stage_update" and "execution_status" events as they happen.
Send "ping" to get {"type": "pong"} back (heartbeat).
"""
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.services.execution.tracker import tracker
from backend.app.services.websocket.execution_ws import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/executions/{execution_id}")
async def execution_status_ws(websocket: WebSocket, execution_id: str):
    await manager.connect(websocket, execution_id)
    try:
        try:
            live = tracker.get(uuid.UUID(execution_id))
        except ValueError:
            live = None
        if live is not None:
            await websocket.send_json({"type": "snapshot", **live.snapshot()})
        else:
            await websocket.send_json({"type": "unknown_execution", "execution_id": execution_id})

        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, execution_id)
