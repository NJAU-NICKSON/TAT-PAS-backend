from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pymongo.asynchronous.database import AsyncDatabase


# Record one user action for accountability.
async def log_action(
    db: AsyncDatabase,
    action: str,
    user_id: Optional[str],
    user_role: Optional[str],
    user_name: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    detail: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    try:
        await db.activity_log.insert_one({
            "action": action,
            "user_id": user_id,
            "user_role": user_role,
            "user_name": user_name,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "detail": detail,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        # Logging must never break the action it records.
        pass


# List activity log entries, newest first, with optional filters.
async def list_activity(
    db: AsyncDatabase,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    query: dict = {}
    if action:
        query["action"] = action
    if user_id:
        query["user_id"] = user_id
    if user_role:
        query["user_role"] = user_role

    cursor = db.activity_log.find(query).sort("created_at", -1).skip(skip).limit(limit)
    out = []
    async for d in cursor:
        out.append({
            "id": str(d["_id"]),
            "action": d.get("action"),
            "user_id": d.get("user_id"),
            "user_role": d.get("user_role"),
            "user_name": d.get("user_name"),
            "entity_type": d.get("entity_type"),
            "entity_id": d.get("entity_id"),
            "detail": d.get("detail"),
            "ip_address": d.get("ip_address"),
            "created_at": d.get("created_at"),
        })
    return out
