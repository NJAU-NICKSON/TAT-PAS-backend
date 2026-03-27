from datetime import datetime, timedelta, date, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from app.models.audit import AuditRecordInDB, AuditType, AuditSeverity, ResolutionType, SecurityEventType
from fastapi import HTTPException, status as http_status


def _make_snapshot_safe(doc: Optional[dict]) -> Optional[dict]:
    """Convert a MongoDB document to a JSON-safe dict by stringifying ObjectIds."""
    if doc is None:
        return None
    safe = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            safe[k] = str(v)
        elif isinstance(v, dict):
            safe[k] = _make_snapshot_safe(v)
        elif isinstance(v, list):
            safe[k] = [str(i) if isinstance(i, ObjectId) else i for i in v]
        elif isinstance(v, datetime):
            safe[k] = v.isoformat()
        else:
            safe[k] = v
    return safe


def _doc_to_audit(doc: dict) -> AuditRecordInDB:
    def _str(val) -> Optional[str]:
        if val is None:
            return None
        return str(val) if not isinstance(val, str) else val

    return AuditRecordInDB(
        id=str(doc["_id"]),
        prescription_id=_str(doc["prescription_id"]) or "system",
        created_by=_str(doc.get("created_by")) or "system",
        created_by_role=doc.get("created_by_role", "system"),
        type=doc.get("type", "manual"),
        flag_code=doc.get("flag_code", "generic"),
        issue=doc.get("issue", ""),
        severity=doc.get("severity", "low"),
        recommendation=doc.get("recommendation"),
        resolved=doc.get("resolved", False),
        resolved_by=_str(doc.get("resolved_by")),
        resolved_at=doc.get("resolved_at"),
        resolution_note=doc.get("resolution_note"),
        resolution_type=doc.get("resolution_type"),
        countersigned=doc.get("countersigned", False),
        countersigned_by=_str(doc.get("countersigned_by")),
        countersigned_at=doc.get("countersigned_at"),
        countersign_note=doc.get("countersign_note"),
        original_flag_id=_str(doc.get("original_flag_id")),
        esig_required=doc.get("esig_required"),
        esig_confirmed_by=_str(doc.get("esig_confirmed_by")),
        esig_confirmed_at=doc.get("esig_confirmed_at"),
        before_snapshot=doc.get("before_snapshot"),
        after_snapshot=doc.get("after_snapshot"),
        ip_address=doc.get("ip_address"),
        user_agent=doc.get("user_agent"),
        is_security_event=doc.get("is_security_event", False),
        security_event_type=doc.get("security_event_type"),
        reviewed_at=doc.get("reviewed_at"),
        reviewed_by=_str(doc.get("reviewed_by")),
        created_at=doc["created_at"],
        visit_id=_str(doc.get("visit_id")),
        department_id=_str(doc.get("department_id")),
        patient_id=_str(doc.get("patient_id")),
        drug_name=doc.get("drug_name"),
        dose=doc.get("dose"),
        patient_age=doc.get("patient_age"),
        patient_allergies_snapshot=doc.get("patient_allergies_snapshot", []),
        tat_pharmacy_min_at_flag=doc.get("tat_pharmacy_min_at_flag"),
        sla_threshold_min=doc.get("sla_threshold_min"),
        rx_number=doc.get("rx_number"),
        patient_name=doc.get("patient_name"),
    )


async def create_audit_record(
    db: AsyncDatabase,
    prescription_id: str,
    created_by: str,
    created_by_role: str,
    audit_type: str,
    issue: str,
    severity: str,
    recommendation: str,
    flag_code: str = "generic",
    before_snapshot: Optional[Dict[str, Any]] = None,
    after_snapshot: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    is_security_event: bool = False,
    security_event_type: Optional[str] = None,
    visit_id: Optional[str] = None,
    department_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    drug_name: Optional[str] = None,
    dose: Optional[str] = None,
    patient_age: Optional[int] = None,
    patient_allergies_snapshot: Optional[List[str]] = None,
    tat_pharmacy_min_at_flag: Optional[float] = None,
    sla_threshold_min: Optional[float] = None,
    esig_required: bool = False,
) -> AuditRecordInDB:
    now = datetime.now(timezone.utc)

    # HIGH and CRITICAL severity clinical flags require countersign before resolution
    high_severity_clinical_types = {AuditSeverity.high.value, AuditSeverity.critical.value}
    clinical_flag_codes = {
        "allergy_match", "drug_interaction", "controlled_sub",
        "high_dose", "extended_duration", "duplicate_rx",
    }
    requires_countersign = (
        severity in high_severity_clinical_types
        and flag_code in clinical_flag_codes
        and audit_type in ("automated", "manual")
    )

    doc = {
        "prescription_id": prescription_id,
        "visit_id": visit_id,
        "department_id": department_id,
        "patient_id": patient_id,
        "flag_code": flag_code,
        "drug_name": drug_name,
        "dose": dose,
        "patient_age": patient_age,
        "patient_allergies_snapshot": patient_allergies_snapshot or [],
        "tat_pharmacy_min_at_flag": tat_pharmacy_min_at_flag,
        "sla_threshold_min": sla_threshold_min,
        "created_by": created_by,
        "created_by_role": created_by_role,
        "type": audit_type,
        "issue": issue,
        "severity": severity,
        "recommendation": recommendation,
        "resolved": False,
        "resolved_by": None,
        "resolved_at": None,
        "resolution_note": None,
        "resolution_type": None,
        "countersigned": False,
        "countersigned_by": None,
        "countersigned_at": None,
        "countersign_note": None,
        "original_flag_id": None,
        "esig_required": requires_countersign or esig_required,
        "esig_confirmed_by": None,
        "esig_confirmed_at": None,
        "before_snapshot": _make_snapshot_safe(before_snapshot),
        "after_snapshot": _make_snapshot_safe(after_snapshot),
        "ip_address": ip_address,
        "user_agent": user_agent,
        "is_security_event": is_security_event,
        "security_event_type": security_event_type,
        "reviewed_at": None,
        "reviewed_by": None,
        "created_at": now,
    }
    result = await db.audit_records.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_audit(doc)


async def create_security_audit(
    db: AsyncDatabase,
    user_id: str,
    user_role: str,
    event_type: str,
    details: Dict[str, Any],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditRecordInDB:
    return await create_audit_record(
        db=db,
        prescription_id="system",
        created_by=user_id,
        created_by_role=user_role,
        audit_type="manual",
        issue=f"Security event: {event_type}",
        severity="medium",
        recommendation="Review if suspicious",
        flag_code="security",
        after_snapshot=_make_snapshot_safe(details),
        ip_address=ip_address,
        user_agent=user_agent,
        is_security_event=True,
        security_event_type=event_type,
    )


async def _enrich_audit_docs(db: AsyncDatabase, docs: List[dict]) -> List[dict]:
    """Attach rx_number and patient_name to audit docs in-place."""
    rx_ids = list({d["prescription_id"] for d in docs if d.get("prescription_id") and d["prescription_id"] != "system"})
    rx_map: Dict[str, str] = {}
    patient_map: Dict[str, str] = {}

    if rx_ids:
        valid_rx_ids = [ObjectId(rid) for rid in rx_ids if ObjectId.is_valid(rid)]
        if valid_rx_ids:
            async for rdoc in db.prescriptions.find(
                {"_id": {"$in": valid_rx_ids}},
                {"rx_number": 1, "patient_id": 1}
            ):
                rx_str = str(rdoc["_id"])
                rx_map[rx_str] = rdoc.get("rx_number") or ""
                pid = str(rdoc.get("patient_id", ""))
                if pid:
                    patient_map[rx_str] = pid

    # batch fetch patient names
    pid_set = list(set(patient_map.values()))
    valid_pids = [ObjectId(pid) for pid in pid_set if ObjectId.is_valid(pid)]
    pname_map: Dict[str, str] = {}
    if valid_pids:
        async for pdoc in db.patients.find({"_id": {"$in": valid_pids}}, {"first_name": 1, "last_name": 1}):
            name = f"{pdoc.get('first_name', '')} {pdoc.get('last_name', '')}".strip()
            pname_map[str(pdoc["_id"])] = name or ""

    for doc in docs:
        rx_str = str(doc.get("prescription_id", ""))
        doc["rx_number"] = rx_map.get(rx_str, "")
        pid = patient_map.get(rx_str, "")
        doc["patient_name"] = pname_map.get(pid, "") if pid else ""

    return docs


async def get_audit_records(
    db: AsyncDatabase,
    prescription_id: Optional[str] = None,
    resolved: Optional[bool] = None,
    skip: int = 0,
    limit: int = 20,
    flag_type: Optional[str] = None,
    severity: Optional[str] = None,
) -> List[AuditRecordInDB]:
    query: dict = {}
    if prescription_id is not None:
        query["prescription_id"] = prescription_id
    if resolved is not None:
        query["resolved"] = resolved
    if flag_type is not None:
        query["flag_code"] = flag_type
    if severity is not None:
        query["severity"] = severity
    cursor = db.audit_records.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    docs = await _enrich_audit_docs(db, docs)
    return [_doc_to_audit(doc) for doc in docs]


async def get_unresolved_audit_records(
    db: AsyncDatabase,
    skip: int = 0,
    limit: int = 50,
) -> List[AuditRecordInDB]:
    """Return only original (non-resolution) unresolved flag records."""
    query = {
        "resolved": False,
        "type": {"$nin": ["resolution", "countersign", "status_change"]},
    }
    cursor = db.audit_records.find(query).sort([("severity", -1), ("created_at", 1)]).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    docs = await _enrich_audit_docs(db, docs)
    return [_doc_to_audit(doc) for doc in docs]


async def get_audit_log(
    db: AsyncDatabase,
    skip: int = 0,
    limit: int = 50,
    prescription_id: Optional[str] = None,
    flag_type: Optional[str] = None,
    severity: Optional[str] = None,
    resolved: Optional[bool] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[AuditRecordInDB]:
    """Full immutable audit log with all record types."""
    query: dict = {}
    if prescription_id:
        query["prescription_id"] = prescription_id
    if flag_type:
        query["flag_code"] = flag_type
    if severity:
        query["severity"] = severity
    if resolved is not None:
        query["resolved"] = resolved
    if date_from or date_to:
        date_q: dict = {}
        if date_from:
            date_q["$gte"] = date_from
        if date_to:
            date_q["$lte"] = date_to
        query["created_at"] = date_q
    cursor = db.audit_records.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    docs = await _enrich_audit_docs(db, docs)
    return [_doc_to_audit(doc) for doc in docs]


async def get_audit_by_id(
    db: AsyncDatabase, audit_id: str
) -> Optional[AuditRecordInDB]:
    try:
        obj_id = ObjectId(audit_id)
    except Exception:
        return None
    doc = await db.audit_records.find_one({"_id": obj_id})
    if not doc:
        return None
    return _doc_to_audit(doc)


async def countersign_audit(
    db: AsyncDatabase,
    flag_id: str,
    countersigner_id: str,
    countersigner_role: str,
    note: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditRecordInDB:
    """
    Create an immutable countersign record for a flag.

    Rules:
    - Flag must exist and be unresolved.
    - Countersigner must not be the same user who created the flag.
    - Only one countersign record may exist per flag.
    """
    from app.ws.manager import manager

    try:
        obj_id = ObjectId(flag_id)
    except Exception:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Invalid flag ID",
            headers={"X-Error-Code": "INVALID_FLAG_ID"},
        )

    flag_doc = await db.audit_records.find_one({"_id": obj_id})
    if not flag_doc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FLAG_NOT_FOUND",
                "message": "The specified flag does not exist.",
                "details": {"flag_id": flag_id},
            },
        )

    if flag_doc.get("resolved", False):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "FLAG_ALREADY_RESOLVED",
                "message": "This flag is already resolved and cannot be countersigned.",
                "details": {"flag_id": flag_id},
            },
        )

    if str(flag_doc.get("created_by")) == countersigner_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "COUNTERSIGN_SAME_USER",
                "message": "The countersigning auditor cannot be the same user who created the flag.",
                "details": {"flag_id": flag_id, "created_by": str(flag_doc.get("created_by"))},
            },
        )

    existing = await db.audit_records.find_one({
        "type": "countersign",
        "original_flag_id": flag_id,
    })
    if existing:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ALREADY_COUNTERSIGNED",
                "message": "This flag has already been countersigned.",
                "details": {"flag_id": flag_id, "countersigned_by": str(existing.get("created_by"))},
            },
        )

    now = datetime.now(timezone.utc)
    countersign_doc = {
        "prescription_id": flag_doc.get("prescription_id"),
        "visit_id": flag_doc.get("visit_id"),
        "department_id": flag_doc.get("department_id"),
        "patient_id": flag_doc.get("patient_id"),
        "flag_code": flag_doc.get("flag_code", "generic"),
        "drug_name": flag_doc.get("drug_name"),
        "dose": flag_doc.get("dose"),
        "patient_age": flag_doc.get("patient_age"),
        "patient_allergies_snapshot": flag_doc.get("patient_allergies_snapshot", []),
        "tat_pharmacy_min_at_flag": flag_doc.get("tat_pharmacy_min_at_flag"),
        "sla_threshold_min": flag_doc.get("sla_threshold_min"),
        "created_by": countersigner_id,
        "created_by_role": countersigner_role,
        "type": "countersign",
        "issue": f"Countersign: {flag_doc.get('issue', '')}",
        "severity": flag_doc.get("severity", "low"),
        "recommendation": note,
        "resolved": False,
        "resolved_by": None,
        "resolved_at": None,
        "resolution_note": None,
        "resolution_type": None,
        "countersigned": True,
        "countersigned_by": countersigner_id,
        "countersigned_at": now,
        "countersign_note": note,
        "original_flag_id": flag_id,
        "esig_required": False,
        "esig_confirmed_by": None,
        "esig_confirmed_at": None,
        "before_snapshot": _make_snapshot_safe(flag_doc),
        "after_snapshot": None,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "is_security_event": False,
        "security_event_type": None,
        "reviewed_at": None,
        "reviewed_by": None,
        "created_at": now,
    }

    result = await db.audit_records.insert_one(countersign_doc)
    countersign_doc["_id"] = result.inserted_id

    prescription_id = flag_doc.get("prescription_id", "")
    event = {
        "event_type": "audit.countersigned",
        "entity_id": prescription_id,
        "entity_type": "prescription",
        "message": f"Flag countersigned for prescription {prescription_id}",
        "data": {
            "flag_id": flag_id,
            "prescription_id": prescription_id,
            "countersigned_by": countersigner_id,
        },
        "timestamp": now.isoformat(),
        "triggered_by_role": countersigner_role,
    }
    await manager.broadcast_multi(["auditor", "admin"], event)

    return _doc_to_audit(countersign_doc)


async def resolve_audit_record(
    prescription_id: str,
    resolution_note: str,
    resolution_type: str,
    auditor,
    db: AsyncDatabase,
) -> List[AuditRecordInDB]:
    """
    Create resolution records for all open flags on a prescription.

    Immutability contract: original flag records are never modified.
    A resolution record is appended. The resolved state is a projection
    derived from the existence of a resolution record for a given flag.

    Blocking rule: HIGH or CRITICAL severity flags that have esig_required=True
    must have a countersign record before resolution is permitted.
    """
    from app.ws.manager import manager

    now = datetime.now(timezone.utc)

    unresolved_cursor = db.audit_records.find({
        "prescription_id": prescription_id,
        "resolved": False,
        "type": {"$nin": ["resolution", "countersign", "status_change"]},
    })
    unresolved_records = await unresolved_cursor.to_list(length=None)

    if not unresolved_records:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "NO_OPEN_FLAGS",
                "message": "There are no open flags to resolve for this prescription.",
                "details": {"prescription_id": prescription_id},
            },
        )

    # Check each high-severity flag for required countersign
    for record in unresolved_records:
        if record.get("esig_required", False):
            flag_id = str(record["_id"])
            existing_countersign = await db.audit_records.find_one({
                "type": "countersign",
                "original_flag_id": flag_id,
            })
            if not existing_countersign:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "AUDIT_RESOLUTION_BLOCKED",
                        "message": "High severity flags require countersign before resolution.",
                        "details": {
                            "flag_id": flag_id,
                            "severity": record.get("severity"),
                            "required_action": "countersign",
                        },
                    },
                )

    resolution_records = []

    for original in unresolved_records:
        original_flag_id = str(original["_id"])

        resolution_doc = {
            "prescription_id": prescription_id,
            "visit_id": original.get("visit_id"),
            "department_id": original.get("department_id"),
            "patient_id": original.get("patient_id"),
            "flag_code": original.get("flag_code", "generic"),
            "drug_name": original.get("drug_name"),
            "dose": original.get("dose"),
            "patient_age": original.get("patient_age"),
            "patient_allergies_snapshot": original.get("patient_allergies_snapshot", []),
            "tat_pharmacy_min_at_flag": original.get("tat_pharmacy_min_at_flag"),
            "sla_threshold_min": original.get("sla_threshold_min"),
            "created_by": str(auditor.id),
            "created_by_role": auditor.role,
            "type": "resolution",
            "issue": original["issue"],
            "severity": original["severity"],
            "recommendation": resolution_note,
            "resolved": True,
            "resolved_by": str(auditor.id),
            "resolved_at": now,
            "resolution_note": resolution_note,
            "resolution_type": resolution_type,
            "countersigned": False,
            "countersigned_by": None,
            "countersigned_at": None,
            "countersign_note": None,
            "original_flag_id": original_flag_id,
            "esig_required": original.get("esig_required", False),
            "esig_confirmed_by": str(auditor.id) if original.get("esig_required") else None,
            "esig_confirmed_at": now if original.get("esig_required") else None,
            "before_snapshot": original.get("before_snapshot"),
            "after_snapshot": original.get("after_snapshot"),
            "ip_address": original.get("ip_address"),
            "user_agent": original.get("user_agent"),
            "is_security_event": original.get("is_security_event", False),
            "security_event_type": original.get("security_event_type"),
            "reviewed_at": None,
            "reviewed_by": None,
            "created_at": now,
        }

        result = await db.audit_records.insert_one(resolution_doc)
        resolution_doc["_id"] = result.inserted_id
        resolution_records.append(_doc_to_audit(resolution_doc))

        # Mark original as resolved in place - projection update only.
        # This is a deliberate projection flag: original record content is unchanged,
        # only the resolved boolean is set so queries for open flags remain correct.
        # The full resolution detail is in the resolution record linked via original_flag_id.
        await db.audit_records.update_one(
            {"_id": original["_id"]},
            {"$set": {"resolved": True}},
        )

    # Fetch doctor_id from the prescription so the broadcast targets the correct room
    rx_doc = await db.prescriptions.find_one({"_id": ObjectId(prescription_id)}) if _is_valid_object_id(prescription_id) else None
    doctor_id_val = str(rx_doc.get("doctor_id")) if rx_doc else None

    event = {
        "event_type": "audit.flag_resolved",
        "entity_id": prescription_id,
        "entity_type": "prescription",
        "message": f"Audit flags resolved for prescription {prescription_id}",
        "data": {
            "prescription_id": prescription_id,
            "resolved_count": len(resolution_records),
            "resolution_type": resolution_type,
        },
        "timestamp": now.isoformat(),
        "triggered_by_role": auditor.role,
    }

    rooms = ["auditor", "admin"]
    if doctor_id_val:
        rooms.append(f"doctor:{doctor_id_val}")
    await manager.broadcast_multi(rooms, event)

    return resolution_records


def _is_valid_object_id(value: str) -> bool:
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


async def get_security_events_for_day(
    db: AsyncDatabase,
    review_date: date,
    skip: int = 0,
    limit: int = 100,
) -> List[AuditRecordInDB]:
    start = datetime.combine(review_date, datetime.min.time())
    end = datetime.combine(review_date, datetime.max.time())
    cursor = db.audit_records.find({
        "is_security_event": True,
        "created_at": {"$gte": start, "$lte": end},
        "reviewed_at": None,
    }).skip(skip).limit(limit).sort("created_at", -1)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_audit(doc) for doc in docs]


async def mark_events_reviewed(
    db: AsyncDatabase,
    event_ids: List[str],
    reviewed_by: str,
) -> int:
    obj_ids = []
    for eid in event_ids:
        try:
            obj_ids.append(ObjectId(eid))
        except Exception:
            continue
    if not obj_ids:
        return 0
    now = datetime.now(timezone.utc)
    result = await db.audit_records.update_many(
        {"_id": {"$in": obj_ids}, "reviewed_at": None},
        {"$set": {"reviewed_at": now, "reviewed_by": reviewed_by}}
    )
    return result.modified_count


async def escalate_overdue_flags(db: AsyncDatabase):
    from app.ws.manager import manager

    now = datetime.now(timezone.utc)
    two_hours_ago = now - timedelta(hours=2)

    overdue_cursor = db.audit_records.find({
        "resolved": False,
        "severity": "high",
        "type": {"$nin": ["resolution", "countersign", "status_change"]},
        "created_at": {"$lt": two_hours_ago}
    })
    overdue_records = await overdue_cursor.to_list(length=None)

    escalated_count = 0

    for overdue in overdue_records:
        flag_id = str(overdue["_id"])
        existing_escalation = await db.audit_records.find_one({
            "type": "sla_warning",
            "original_flag_id": flag_id,
        })
        if existing_escalation:
            continue

        escalation_doc = {
            "prescription_id": overdue["prescription_id"],
            "visit_id": overdue.get("visit_id"),
            "department_id": overdue.get("department_id"),
            "patient_id": overdue.get("patient_id"),
            "flag_code": overdue.get("flag_code", "generic"),
            "drug_name": overdue.get("drug_name"),
            "dose": overdue.get("dose"),
            "patient_age": overdue.get("patient_age"),
            "patient_allergies_snapshot": overdue.get("patient_allergies_snapshot", []),
            "tat_pharmacy_min_at_flag": overdue.get("tat_pharmacy_min_at_flag"),
            "sla_threshold_min": overdue.get("sla_threshold_min"),
            "created_by": "system",
            "created_by_role": "system",
            "type": "sla_warning",
            "issue": f"ESCALATED: {overdue['issue']} - Unresolved for >2 hours",
            "severity": "critical",
            "recommendation": "URGENT: Immediate auditor review required",
            "resolved": False,
            "resolved_by": None,
            "resolved_at": None,
            "resolution_note": None,
            "resolution_type": None,
            "countersigned": False,
            "countersigned_by": None,
            "countersigned_at": None,
            "countersign_note": None,
            "original_flag_id": flag_id,
            "esig_required": False,
            "esig_confirmed_by": None,
            "esig_confirmed_at": None,
            "before_snapshot": None,
            "after_snapshot": None,
            "ip_address": None,
            "user_agent": None,
            "is_security_event": False,
            "security_event_type": None,
            "reviewed_at": None,
            "reviewed_by": None,
            "created_at": now,
        }

        await db.audit_records.insert_one(escalation_doc)
        escalated_count += 1

        event = {
            "event_type": "audit.flag_escalated",
            "entity_id": overdue["prescription_id"],
            "entity_type": "audit",
            "message": "High-severity flag escalated to critical",
            "data": {
                "prescription_id": overdue["prescription_id"],
                "flag_code": overdue.get("flag_code", "generic"),
                "original_issue": overdue["issue"],
            },
            "timestamp": now.isoformat(),
            "triggered_by_role": "system",
        }
        await manager.broadcast_multi(["auditor", "admin"], event)

    return escalated_count


async def get_unresolved_for_prescription(
    prescription_id: str, db: AsyncDatabase
) -> List[AuditRecordInDB]:
    cursor = db.audit_records.find({
        "prescription_id": prescription_id,
        "resolved": False,
        "type": {"$nin": ["resolution", "countersign", "status_change"]},
    })
    docs = await cursor.to_list(length=None)
    return [_doc_to_audit(doc) for doc in docs]
