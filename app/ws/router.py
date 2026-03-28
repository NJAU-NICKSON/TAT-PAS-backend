import json
import asyncio
import logging
from bson import ObjectId
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from app.security.jwt import decode_token
from app.db.client import get_database
from app.ws.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

PING_INTERVAL = 25  # seconds between server-side pings


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint with first-message token authentication.

    Protocol:
    1. Server accepts the connection.
    2. Client sends: {"type": "auth", "token": "<access_jwt>"}
    3. Server replies: {"type": "auth_ok", "room": "<room>"}
       or closes with 1008 Policy Violation on auth failure.
    4. Server sends periodic {"type": "ping"} frames; client may respond
       with {"type": "pong"} (ignored if not sent — TCP keepalive handles it).
    """
    await websocket.accept()

    # ── Step 1: read auth frame ──────────────────────────────────────
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        frame = json.loads(raw)
    except (asyncio.TimeoutError, Exception):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if frame.get("type") != "auth" or not frame.get("token"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # ── Step 2: validate token and confirm user still exists in DB ───
    try:
        payload = decode_token(frame["token"])
        if payload.get("type") != "access":
            raise ValueError("not an access token")
        user_id = payload.get("sub")
        role = payload.get("role")
        department_id = payload.get("department_id")
        if not user_id or not role:
            raise ValueError("missing sub or role")

        db = await get_database()
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user_doc:
            raise ValueError("user not found")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # ── Step 3: assign room ──────────────────────────────────────────
    if role == "pharmacist":
        room = "pharmacy"
    elif role == "auditor":
        room = "auditor"
    elif role == "admin":
        room = "admin"
    elif role == "billing":
        room = "billing"
    elif role == "receptionist":
        room = "receptionist"
    elif role == "doctor":
        room = f"doctor:{user_id}"
    elif role == "nurse":
        room = f"ward:{department_id}" if department_id else "ward:general"
    else:
        room = "general"

    # Register into the manager using the lock — avoids race conditions
    async with manager._lock:
        if room not in manager.active_connections:
            manager.active_connections[room] = []
        manager.active_connections[room].append(websocket)

    # ── Step 4: confirm auth ─────────────────────────────────────────
    try:
        await websocket.send_text(json.dumps({"type": "auth_ok", "room": room}))
    except Exception:
        await manager.disconnect(websocket, room)
        return

    # ── Step 5: message loop with periodic ping ──────────────────────
    async def _ping_loop():
        while True:
            await asyncio.sleep(PING_INTERVAL)
            try:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break

    ping_task = asyncio.create_task(_ping_loop())

    try:
        while True:
            # Consume client frames (pong / ignored messages)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "pong":
                    pass  # acknowledged
            except Exception:
                pass  # malformed frame — ignore
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ping_task.cancel()
        await manager.disconnect(websocket, room)
