from typing import Dict, List, Set
from fastapi import WebSocket
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, room: str):
        """Accept and register a WebSocket connection into a room."""
        await websocket.accept()
        async with self._lock:
            if room not in self.active_connections:
                self.active_connections[room] = []
            self.active_connections[room].append(websocket)

    async def disconnect(self, websocket: WebSocket, room: str):
        """Remove a WebSocket from a room safely."""
        async with self._lock:
            if room in self.active_connections:
                try:
                    self.active_connections[room].remove(websocket)
                except ValueError:
                    pass
                # Garbage-collect empty rooms
                if not self.active_connections[room]:
                    del self.active_connections[room]

    async def broadcast(self, room: str, event: dict):
        """Send an event to every live connection in a room."""
        async with self._lock:
            connections = list(self.active_connections.get(room, []))

        if not connections:
            return

        message = json.dumps(event, default=str)
        dead: List[WebSocket] = []

        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception as exc:
                logger.debug("Dead WebSocket in room %s: %s", room, exc)
                dead.append(ws)

        # Remove dead connections
        if dead:
            async with self._lock:
                for ws in dead:
                    try:
                        self.active_connections[room].remove(ws)
                    except (ValueError, KeyError):
                        pass
                if room in self.active_connections and not self.active_connections[room]:
                    del self.active_connections[room]

    async def broadcast_multi(self, rooms: List[str], event: dict):
        """Broadcast the same event to multiple rooms concurrently."""
        await asyncio.gather(
            *(self.broadcast(room, event) for room in rooms),
            return_exceptions=True,
        )

    async def broadcast_all(self, event: dict):
        """Broadcast to every connected room."""
        async with self._lock:
            rooms = list(self.active_connections.keys())
        await self.broadcast_multi(rooms, event)

    def connection_count(self) -> Dict[str, int]:
        """Return the number of live connections per room (for health checks)."""
        return {room: len(conns) for room, conns in self.active_connections.items()}

    def total_connections(self) -> int:
        return sum(len(c) for c in self.active_connections.values())


manager = ConnectionManager()
