from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase


_PRIORITY_ORDER = ["stat", "nicu", "urgent", "discharge", "routine", "chemo"]

_DEFAULT_THRESHOLDS = {
    "stat": 15,
    "urgent": 30,
    "routine": 60,
    "discharge": 45,
    "nicu": 20,
    "chemo": 120,
}


async def get_sla_config(db: AsyncDatabase) -> List[Dict[str, Any]]:
    """Return SLA thresholds for all priorities."""
    results = []
    for priority in _PRIORITY_ORDER:
        doc = await db.sla_config.find_one({"priority": priority})
        if doc:
            results.append({
                "priority": priority,
                "threshold_min": doc.get("threshold_min", _DEFAULT_THRESHOLDS.get(priority, 60)),
                "warning_min": round(doc.get("threshold_min", _DEFAULT_THRESHOLDS.get(priority, 60)) * 0.75, 1),
                "updated_at": doc.get("updated_at"),
            })
        else:
            threshold = _DEFAULT_THRESHOLDS.get(priority, 60)
            results.append({
                "priority": priority,
                "threshold_min": threshold,
                "warning_min": round(threshold * 0.75, 1),
                "updated_at": None,
            })
    return results


async def update_sla_config(
    db: AsyncDatabase,
    priority: str,
    threshold_min: float,
    updated_by: str,
) -> Dict[str, Any]:
    """Update the SLA threshold for a given priority."""
    if priority not in _DEFAULT_THRESHOLDS:
        raise ValueError(f"Unknown priority: {priority}. Valid priorities: {list(_DEFAULT_THRESHOLDS.keys())}")

    if threshold_min <= 0:
        raise ValueError("threshold_min must be greater than 0")

    now = datetime.now(timezone.utc)
    await db.sla_config.update_one(
        {"priority": priority},
        {
            "$set": {
                "priority": priority,
                "threshold_min": threshold_min,
                "updated_by": updated_by,
                "updated_at": now,
            }
        },
        upsert=True,
    )

    return {
        "priority": priority,
        "threshold_min": threshold_min,
        "warning_min": round(threshold_min * 0.75, 1),
        "updated_at": now.isoformat(),
    }


async def get_live_breaches(db: AsyncDatabase) -> List[Dict[str, Any]]:
    """Return all currently active SLA breaches."""
    now = datetime.now(timezone.utc)

    cursor = db.prescriptions.find({
        "status": {"$in": ["submitted", "flagged"]},
        "sla_breached": True,
    }).sort("submitted_at", 1)

    docs = await cursor.to_list(length=None)
    breaches = []

    for doc in docs:
        submitted_at = doc.get("submitted_at")
        if submitted_at and submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=timezone.utc)

        elapsed_min = (now - submitted_at).total_seconds() / 60 if submitted_at else 0
        threshold = doc.get("sla_threshold_min", _DEFAULT_THRESHOLDS.get(doc.get("priority", "routine"), 60))
        breach_duration = max(0.0, elapsed_min - threshold)

        breaches.append({
            "prescription_id": str(doc["_id"]),
            "rx_number": doc.get("rx_number"),
            "patient_id": str(doc.get("patient_id", "")),
            "priority": doc.get("priority", "routine"),
            "status": doc.get("status"),
            "submitted_at": submitted_at.isoformat() if submitted_at else None,
            "elapsed_min": round(elapsed_min, 1),
            "threshold_min": threshold,
            "breach_duration_min": round(breach_duration, 1),
            "department_id": str(doc.get("department_id", "")) if doc.get("department_id") else None,
        })

    return breaches


async def get_breach_count(db: AsyncDatabase) -> int:
    return await db.prescriptions.count_documents({
        "status": {"$in": ["submitted", "flagged"]},
        "sla_breached": True,
    })
