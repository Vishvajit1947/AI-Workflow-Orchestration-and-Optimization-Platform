"""
WebSocket endpoint for live execution status.

On connect the client receives a {"type": "snapshot"} of the execution (if this
server knows it), then "stage_update" and "execution_status" events as they happen.
Send "ping" to get {"type": "pong"} back (heartbeat).

Access control happens before the handshake is accepted: the browser sends the same
httponly session cookie it uses for the REST API, and the execution must belong to a
workflow owned by that user. Otherwise the handshake is refused (close code 4401 when
not signed in, 4404 when the execution is unknown or someone else's), and nothing
about the execution is sent.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.ownership import require_owned_execution
from backend.app.database import get_session_factory
from backend.app.services import session_service
from backend.app.services.execution.tracker import tracker
from backend.app.services.websocket.execution_ws import manager

router = APIRouter(tags=["websocket"])

CLOSE_UNAUTHENTICATED = 4401
CLOSE_NOT_FOUND = 4404


async def _authorize(websocket: WebSocket, execution_id: str, session_factory: async_sessionmaker) -> Optional[int]:
    """None when the caller may watch this execution, else the close code to refuse with."""
    token = websocket.cookies.get("session_token")
    if not token:
        return CLOSE_UNAUTHENTICATED
    try:
        execution_uuid = uuid.UUID(execution_id)
    except ValueError:
        return CLOSE_NOT_FOUND
    # Short-lived session: released before the (possibly long) stream starts
    async with session_factory() as db:
        user = await session_service.validate_session(db, token)
        if user is None:
            return CLOSE_UNAUTHENTICATED
        try:
            await require_owned_execution(db, execution_uuid, user.id)
        except HTTPException:
            return CLOSE_NOT_FOUND
        await db.commit()  # keep the session's last_used_at update
    return None


@router.websocket("/ws/executions/{execution_id}")
async def execution_status_ws(
    websocket: WebSocket,
    execution_id: str,
    session_factory: async_sessionmaker = Depends(get_session_factory),
):
    refusal = await _authorize(websocket, execution_id, session_factory)
    if refusal is not None:
        await websocket.close(code=refusal)
        return

    await manager.connect(websocket, execution_id)
    try:
        live = tracker.get(uuid.UUID(execution_id))
        if live is not None:
            await websocket.send_json({"type": "snapshot", **live.snapshot()})
        else:
            # Owned, finished execution no longer held in memory: results come from the REST API
            await websocket.send_json({"type": "unknown_execution", "execution_id": execution_id})

        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, execution_id)
