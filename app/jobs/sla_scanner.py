from datetime import datetime, timezone, timedelta
from pymongo.asynchronous.database import AsyncDatabase
from app.services import audit_service, analytics_service
from app.ws.manager import manager

# Fallback thresholds used when DB config is missing for a priority
_DEFAULT_SLA_THRESHOLDS = {
    "stat": 15,
    "urgent": 30,
    "routine": 60,
    "discharge": 45,
    "nicu": 20,
    "chemo": 120,
}

_SLA_PRIORITY_NAMES = list(_DEFAULT_SLA_THRESHOLDS.keys())

_WARNING_FRACTION = 0.75


async def _get_threshold(db: AsyncDatabase, priority: str) -> int:
    """Look up threshold from DB config, falling back to the hardcoded default."""
    doc = await db.sla_config.find_one({"priority": priority})
    if doc and doc.get("threshold_min") is not None:
        return int(doc["threshold_min"])
    return _DEFAULT_SLA_THRESHOLDS.get(priority, 60)


async def scan_all_slas(db: AsyncDatabase):
    for priority in _SLA_PRIORITY_NAMES:
        await _scan_priority(db, priority)

async def scan_stat_slas(db: AsyncDatabase):
    await _scan_priority(db, "stat")

async def scan_urgent_slas(db: AsyncDatabase):
    await _scan_priority(db, "urgent")

async def scan_routine_slas(db: AsyncDatabase):
    await _scan_priority(db, "routine")

async def scan_nicu_slas(db: AsyncDatabase):
    await _scan_priority(db, "nicu")

async def scan_discharge_slas(db: AsyncDatabase):
    await _scan_priority(db, "discharge")

async def scan_chemo_slas(db: AsyncDatabase):
    await _scan_priority(db, "chemo")

async def _scan_priority(db: AsyncDatabase, priority: str):
    """Detect SLA warnings and breaches for a given priority."""
    threshold_min = await _get_threshold(db, priority)
    now = datetime.now(timezone.utc)
    warning_cutoff = now - timedelta(minutes=threshold_min * _WARNING_FRACTION)
    breach_cutoff = now - timedelta(minutes=threshold_min)

    # Find all active prescriptions for this priority that are not yet breached
    query = {
        "status": {"$in": ["submitted", "flagged"]},
        "priority": priority,
        "sla_breached": {"$ne": True},
    }

    async for rx in db.prescriptions.find(query):
        submitted_at = rx.get("submitted_at")
        if not submitted_at:
            continue

        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=timezone.utc)

        elapsed_min = (now - submitted_at).total_seconds() / 60
        rx_id_str = str(rx["_id"])

        if elapsed_min >= threshold_min:
            # Full breach - check for duplicate
            existing_breach = await db.audit_records.find_one({
                "prescription_id": rx_id_str,
                "flag_code": "sla_breach",
                "type": "sla_breach",
            })
            if existing_breach:
                continue

            breach_duration = elapsed_min - threshold_min

            await db.prescriptions.update_one(
                {"_id": rx["_id"]},
                {
                    "$set": {
                        "sla_breached": True,
                        "sla_breach_duration_min": breach_duration,
                        "tat_breached_at": now,
                        "updated_at": now,
                    }
                },
            )

            await db.audit_records.insert_one({
                "prescription_id": rx_id_str,
                "patient_id": rx.get("patient_id"),
                "visit_id": rx.get("visit_id"),
                "department_id": rx.get("department_id"),
                "flag_code": "sla_breach",
                "type": "sla_breach",
                "issue": (
                    f"SLA breach: {priority} prescription exceeded {threshold_min} min "
                    f"threshold by {breach_duration:.1f} min"
                ),
                "severity": "high",
                "recommendation": "Expedite pharmacy processing immediately",
                "created_by": "system",
                "created_by_role": "system",
                "resolved": False,
                "countersigned": False,
                "sla_threshold_min": float(threshold_min),
                "tat_pharmacy_min_at_flag": elapsed_min,
                "created_at": now,
            })

            doctor_id_val = rx.get("doctor_id")
            rooms = ["pharmacy", "auditor", "admin"]
            if doctor_id_val:
                rooms.append(f"doctor:{str(doctor_id_val)}")

            await manager.broadcast_multi(rooms, {
                "event_type": "sla.breached",
                "entity_id": rx_id_str,
                "entity_type": "prescription",
                "message": f"SLA breach: {priority} prescription",
                "data": {
                    "rx_id": rx_id_str,
                    "priority": priority,
                    "breach_min": round(breach_duration, 1),
                    "threshold_min": threshold_min,
                },
                "timestamp": now.isoformat(),
                "triggered_by_role": "system",
            })

        elif elapsed_min >= threshold_min * _WARNING_FRACTION:
            
            # Warning threshold - check for duplicate
            existing_warning = await db.audit_records.find_one({
                "prescription_id": rx_id_str,
                "flag_code": "sla_warning",
                "type": "sla_warning",
            })
            if existing_warning:
                continue

            await db.audit_records.insert_one({
                "prescription_id": rx_id_str,
                "patient_id": rx.get("patient_id"),
                "visit_id": rx.get("visit_id"),
                "department_id": rx.get("department_id"),
                "flag_code": "sla_warning",
                "type": "sla_warning",
                "issue": (
                    f"SLA warning: {priority} prescription at {elapsed_min:.1f} min "
                    f"({_WARNING_FRACTION * 100:.0f}% of {threshold_min} min threshold)"
                ),
                "severity": "medium",
                "recommendation": "Prioritise this prescription to avoid SLA breach",
                "created_by": "system",
                "created_by_role": "system",
                "resolved": False,
                "countersigned": False,
                "sla_threshold_min": float(threshold_min),
                "tat_pharmacy_min_at_flag": elapsed_min,
                "created_at": now,
            })

            doctor_id_val = rx.get("doctor_id")
            rooms = ["pharmacy", "auditor"]
            if doctor_id_val:
                rooms.append(f"doctor:{str(doctor_id_val)}")

            await manager.broadcast_multi(rooms, {
                "event_type": "sla.warning_threshold_reached",
                "entity_id": rx_id_str,
                "entity_type": "prescription",
                "message": f"SLA warning: {priority} prescription approaching threshold",
                "data": {
                    "rx_id": rx_id_str,
                    "priority": priority,
                    "elapsed_min": round(elapsed_min, 1),
                    "threshold_min": threshold_min,
                    "pct_elapsed": round(elapsed_min / threshold_min * 100, 1),
                },
                "timestamp": now.isoformat(),
                "triggered_by_role": "system",
            })


async def run_flag_escalation(db: AsyncDatabase):
    await audit_service.escalate_overdue_flags(db)


async def generate_daily_report(db: AsyncDatabase):
    from datetime import timezone as tz
    yesterday = datetime.now(tz.utc) - timedelta(days=1)
    date_from = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    date_to = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)

    summary = await analytics_service.get_tat_summary(db, date_from, date_to)

    await db.daily_reports.insert_one({
        "date": date_from,
        "summary": summary,
        "created_at": datetime.now(tz.utc),
    })
