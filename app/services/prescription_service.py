import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from app.models.prescription import (
    PrescriptionCreate,
    PrescriptionInDB,
    PrescriptionStatus,
    MedicationItem,
    Priority,
    OrderSource,
)
from fastapi import HTTPException, status as http_status
from app.services import audit_service
from app.ws.manager import manager


_DEFAULT_SLA_THRESHOLDS: Dict[str, float] = {
    "stat": 15.0,
    "urgent": 30.0,
    "routine": 60.0,
    "discharge": 45.0,
    "nicu": 20.0,
    "chemo": 120.0,
}

_SLA_WARNING_FRACTION = 0.75


# Coerce a datetime to timezone-aware UTC.
def _ensure_aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# Stringify an id reference, passing through None.
def _normalize_ref(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value) if not isinstance(value, str) else value


# Reject prescribing until triage and consultation are done.
async def _ensure_visit_ready_for_prescription(
    db: AsyncDatabase,
    prescription: PrescriptionCreate,
) -> None:
    if not prescription.visit_id:
        return
    if not ObjectId.is_valid(prescription.visit_id):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select a valid visit before creating a prescription.",
        )

    visit_doc = await db.visits.find_one(
        {"_id": ObjectId(prescription.visit_id)},
        {
            "patient_id": 1,
            "triaged_at": 1,
            "consultation_started_at": 1,
        },
    )
    if not visit_doc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="The selected visit could not be found.",
        )

    visit_patient_id = _normalize_ref(visit_doc.get("patient_id"))
    if visit_patient_id and visit_patient_id != prescription.patient_id:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected visit does not belong to the selected patient.",
        )

    if not visit_doc.get("triaged_at"):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Complete triage before creating a prescription for this visit.",
        )

    if not visit_doc.get("consultation_started_at"):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Start the consultation before creating a prescription for this visit.",
        )


# Convert a prescription document to a model.
def _doc_to_prescription(doc: dict) -> PrescriptionInDB:
    medications = []
    for m in doc.get("medications", []):
        if isinstance(m, dict):
            medications.append(MedicationItem(**m))
        else:
            medications.append(m)

    # Stringify an ObjectId, passing through None.
    def _str(val) -> Optional[str]:
        return _normalize_ref(val)

    priority_val = doc.get("priority")
    if priority_val is None:
        priority = Priority.routine
    elif isinstance(priority_val, str):
        try:
            priority = Priority(priority_val)
        except ValueError:
            priority = Priority.routine
    else:
        priority = priority_val

    order_source_val = doc.get("order_source")
    if order_source_val is None:
        order_source = OrderSource.opd
    elif isinstance(order_source_val, str):
        try:
            order_source = OrderSource(order_source_val)
        except ValueError:
            order_source = OrderSource.opd
    else:
        order_source = order_source_val

    return PrescriptionInDB(
        id=str(doc["_id"]),
        patient_id=_str(doc.get("patient_id")) or "",
        doctor_id=_str(doc.get("doctor_id")) or "",
        medications=medications,
        status=doc.get("status", "submitted"),
        priority=priority,
        order_source=order_source,
        ordered_at=doc.get("ordered_at"),
        submitted_at=doc.get("submitted_at"),
        verified_at=doc.get("verified_at"),
        dispensed_at=doc.get("dispensed_at"),
        administered_at=doc.get("administered_at"),
        flags=doc.get("flags", []),
        notes=doc.get("notes"),
        pharmacist_comment=doc.get("pharmacist_comment"),
        created_at=doc.get("created_at") or doc.get("ordered_at"),
        updated_at=doc.get("updated_at") or doc.get("created_at") or doc.get("ordered_at"),
        tat_order_to_submit_min=doc.get("tat_order_to_submit_min"),
        tat_submit_to_verify_min=doc.get("tat_submit_to_verify_min"),
        tat_flag_hold_min=doc.get("tat_flag_hold_min"),
        tat_verify_to_dispense_min=doc.get("tat_verify_to_dispense_min"),
        tat_dispense_to_admin_min=doc.get("tat_dispense_to_admin_min"),
        tat_pharmacy_min=doc.get("tat_pharmacy_min"),
        tat_total_min=doc.get("tat_total_min"),
        sla_threshold_min=doc.get("sla_threshold_min"),
        sla_breached=doc.get("sla_breached", False),
        sla_breach_duration_min=doc.get("sla_breach_duration_min"),
        tat_breached_at=doc.get("tat_breached_at"),
        rx_number=doc.get("rx_number"),
        visit_id=_str(doc.get("visit_id")),
        department_id=_str(doc.get("department_id")),
        ward_id=_str(doc.get("ward_id")),
        dispensed_by_id=_str(doc.get("dispensed_by_id")),
        dispensed_by_name=doc.get("dispensed_by_name"),
        administered_by_id=_str(doc.get("administered_by_id")),
        administered_by_name=doc.get("administered_by_name"),
        administered_dose=doc.get("administered_dose"),
        administered_route=doc.get("administered_route"),
        administration_notes=doc.get("administration_notes"),
        receipt_number=doc.get("receipt_number"),
        auditor_id=_str(doc.get("auditor_id")),
        auditor_name=doc.get("auditor_name"),
        auditor_approved_at=doc.get("auditor_approved_at"),
        returned_at=doc.get("returned_at"),
        return_reason=doc.get("return_reason"),
        resubmitted_at=doc.get("resubmitted_at"),
        amendment_count=doc.get("amendment_count", 0),
        revisions=doc.get("revisions", []),
        weight_kg=doc.get("weight_kg"),
        patient_name=doc.get("patient_name"),
        doctor_name=doc.get("doctor_name"),
        department=doc.get("department"),
        ward_location=doc.get("ward_location"),
    )


# Attach patient_name, doctor_name, and actor names to prescription docs in-place.
async def _enrich_docs_with_names(db: AsyncDatabase, docs: List[dict]) -> List[dict]:
    patient_ids = list({d["patient_id"] for d in docs if d.get("patient_id")})
    user_id_set: set = set()
    for d in docs:
        for field in ("doctor_id", "dispensed_by_id", "administered_by_id", "auditor_id"):
            if d.get(field):
                user_id_set.add(str(d[field]))

    patient_map: Dict[str, str] = {}
    if patient_ids:
        valid_pids = [ObjectId(pid) for pid in patient_ids if ObjectId.is_valid(pid)]
        if valid_pids:
            cursor = db.patients.find({"_id": {"$in": valid_pids}}, {"first_name": 1, "last_name": 1})
            async for pdoc in cursor:
                name = f"{pdoc.get('first_name', '')} {pdoc.get('last_name', '')}".strip()
                patient_map[str(pdoc["_id"])] = name or ""

    user_map: Dict[str, str] = {}
    if user_id_set:
        valid_uids = [ObjectId(uid) for uid in user_id_set if ObjectId.is_valid(uid)]
        if valid_uids:
            cursor = db.users.find({"_id": {"$in": valid_uids}}, {"full_name": 1, "username": 1})
            async for udoc in cursor:
                user_map[str(udoc["_id"])] = udoc.get("full_name") or udoc.get("username") or ""

    # Resolve department and ward names from each prescription's linked visit.
    visit_ids = list({str(d["visit_id"]) for d in docs if d.get("visit_id")})
    visit_map: Dict[str, dict] = {}
    dept_ids: set = set()
    if visit_ids:
        valid_vids = [ObjectId(vid) for vid in visit_ids if ObjectId.is_valid(vid)]
        if valid_vids:
            async for vdoc in db.visits.find(
                {"_id": {"$in": valid_vids}},
                {"department_id": 1, "bed_label": 1, "ward_name": 1},
            ):
                visit_map[str(vdoc["_id"])] = vdoc
                if vdoc.get("department_id"):
                    dept_ids.add(str(vdoc["department_id"]))

    dept_map: Dict[str, str] = {}
    if dept_ids:
        valid_dids = [ObjectId(did) for did in dept_ids if ObjectId.is_valid(did)]
        if valid_dids:
            async for ddoc in db.departments.find({"_id": {"$in": valid_dids}}, {"name": 1}):
                dept_map[str(ddoc["_id"])] = ddoc.get("name") or ""

    for doc in docs:
        doc["patient_name"] = patient_map.get(str(doc.get("patient_id")), "")
        doc["doctor_name"] = user_map.get(str(doc.get("doctor_id")), "")
        vdoc = visit_map.get(str(doc.get("visit_id"))) if doc.get("visit_id") else None
        if vdoc:
            doc["department"] = dept_map.get(str(vdoc.get("department_id")), "") or None
            doc["ward_location"] = vdoc.get("ward_name") or vdoc.get("bed_label") or None
        if doc.get("dispensed_by_id") and not doc.get("dispensed_by_name"):
            doc["dispensed_by_name"] = user_map.get(str(doc["dispensed_by_id"]), "")
        if doc.get("administered_by_id") and not doc.get("administered_by_name"):
            doc["administered_by_name"] = user_map.get(str(doc["administered_by_id"]), "")
        if doc.get("auditor_id") and not doc.get("auditor_name"):
            doc["auditor_name"] = user_map.get(str(doc["auditor_id"]), "")

    return docs


# Look up the SLA threshold for a given priority from the config collection.
async def _get_sla_threshold(db: AsyncDatabase, priority: str) -> float:
    doc = await db.sla_config.find_one({"priority": priority})
    if doc and doc.get("threshold_min") is not None:
        return float(doc["threshold_min"])
    return _DEFAULT_SLA_THRESHOLDS.get(priority, 60.0)


# Generate a unique, human-readable prescription number (e.g. RX-2026-0042).
async def generate_rx_number(db: AsyncDatabase) -> str:
    year = datetime.now(timezone.utc).strftime("%Y")
    counter_id = f"rx_{year}"

    result = await db.counters.find_one_and_update(
        {"_id": counter_id},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = result.get("seq", 1)

    prefix = f"RX-{year}-"
    if await db.prescriptions.find_one({"rx_number": f"{prefix}{seq:04d}"}, {"_id": 1}):
        count = await db.prescriptions.count_documents({"rx_number": {"$regex": f"^{prefix}"}})
        seq = count + 1
        await db.counters.update_one(
            {"_id": counter_id},
            {"$set": {"seq": seq}},
            upsert=True,
        )

    return f"{prefix}{seq:04d}"


# Generate a unique dispensing receipt number (e.g. RCP-2026-0042).
async def generate_receipt_number(db: AsyncDatabase) -> str:
    year = datetime.now(timezone.utc).strftime("%Y")
    counter_id = f"receipt_{year}"

    result = await db.counters.find_one_and_update(
        {"_id": counter_id},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = result.get("seq", 1)

    prefix = f"RCP-{year}-"
    if await db.prescriptions.find_one({"receipt_number": f"{prefix}{seq:04d}"}, {"_id": 1}):
        count = await db.prescriptions.count_documents({"receipt_number": {"$regex": f"^{prefix}"}})
        seq = count + 1
        await db.counters.update_one(
            {"_id": counter_id},
            {"$set": {"seq": seq}},
            upsert=True,
        )

    return f"{prefix}{seq:04d}"


# Create a prescription and link it to its visit.
async def create_prescription(
    db: AsyncDatabase,
    prescription: PrescriptionCreate,
    doctor_id: str,
) -> PrescriptionInDB:
    now = datetime.now(timezone.utc)
    await _ensure_visit_ready_for_prescription(db, prescription)
    priority_str = prescription.priority.value if hasattr(prescription.priority, "value") else str(prescription.priority)
    sla_threshold = await _get_sla_threshold(db, priority_str)
    rx_number = await generate_rx_number(db)

    doc = {
        "rx_number": rx_number,
        "patient_id": prescription.patient_id,
        "doctor_id": doctor_id,
        "medications": [m.model_dump() for m in prescription.medications],
        "priority": priority_str,
        "order_source": prescription.order_source.value if hasattr(prescription.order_source, "value") else str(prescription.order_source),
        "status": PrescriptionStatus.submitted.value,
        "ordered_at": now,
        "submitted_at": now,
        "verified_at": None,
        "dispensed_at": None,
        "administered_at": None,
        "flags": [],
        "notes": prescription.notes,
        "pharmacist_comment": None,
        "visit_id": prescription.visit_id,
        "department_id": prescription.department_id,
        "sla_threshold_min": sla_threshold,
        "sla_breached": False,
        "sla_breach_duration_min": None,
        "tat_breached_at": None,
        "dispensed_by_id": None,
        "administered_by_id": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.prescriptions.insert_one(doc)
    doc["_id"] = result.inserted_id

    if prescription.visit_id and ObjectId.is_valid(prescription.visit_id):
        await db.visits.update_one(
            {"_id": ObjectId(prescription.visit_id)},
            {"$addToSet": {"prescription_ids": str(result.inserted_id)}},
        )
        # Inherit the visit's department/ward when the order didn't specify one.
        if not prescription.department_id:
            vdoc = await db.visits.find_one(
                {"_id": ObjectId(prescription.visit_id)},
                {"department_id": 1, "bed_id": 1},
            )
            inherited: dict = {}
            if vdoc and vdoc.get("department_id"):
                inherited["department_id"] = str(vdoc["department_id"])
            if vdoc and vdoc.get("bed_id"):
                inherited["ward_id"] = str(vdoc["bed_id"])
            if inherited:
                await db.prescriptions.update_one({"_id": result.inserted_id}, {"$set": inherited})
                doc.update(inherited)

    event = {
        "event_type": "prescription.created",
        "entity_id": str(result.inserted_id),
        "entity_type": "prescription",
        "message": f"New {priority_str} prescription submitted",
        "data": {
            "priority": priority_str,
            "patient_id": prescription.patient_id,
            "rx_number": rx_number,
            "sla_threshold_min": sla_threshold,
        },
        "timestamp": now.isoformat(),
        "triggered_by_role": "doctor",
    }
    # New scripts go to the auditor for review before pharmacy.
    await manager.broadcast_multi(["auditor", "admin"], event)

    return _doc_to_prescription(doc)


# List prescriptions with filters, names attached.
async def get_prescriptions(
    db: AsyncDatabase,
    status: Optional[str] = None,
    patient_id: Optional[str] = None,
    doctor_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> List[PrescriptionInDB]:
    query: dict = {}
    if status:
        query["status"] = status
    if patient_id:
        query["patient_id"] = patient_id
    if doctor_id:
        query["doctor_id"] = doctor_id

    priority_order = ["stat", "nicu", "urgent", "discharge", "routine", "chemo"]
    cursor = db.prescriptions.find(query).sort([
        ("submitted_at", 1),
    ]).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)

    docs = await _enrich_docs_with_names(db, docs)
    results = [_doc_to_prescription(doc) for doc in docs]

    priority_rank = {p: i for i, p in enumerate(priority_order)}
    results.sort(key=lambda p: (
        priority_rank.get(p.priority.value if hasattr(p.priority, "value") else str(p.priority), 99),
        _ensure_aware(p.submitted_at) or datetime.now(timezone.utc),
    ))

    return results


# Work queue for a role: auditors review, pharmacists dispense verified.
async def get_prescription_queue(
    db: AsyncDatabase,
    skip: int = 0,
    limit: int = 50,
    role: Optional[str] = None,
) -> List[PrescriptionInDB]:
    statuses = ["verified"] if role == "pharmacist" else ["submitted", "flagged"]
    query = {"status": {"$in": statuses}}
    docs_cursor = db.prescriptions.find(query).skip(skip).limit(limit)
    docs = await docs_cursor.to_list(length=limit)
    docs = await _enrich_docs_with_names(db, docs)
    results = [_doc_to_prescription(doc) for doc in docs]

    priority_rank = {p: i for i, p in enumerate(["stat", "nicu", "urgent", "discharge", "routine", "chemo"])}
    results.sort(key=lambda p: (
        priority_rank.get(p.priority.value if hasattr(p.priority, "value") else str(p.priority), 99),
        _ensure_aware(p.submitted_at) or datetime.now(timezone.utc),
    ))
    return results


# Prescriptions a given pharmacist has dispensed, newest first (for reprinting receipts).
async def get_dispensed_by(
    db: AsyncDatabase,
    pharmacist_id: str,
    skip: int = 0,
    limit: int = 50,
) -> List[PrescriptionInDB]:
    query = {"dispensed_by_id": pharmacist_id, "dispensed_at": {"$ne": None}}
    docs_cursor = db.prescriptions.find(query).sort([("dispensed_at", -1)]).skip(skip).limit(limit)
    docs = await docs_cursor.to_list(length=limit)
    docs = await _enrich_docs_with_names(db, docs)
    return [_doc_to_prescription(doc) for doc in docs]


# Fetch one prescription by ID.
async def get_prescription_by_id(
    db: AsyncDatabase, prescription_id: str
) -> Optional[PrescriptionInDB]:
    try:
        obj_id = ObjectId(prescription_id)
    except Exception:
        return None
    doc = await db.prescriptions.find_one({"_id": obj_id})
    if not doc:
        return None
    docs = await _enrich_docs_with_names(db, [doc])
    return _doc_to_prescription(docs[0])


# Return all audit records for a prescription, sorted oldest first.
async def get_prescription_history(
    db: AsyncDatabase, prescription_id: str
) -> List[dict]:
    cursor = db.audit_records.find(
        {"prescription_id": prescription_id}
    ).sort("created_at", 1)
    docs = await cursor.to_list(length=None)
    history = []
    for doc in docs:
        history.append({
            "id": str(doc["_id"]),
            "type": doc.get("type", "unknown"),
            "issue": doc.get("issue", ""),
            "severity": doc.get("severity", "low"),
            "flag_code": doc.get("flag_code", "generic"),
            "created_by": str(doc.get("created_by", "")),
            "created_by_role": doc.get("created_by_role", ""),
            "resolved": doc.get("resolved", False),
            "original_flag_id": str(doc["original_flag_id"]) if doc.get("original_flag_id") else None,
            "created_at": doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", "")),
        })
    return history


PERMITTED_TRANSITIONS = {
    "draft": {"submitted": ["doctor", "surgeon", "anaesthetist", "midwife"]},
    "submitted": {
        "verified": ["auditor"],
        "pending_amendment": ["auditor"],
        "flagged": ["auditor"],
    },
    "pending_amendment": {"submitted": ["doctor", "surgeon", "anaesthetist", "midwife"]},
    "flagged": {
        "verified": ["auditor"],
        "pending_amendment": ["auditor"],
    },
    "verified": {"dispensed": ["pharmacist"]},
    "dispensed": {"administered": ["nurse"]},
}


# Move a prescription to its next state and record TAT.
async def advance_status(
    db: AsyncDatabase,
    prescription_id: str,
    new_status: str,
    user_id: str,
    role: str,
    update_data: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Optional[PrescriptionInDB]:
    if update_data is None:
        update_data = {}

    try:
        obj_id = ObjectId(prescription_id)
    except Exception:
        return None

    old_doc = await db.prescriptions.find_one({"_id": obj_id})
    if not old_doc:
        return None

    current_status = old_doc["status"]

    # Idempotent: a repeat action (e.g. double-click) on an already-current status is a no-op success.
    if current_status == new_status:
        return _doc_to_prescription(old_doc)

    now = datetime.now(timezone.utc)
    set_fields: dict = {"status": new_status, "updated_at": now}

    if update_data.get("notes") is not None:
        set_fields["notes"] = update_data["notes"]
    if update_data.get("pharmacist_comment") is not None:
        set_fields["pharmacist_comment"] = update_data["pharmacist_comment"]
    if update_data.get("return_reason") is not None:
        set_fields["return_reason"] = update_data["return_reason"]
    if update_data.get("administered_dose") is not None:
        set_fields["administered_dose"] = update_data["administered_dose"]
    if update_data.get("administered_route") is not None:
        set_fields["administered_route"] = update_data["administered_route"]
    if update_data.get("administration_notes") is not None:
        set_fields["administration_notes"] = update_data["administration_notes"]
    if update_data.get("receipt_number"):
        set_fields["receipt_number"] = update_data["receipt_number"].strip()

    if role == "admin":
        # Admin observes; the only state change it may perform is archiving, as clinical transitions belong to clinical roles.
        if new_status != "archived":
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ADMIN_CLINICAL_FORBIDDEN",
                    "message": "Admin cannot perform clinical prescription actions; only the responsible clinical role can.",
                    "details": {"from": current_status, "to": new_status},
                },
            )
    else:
        if new_status == "archived":
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ARCHIVE_FORBIDDEN",
                    "message": "Only admin can archive prescriptions.",
                    "details": {},
                },
            )
        allowed_roles = PERMITTED_TRANSITIONS.get(current_status, {}).get(new_status, [])
        if not allowed_roles:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_STATUS_TRANSITION",
                    "message": f"Cannot transition from {current_status} to {new_status}.",
                    "details": {"from": current_status, "to": new_status},
                },
            )
        if role not in allowed_roles:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "TRANSITION_ROLE_FORBIDDEN",
                    "message": f"Role {role} cannot transition from {current_status} to {new_status}.",
                    "details": {"role": role, "from": current_status, "to": new_status},
                },
            )

    if new_status == "verified":
        # Only genuine clinical flags block verification; SLA breach/warning records are timing alerts, not blockers.
        unresolved_count = await db.audit_records.count_documents({
            "prescription_id": prescription_id,
            "resolved": False,
            "type": {"$nin": ["resolution", "countersign", "status_change", "sla_breach", "sla_warning"]},
        })
        if unresolved_count > 0:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "OPEN_FLAGS_BLOCK_VERIFICATION",
                    "message": "This prescription has unresolved audit flags. Resolve all flags before verifying.",
                    "details": {"prescription_id": prescription_id, "open_flag_count": unresolved_count},
                },
            )

    push_ops: dict = {}

    if new_status == "submitted":
        set_fields["submitted_at"] = now
        ordered_at = _ensure_aware(old_doc.get("ordered_at"))
        if ordered_at:
            set_fields["tat_order_to_submit_min"] = (now - ordered_at).total_seconds() / 60

        # Resubmit after the auditor sent it back: keep the prior version as an immutable revision and apply the edits.
        if current_status == "pending_amendment":
            set_fields["resubmitted_at"] = now
            set_fields["amendment_count"] = old_doc.get("amendment_count", 0) + 1
            push_ops["revisions"] = {
                "medications": old_doc.get("medications", []),
                "notes": old_doc.get("notes"),
                "revised_at": now,
                "revised_by": user_id,
                "reason": old_doc.get("return_reason"),
            }
            new_meds = update_data.get("medications")
            if new_meds:
                set_fields["medications"] = new_meds
            if update_data.get("amendment_note") is not None:
                set_fields["notes"] = update_data["amendment_note"]

    elif new_status == "pending_amendment":
        set_fields["returned_at"] = now
        set_fields["auditor_id"] = user_id

    elif new_status == "verified":
        set_fields["verified_at"] = now
        set_fields["auditor_id"] = user_id
        submitted_at = _ensure_aware(old_doc.get("submitted_at"))
        if submitted_at:
            set_fields["tat_submit_to_verify_min"] = (now - submitted_at).total_seconds() / 60

        resolved_cursor = db.audit_records.find({
            "prescription_id": prescription_id,
            "type": "resolution",
        })
        resolved_audits = await resolved_cursor.to_list(length=None)

        tat_flag_hold_min = 0.0
        for audit in resolved_audits:
            original_flag_id = audit.get("original_flag_id")
            if original_flag_id:
                try:
                    orig = await db.audit_records.find_one({"_id": ObjectId(original_flag_id)})
                except Exception:
                    orig = None
                if orig and audit.get("resolved_at") and orig.get("created_at"):
                    resolved_at = _ensure_aware(audit["resolved_at"])
                    flag_created_at = _ensure_aware(orig["created_at"])
                    flag_hold = (resolved_at - flag_created_at).total_seconds() / 60
                    tat_flag_hold_min += flag_hold
        set_fields["tat_flag_hold_min"] = tat_flag_hold_min

    elif new_status == "dispensed":
        set_fields["dispensed_at"] = now
        set_fields["dispensed_by_id"] = user_id
        # Auto-generate the dispensing receipt number unless one is already on record.
        if not old_doc.get("receipt_number") and not set_fields.get("receipt_number"):
            set_fields["receipt_number"] = await generate_receipt_number(db)
        verified_at = _ensure_aware(old_doc.get("verified_at"))
        submitted_at = _ensure_aware(old_doc.get("submitted_at"))

        if verified_at:
            set_fields["tat_verify_to_dispense_min"] = (now - verified_at).total_seconds() / 60

        if submitted_at:
            tat_pharmacy_min = (now - submitted_at).total_seconds() / 60
            set_fields["tat_pharmacy_min"] = tat_pharmacy_min

            sla_threshold_min = old_doc.get("sla_threshold_min")
            if sla_threshold_min and tat_pharmacy_min > sla_threshold_min:
                sla_breach_duration_min = tat_pharmacy_min - sla_threshold_min
                set_fields["sla_breached"] = True
                set_fields["sla_breach_duration_min"] = sla_breach_duration_min
                set_fields["tat_breached_at"] = now

                safe_old = audit_service._make_snapshot_safe(old_doc)
                await audit_service.create_audit_record(
                    db=db,
                    prescription_id=prescription_id,
                    created_by="system",
                    created_by_role="system",
                    audit_type="sla_breach",
                    issue=f"SLA breached by {sla_breach_duration_min:.1f} minutes",
                    severity="high",
                    recommendation="Review pharmacy workflow for this priority level",
                    flag_code="sla_breach",
                    before_snapshot=safe_old,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )

                rx_number = old_doc.get("rx_number", prescription_id)
                priority = old_doc.get("priority", "unknown")
                breach_event = {
                    "event_type": "sla.breached",
                    "entity_id": prescription_id,
                    "entity_type": "prescription",
                    "message": f"Prescription {rx_number} breached SLA",
                    "data": {
                        "rx_number": rx_number,
                        "patient_id": old_doc.get("patient_id"),
                        "priority": priority,
                        "sla_breach_duration_min": sla_breach_duration_min,
                    },
                    "timestamp": now.isoformat(),
                    "triggered_by_role": role,
                }
                doctor_id_val = old_doc.get("doctor_id")
                breach_rooms = ["pharmacy", "auditor", "admin"]
                if doctor_id_val:
                    breach_rooms.append(f"doctor:{str(doctor_id_val)}")
                await manager.broadcast_multi(breach_rooms, breach_event)

    elif new_status == "administered":
        set_fields["administered_at"] = now
        set_fields["administered_by_id"] = user_id
        dispensed_at = _ensure_aware(old_doc.get("dispensed_at"))
        ordered_at = _ensure_aware(old_doc.get("ordered_at"))

        if dispensed_at:
            set_fields["tat_dispense_to_admin_min"] = (now - dispensed_at).total_seconds() / 60

        if ordered_at:
            set_fields["tat_total_min"] = (now - ordered_at).total_seconds() / 60

    update_ops: dict = {"$set": set_fields}
    if push_ops:
        update_ops["$push"] = push_ops
    result = await db.prescriptions.find_one_and_update(
        {"_id": obj_id},
        update_ops,
        return_document=True,
    )

    if not result:
        return None

    safe_old = audit_service._make_snapshot_safe(old_doc)
    safe_new = audit_service._make_snapshot_safe(result)

    await audit_service.create_audit_record(
        db=db,
        prescription_id=prescription_id,
        created_by=user_id,
        created_by_role=role,
        audit_type="status_change",
        issue=f"Status changed from {current_status} to {new_status}",
        severity="low",
        recommendation="",
        flag_code="status_change",
        before_snapshot=safe_old,
        after_snapshot=safe_new,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    rx_number = result.get("rx_number", prescription_id)
    priority = result.get("priority", "unknown")
    status_event = {
        "event_type": "prescription.status_changed",
        "entity_id": prescription_id,
        "entity_type": "prescription",
        "message": f"Prescription {rx_number} moved to {new_status}",
        "data": {
            "rx_number": rx_number,
            "new_status": new_status,
            "patient_id": result.get("patient_id"),
            "priority": priority,
        },
        "timestamp": now.isoformat(),
        "triggered_by_role": role,
    }

    doctor_id_val = result.get("doctor_id")
    department_id_val = result.get("department_id")

    doctor_room = [f"doctor:{str(doctor_id_val)}", f"user:{str(doctor_id_val)}"] if doctor_id_val else []
    ward_room = [f"ward:{str(department_id_val)}"] if department_id_val else []

    if new_status == "submitted":
        # Awaiting the auditor's safety check before pharmacy.
        await manager.broadcast_multi(["auditor", "admin"], status_event)
    elif new_status == "pending_amendment":
        # Auditor sent it back: the prescribing doctor must be told.
        await manager.broadcast_multi(["auditor", "admin"] + doctor_room, status_event)
    elif new_status == "flagged":
        await manager.broadcast_multi(["pharmacy", "auditor", "admin"] + doctor_room, status_event)
    elif new_status == "verified":
        # Approved by the auditor; pharmacy now processes it and the care team is informed it cleared review.
        await manager.broadcast_multi(["pharmacy", "auditor", "admin"] + doctor_room + ward_room, status_event)
    elif new_status == "dispensed":
        # Pharmacy has dispensed; meds are ready for the ward nurse to pick up.
        await manager.broadcast_multi(["pharmacy", "receptionist", "admin"] + doctor_room + ward_room, status_event)
    elif new_status == "administered":
        # Administration is visible to everyone in the chain.
        await manager.broadcast_multi(
            ["pharmacy", "auditor", "receptionist", "admin"] + doctor_room + ward_room,
            status_event,
        )

    return _doc_to_prescription(result)


# Attach a safety flag to a prescription.
async def add_flag(
    db: AsyncDatabase,
    prescription_id: str,
    flag: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Optional[PrescriptionInDB]:
    try:
        obj_id = ObjectId(prescription_id)
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    result = await db.prescriptions.find_one_and_update(
        {"_id": obj_id},
        {
            "$addToSet": {"flags": flag},
            "$set": {"status": PrescriptionStatus.flagged.value, "updated_at": now},
        },
        return_document=True,
    )
    if not result:
        return None

    flag_event = {
        "event_type": "audit.flag_created",
        "entity_id": prescription_id,
        "entity_type": "prescription",
        "message": f"Flag added to prescription: {flag}",
        "data": {"flag": flag},
        "timestamp": now.isoformat(),
        "triggered_by_role": "system",
    }
    doctor_id_val = result.get("doctor_id")
    rooms = ["pharmacy", "auditor"]
    if doctor_id_val:
        rooms.append(f"doctor:{str(doctor_id_val)}")
    await manager.broadcast_multi(rooms, flag_event)

    return _doc_to_prescription(result)


# Run quick inline safety checks on the medications.
def run_automated_checks(prescription: dict) -> List[dict]:
    issues: List[dict] = []
    medications = prescription.get("medications", [])
    for med in medications:
        if isinstance(med, dict):
            dose_str = med.get("dose", "")
            name = med.get("name", "")
            duration = med.get("duration_days", 0)
        else:
            dose_str = med.dose
            name = med.name
            duration = med.duration_days

        numbers = re.findall(r"\d+(?:\.\d+)?", dose_str)
        for num_str in numbers:
            val = float(num_str)
            unit_lower = dose_str.lower()
            is_high = (
                (val > 2000 and ("mg" in unit_lower or not any(u in unit_lower for u in ["mcg", "microgram", "unit", "iu"])))
                or (val > 500 and any(u in unit_lower for u in ["mcg", "microgram"]))
            )
            if is_high:
                issues.append({
                    "issue": f"High dose detected: {dose_str} for {name}",
                    "severity": "high",
                    "recommendation": "Verify dosage with prescribing physician before dispensing",
                    "flag_code": "high_dose",
                    "drug_name": name,
                    "dose": dose_str,
                })
                break

        if duration > 30:
            issues.append({
                "issue": f"Extended duration: {duration} days for {name}",
                "severity": "medium",
                "recommendation": "Confirm extended duration is clinically appropriate",
                "flag_code": "extended_duration",
                "drug_name": name,
                "dose": dose_str,
            })

    return issues
