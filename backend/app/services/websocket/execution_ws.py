"""WebSocket connection manager: fans execution events out to every client watching an execution."""
import asyncio

from fastapi import WebSocket

SEND_TIMEOUT_SECONDS = 5


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, execution_id: str) -> None:
        await websocket.accept()
        self.active_connections.setdefault(execution_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, execution_id: str) -> None:
        connections = self.active_connections.get(execution_id)
        if connections is not None:
            connections.discard(websocket)
            if not connections:
                del self.active_connections[execution_id]

    def connection_count(self, execution_id: str) -> int:
        return len(self.active_connections.get(execution_id, ()))

    async def broadcast(self, execution_id: str, message: dict) -> None:
        """Send to all watchers; drop clients that fail or stall so execution never blocks on them."""
        for websocket in list(self.active_connections.get(execution_id, ())):
            try:
                await asyncio.wait_for(websocket.send_json(message), SEND_TIMEOUT_SECONDS)
            except Exception:
                self.disconnect(websocket, execution_id)


manager = ConnectionManager()
