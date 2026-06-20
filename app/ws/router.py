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

PING_INTERVAL = 25  


# WebSocket endpoint with first-message token authentication.
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Close the socket, ignoring the case where the client already left.
    async def _safe_close(code: int) -> None:
        try:
            await websocket.close(code=code)
        except (WebSocketDisconnect, RuntimeError):
            pass

    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        frame = json.loads(raw)
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, Exception):
        await _safe_close(status.WS_1008_POLICY_VIOLATION)
        return

    if frame.get("type") != "auth" or not frame.get("token"):
        await _safe_close(status.WS_1008_POLICY_VIOLATION)
        return

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
        await _safe_close(status.WS_1008_POLICY_VIOLATION)
        return

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

    # Every user also joins a personal room so they can be notified directly
    # regardless of department (e.g. a nurse assigned to a care team).
    personal_room = f"user:{user_id}"
    rooms = [room, personal_room]

    async with manager._lock:
        for r in rooms:
            if r not in manager.active_connections:
                manager.active_connections[r] = []
            manager.active_connections[r].append(websocket)

    try:
        await websocket.send_text(json.dumps({"type": "auth_ok", "room": room}))
    except Exception:
        for r in rooms:
            await manager.disconnect(websocket, r)
        return

    # Send periodic pings to keep a WebSocket alive.
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
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "pong":
                    pass  
            except Exception:
                pass 
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ping_task.cancel()
        for r in rooms:
            await manager.disconnect(websocket, r)
