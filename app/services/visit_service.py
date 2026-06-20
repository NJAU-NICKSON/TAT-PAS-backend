from datetime import datetime, timezone
from typing import Optional, List
from bson import ObjectId
from fastapi import HTTPException
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError
from app.models.visit import VisitCreate, VisitInDB, VisitUpdate, VisitStatus, VisitResponse, TriageSubmit, AdmitPatient, ConsultationNote, ConsultationNoteCreate
from app.ws.manager import manager


# Produce the next visit number for today.
async def generate_visit_number(db: AsyncDatabase) -> str:
    today = datetime.now(timezone.utc)
    date_prefix = today.strftime("%Y%m%d")
    counter_id = f"visit_{date_prefix}"

    result = await db.counters.find_one_and_update(
        {"_id": counter_id},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )

    seq = result.get("seq", 1)

    prefix = f"V-{date_prefix}-"
    existing = await db.visits.find_one(
        {"visit_number": f"{prefix}{seq:04d}"},
        {"_id": 1},
    )
    if existing:
        count = await db.visits.count_documents(
            {"visit_number": {"$regex": f"^{prefix}"}}
        )
        seq = count + 1
        await db.counters.update_one(
            {"_id": counter_id},
            {"$set": {"seq": seq}},
            upsert=True,
        )

    return f"{prefix}{seq:04d}"


# Look up a staff member's display name.
async def _get_user_name(db: AsyncDatabase, user_id: str) -> Optional[str]:
    if not user_id or not ObjectId.is_valid(user_id):
        return None
    udoc = await db.users.find_one({"_id": ObjectId(user_id)}, {"full_name": 1, "username": 1})
    if not udoc:
        return None
    return udoc.get("full_name") or udoc.get("username")


# Register a new visit for a patient.
async def create_visit(data: VisitCreate, created_by_id: str, db: AsyncDatabase) -> VisitInDB:
    now = datetime.now(timezone.utc)
    visit_number = await generate_visit_number(db)
    registered_by_name = await _get_user_name(db, created_by_id)

    doc = {
        "visit_number": visit_number,
        "patient_id": data.patient_id,
        "visit_type": data.visit_type.value,
        "department_id": data.department_id,
        "chief_complaint": data.chief_complaint,
        "priority": data.priority,
        "status": VisitStatus.registered.value,
        "registered_by_id": created_by_id,
        "registered_by_name": registered_by_name,
        "assigned_doctor_id": None,
        "assigned_doctor_name": None,
        "triage_nurse_id": None,
        "triage_nurse_name": None,
        "consultation_room": None,
        "consultation_nurse_id": None,
        "consultation_nurse_name": None,
        "bed_id": None,
        "bed_label": None,
        "prescription_ids": [],
        "registered_at": now,
        "doctor_assigned_at": None,
        "triaged_at": None,
        "consultation_started_at": None,
        "consultation_ended_at": None,
        "admitted_at": None,
        "discharged_at": None,
        "created_at": now,
        "updated_at": now
    }

    for _attempt in range(3):
        try:
            result = await db.visits.insert_one(doc)
            break
        except DuplicateKeyError:
            doc["visit_number"] = await generate_visit_number(db)
    else:
        raise RuntimeError("Could not generate a unique visit number after 3 attempts")

    doc["_id"] = result.inserted_id
    doc["id"] = str(doc["_id"])
    return VisitInDB(**doc)


# Look up a patient's display name.
async def _get_patient_name(db: AsyncDatabase, patient_id: str) -> Optional[str]:
    if not patient_id or not ObjectId.is_valid(patient_id):
        return None
    pdoc = await db.patients.find_one({"_id": ObjectId(patient_id)}, {"first_name": 1, "last_name": 1})
    if not pdoc:
        return None
    return f"{pdoc.get('first_name', '')} {pdoc.get('last_name', '')}".strip() or None


# Attach patient_name and actor names to a visit document.
async def _enrich_visit_doc(doc: dict, db: AsyncDatabase) -> dict:
    doc["patient_name"] = await _get_patient_name(db, str(doc.get("patient_id", "")))

    if doc.get("assigned_doctor_id") and not doc.get("assigned_doctor_name"):
        doc["assigned_doctor_name"] = await _get_user_name(db, str(doc["assigned_doctor_id"]))
    if doc.get("triage_nurse_id") and not doc.get("triage_nurse_name"):
        doc["triage_nurse_name"] = await _get_user_name(db, str(doc["triage_nurse_id"]))
    if doc.get("registered_by_id") and not doc.get("registered_by_name"):
        doc["registered_by_name"] = await _get_user_name(db, str(doc["registered_by_id"]))
    if doc.get("consultation_nurse_id") and not doc.get("consultation_nurse_name"):
        doc["consultation_nurse_name"] = await _get_user_name(db, str(doc["consultation_nurse_id"]))

    if doc.get("bed_id") and not doc.get("bed_label"):
        try:
            bed_doc = await db.beds.find_one(
                {"_id": ObjectId(str(doc["bed_id"]))},
                {"bed_label": 1, "ward_name": 1},
            )
            if bed_doc:
                doc["bed_label"] = bed_doc.get("bed_label") or bed_doc.get("ward_name")
        except Exception:
            pass

    return doc


# Fetch one visit by ID, with names attached.
async def get_visit(visit_id: str, db: AsyncDatabase) -> Optional[VisitResponse]:
    try:
        obj_id = ObjectId(visit_id)
    except Exception:
        return None

    doc = await db.visits.find_one({"_id": obj_id})
    if not doc:
        return None
    doc["id"] = str(doc["_id"])
    doc = await _enrich_visit_doc(doc, db)
    return VisitResponse(**doc)


# List visits with filters and paging.
async def list_visits(
    patient_id: Optional[str],
    status: Optional[str],
    visit_type: Optional[str],
    department_id: Optional[str],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    skip: int,
    limit: int,
    db: AsyncDatabase,
    scope_role: Optional[str] = None,
    scope_user_id: Optional[str] = None,
) -> List[VisitResponse]:
    query = {}
    if patient_id:
        query["patient_id"] = patient_id
    if status:
        query["status"] = status
    if visit_type:
        query["visit_type"] = visit_type
    if department_id:
        query["department_id"] = department_id
    if date_from or date_to:
        date_filter = {}
        if date_from:
            date_filter["$gte"] = date_from
        if date_to:
            date_filter["$lte"] = date_to
        query["registered_at"] = date_filter

    # Doctors and nurses see only patients assigned to them; admin, auditor,
    # billing, and receptionist keep full visibility. Nurses also see the
    # shared triage queue (patients not yet triaged / not yet assigned a nurse)
    # so they can pick up new arrivals.
    if scope_role == "doctor" and scope_user_id:
        query["$or"] = [
            {"assigned_doctor_id": scope_user_id},
            {"assigned_doctor_id": {"$in": [None, ""]}, "status": "waiting_for_doctor"},
        ]
    elif scope_role == "nurse" and scope_user_id:
        query["$or"] = [
            {"triage_nurse_id": scope_user_id},
            {"consultation_nurse_id": scope_user_id},
            {"triage_nurse_id": {"$in": [None, ""]}, "status": {"$in": ["registered", "triaged", "waiting_for_doctor"]}},
        ]

    cursor = db.visits.find(query).sort([("registered_at", -1)]).skip(skip).limit(limit)
    docs = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        docs.append(doc)

    pid_set = list({str(d.get("patient_id", "")) for d in docs if d.get("patient_id")})
    valid_pids = [ObjectId(pid) for pid in pid_set if ObjectId.is_valid(pid)]
    patient_map: dict = {}
    if valid_pids:
        async for pdoc in db.patients.find({"_id": {"$in": valid_pids}}, {"first_name": 1, "last_name": 1}):
            name = f"{pdoc.get('first_name', '')} {pdoc.get('last_name', '')}".strip()
            patient_map[str(pdoc["_id"])] = name or None

    visits = []
    for doc in docs:
        doc["patient_name"] = patient_map.get(str(doc.get("patient_id", "")))
        visits.append(VisitResponse(**doc))
    return visits


# Update visit status and/or clinical fields.
async def update_visit(visit_id: str, data: VisitUpdate, user_id: str, db: AsyncDatabase, role: Optional[str] = None) -> Optional[VisitResponse]:
    try:
        obj_id = ObjectId(visit_id)
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    update_fields: dict = {"updated_at": now}

    # Only the receptionist (and admin) may set or change the consultation room.
    if data.consultation_room is not None and role not in (None, "receptionist", "admin"):
        raise HTTPException(status_code=403, detail="Only the receptionist can assign the consultation room.")

    if data.status:
        update_fields["status"] = data.status.value
        if data.status in (VisitStatus.triaged, VisitStatus.waiting_for_doctor):
            update_fields["triaged_at"] = now
        elif data.status == VisitStatus.in_consultation:
            update_fields["consultation_started_at"] = now
        elif data.status == VisitStatus.admitted:
            update_fields["admitted_at"] = now
        elif data.status == VisitStatus.discharged:
            update_fields["discharged_at"] = now
            visit_doc = await db.visits.find_one({"_id": obj_id})
            bed_id = visit_doc.get("bed_id") if visit_doc else None
            if bed_id:
                try:
                    await db.beds.update_one(
                        {"_id": ObjectId(bed_id)},
                        {"$set": {"status": "cleaning", "current_patient_id": None,
                                  "current_admission_id": None, "updated_at": now}}
                    )
                except Exception:
                    pass

    if data.assigned_doctor_id is not None:
        doctor_doc = await db.users.find_one(
            {"_id": ObjectId(data.assigned_doctor_id)},
            {"role": 1},
        )
        if not doctor_doc or doctor_doc.get("role") != "doctor":
            raise HTTPException(
                status_code=422,
                detail="assigned_doctor_id must reference a user with role 'doctor'",
            )
        update_fields["assigned_doctor_id"] = data.assigned_doctor_id
        update_fields["assigned_doctor_name"] = await _get_user_name(db, data.assigned_doctor_id)
        existing = await db.visits.find_one({"_id": obj_id}, {"doctor_assigned_at": 1})
        if not (existing and existing.get("doctor_assigned_at")):
            update_fields["doctor_assigned_at"] = now

    if data.chief_complaint is not None:
        update_fields["chief_complaint"] = data.chief_complaint
    if data.priority is not None:
        update_fields["priority"] = data.priority
    if data.billing_completed_at is not None:
        update_fields["billing_completed_at"] = data.billing_completed_at
    if data.consultation_room is not None:
        update_fields["consultation_room"] = data.consultation_room
    if data.consultation_nurse_id is not None:
        nurse_doc = await db.users.find_one(
            {"_id": ObjectId(data.consultation_nurse_id)},
            {"role": 1},
        )
        if not nurse_doc or nurse_doc.get("role") != "nurse":
            raise HTTPException(status_code=422, detail="consultation_nurse_id must reference a user with role 'nurse'")
        update_fields["consultation_nurse_id"] = data.consultation_nurse_id
        update_fields["consultation_nurse_name"] = await _get_user_name(db, data.consultation_nurse_id)
    if data.diagnosis is not None:
        update_fields["diagnosis"] = data.diagnosis
    if data.clinical_findings is not None:
        update_fields["clinical_findings"] = data.clinical_findings
    if data.recommendations is not None:
        update_fields["recommendations"] = data.recommendations
    if data.follow_up_instructions is not None:
        update_fields["follow_up_instructions"] = data.follow_up_instructions
    if data.discharge_notes is not None:
        update_fields["discharge_notes"] = data.discharge_notes

    result = await db.visits.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_fields},
        return_document=True
    )

    if not result:
        return None
    result["id"] = str(result["_id"])
    result = await _enrich_visit_doc(result, db)

    # Notify newly assigned staff directly via their personal rooms.
    assign_rooms: list[str] = []
    if data.assigned_doctor_id is not None:
        assign_rooms.append(f"doctor:{data.assigned_doctor_id}")
        assign_rooms.append(f"user:{data.assigned_doctor_id}")
    if data.consultation_nurse_id is not None:
        assign_rooms.append(f"user:{data.consultation_nurse_id}")
    if assign_rooms:
        await manager.broadcast_multi(assign_rooms, {
            "event_type": "patient.assigned",
            "entity_id": result["id"],
            "entity_type": "visit",
            "message": f"Patient {result.get('patient_name') or ''} assigned to you",
            "data": {
                "visit_id": result["id"],
                "visit_number": result.get("visit_number"),
                "patient_name": result.get("patient_name"),
                "consultation_room": result.get("consultation_room"),
                "assigned_doctor_name": result.get("assigned_doctor_name"),
                "consultation_nurse_name": result.get("consultation_nurse_name"),
            },
            "timestamp": now.isoformat(),
        })

    return VisitResponse(**result)


# Change a visit's status and stamp the time.
async def update_visit_status(visit_id: str, status: VisitStatus, user_id: str, db: AsyncDatabase) -> Optional[VisitResponse]:
    data = VisitUpdate(status=status)
    return await update_visit(visit_id, data, user_id, db)


# Record triage vitals and move the visit forward.
async def triage_visit(visit_id: str, data: TriageSubmit, nurse_id: str, db: AsyncDatabase) -> Optional[VisitInDB]:
    try:
        obj_id = ObjectId(visit_id)
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    nurse_name = await _get_user_name(db, nurse_id)
    update_fields: dict = {
        "status": VisitStatus.waiting_for_doctor.value,
        "triaged_at": now,
        "triage_nurse_id": nurse_id,
        "triage_nurse_name": nurse_name,
        "vitals": data.vitals.model_dump(),
        "updated_at": now,
    }
    if data.assigned_doctor_id:
        doctor_doc = await db.users.find_one({"_id": ObjectId(data.assigned_doctor_id)}, {"role": 1})
        if not doctor_doc or doctor_doc.get("role") != "doctor":
            raise HTTPException(status_code=422, detail="assigned_doctor_id must reference a user with role 'doctor'")
        update_fields["assigned_doctor_id"] = data.assigned_doctor_id
        update_fields["assigned_doctor_name"] = await _get_user_name(db, data.assigned_doctor_id)

    result = await db.visits.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_fields},
        return_document=True
    )
    if not result:
        return None
    result["id"] = str(result["_id"])
    result = await _enrich_visit_doc(result, db)
    return VisitResponse(**result)


# Assign a bed and mark visit as admitted atomically.
async def admit_patient(visit_id: str, data: AdmitPatient, user_id: str, db: AsyncDatabase) -> Optional[VisitInDB]:
    try:
        visit_obj_id = ObjectId(visit_id)
        bed_obj_id = ObjectId(data.bed_id)
    except Exception:
        return None

    visit_doc = await db.visits.find_one({"_id": visit_obj_id})
    if not visit_doc:
        return None

    admittable_statuses = {"triaged", "waiting_for_doctor", "in_consultation", "awaiting_results", "treatment_in_progress"}
    if visit_doc.get("status") not in admittable_statuses:
        return None

    bed_doc = await db.beds.find_one({
        "_id": bed_obj_id,
        "status": {"$in": ["available", "reserved"]},
    })
    if not bed_doc:
        return None

    if data.assigned_doctor_id:
        doctor_doc = await db.users.find_one({"_id": ObjectId(data.assigned_doctor_id)}, {"role": 1})
        if not doctor_doc or doctor_doc.get("role") != "doctor":
            raise HTTPException(status_code=422, detail="assigned_doctor_id must reference a user with role 'doctor'")

    now = datetime.now(timezone.utc)

    await db.beds.update_one(
        {"_id": bed_obj_id},
        {"$set": {
            "status": "occupied",
            "current_patient_id": visit_doc["patient_id"],
            "current_admission_id": visit_id,
            "updated_at": now,
        }}
    )

    update_fields = {
        "status": VisitStatus.admitted.value,
        "visit_type": "ipd",
        "department_id": bed_doc.get("department_id", visit_doc.get("department_id")),
        "admitted_at": now,
        "bed_id": data.bed_id,
        "bed_label": bed_doc.get("bed_label"),
        "ward_name": bed_doc.get("ward_name"),
        "updated_at": now,
    }
    if data.notes:
        update_fields["admission_notes"] = data.notes
    if data.assigned_doctor_id:
        update_fields["assigned_doctor_id"] = data.assigned_doctor_id
        update_fields["assigned_doctor_name"] = await _get_user_name(db, data.assigned_doctor_id)

    result = await db.visits.find_one_and_update(
        {"_id": visit_obj_id},
        {"$set": update_fields},
        return_document=True
    )
    if not result:
        return None
    result["id"] = str(result["_id"])
    result = await _enrich_visit_doc(result, db)
    return VisitInDB(**result)


# Discharge patient and release bed to cleaning status.
async def discharge_patient(visit_id: str, user_id: str, db: AsyncDatabase) -> Optional[VisitInDB]:
    try:
        obj_id = ObjectId(visit_id)
    except Exception:
        return None

    visit_doc = await db.visits.find_one({"_id": obj_id})
    if not visit_doc:
        return None

    unpaid = await db.bills.find_one({
        "visit_id": visit_id,
        "status": {"$in": ["open", "partially_paid"]},
    })
    if unpaid:
        raise ValueError("Cannot discharge: the patient has an outstanding bill. Settle billing first.")

    pending_rx = await db.prescriptions.find_one({
        "visit_id": visit_id,
        "status": {"$nin": ["administered", "archived", "cancelled"]},
    })
    if pending_rx:
        raise ValueError("Cannot discharge: the patient has prescribed medication that has not been administered yet.")

    now = datetime.now(timezone.utc)

    bed_id = visit_doc.get("bed_id")
    if bed_id:
        try:
            bed_obj_id = ObjectId(bed_id)
            await db.beds.update_one(
                {"_id": bed_obj_id},
                {"$set": {
                    "status": "cleaning",
                    "current_patient_id": None,
                    "current_admission_id": None,
                    "updated_at": now,
                }}
            )
        except Exception:
            pass

    result = await db.visits.find_one_and_update(
        {"_id": obj_id},
        {"$set": {
            "status": VisitStatus.discharged.value,
            "discharged_at": now,
            "updated_at": now,
        }},
        return_document=True
    )
    if not result:
        return None
    result["id"] = str(result["_id"])
    return VisitInDB(**result)


# Return per-stage TAT breakdown for a visit (in minutes).
async def build_journey_summary(visit: VisitInDB, db: AsyncDatabase) -> dict:
    # Strip timezone info from a datetime for subtraction.
    def _naive(dt) -> Optional[datetime]:
        if dt is None:
            return None
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    # Minutes between two times, or None if either is missing.
    def diff_min(a, b) -> Optional[float]:
        a, b = _naive(a), _naive(b)
        if a and b:
            return round((b - a).total_seconds() / 60, 1)
        return None

    # Earliest of the given times, ignoring None.
    def earliest(values):
        vals = [_naive(v) for v in values if v is not None]
        return min(vals) if vals else None

    now = datetime.utcnow()
    end = _naive(visit.discharged_at) or now

    rx_submitted_at   = None
    rx_verified_at    = None
    rx_dispensed_at   = None
    rx_administered_at = None

    rxs = await db.prescriptions.find(
        {"visit_id": str(visit.id)},
        {"submitted_at": 1, "verified_at": 1, "dispensed_at": 1, "administered_at": 1},
    ).to_list(length=None)
    if rxs:
        rx_submitted_at    = earliest(r.get("submitted_at")    for r in rxs)
        rx_verified_at     = earliest(r.get("verified_at")     for r in rxs)
        rx_dispensed_at    = earliest(r.get("dispensed_at")    for r in rxs)
        rx_administered_at = earliest(r.get("administered_at") for r in rxs)

    consultation_ended = _naive(visit.consultation_ended_at)
    if consultation_ended is None:
        audit_start = None
    else:
        audit_start = rx_submitted_at or consultation_ended

    stages = [
        {
            "stage": 1,
            "name": "Registration",
            "role": "receptionist",
            "started_at": visit.registered_at,
            "completed_at": visit.doctor_assigned_at or visit.triaged_at,
            "target_min": 10,
            "tat_min": diff_min(visit.registered_at, visit.doctor_assigned_at or visit.triaged_at),
        },
        {
            "stage": 2,
            "name": "Triage",
            "role": "nurse",
            "started_at": visit.triaged_at,
            "completed_at": visit.consultation_started_at,
            "target_min": 15,
            "tat_min": diff_min(visit.triaged_at, visit.consultation_started_at),
        },
        {
            "stage": 3,
            "name": "Doctor Consultation",
            "role": "doctor",
            "started_at": visit.consultation_started_at,
            "completed_at": visit.consultation_ended_at,
            "target_min": 30,
            "tat_min": diff_min(visit.consultation_started_at, visit.consultation_ended_at),
        },
        {
            "stage": 4,
            "name": "Prescription Audit",
            "role": "auditor",
            "started_at": audit_start,
            "completed_at": rx_verified_at,
            "target_min": 30,
            "tat_min": diff_min(audit_start, rx_verified_at),
        },
        {
            "stage": 5,
            "name": "Pharmacy Dispensing",
            "role": "pharmacist",
            "started_at": rx_verified_at,
            "completed_at": rx_dispensed_at,
            "target_min": 20,
            "tat_min": diff_min(rx_verified_at, rx_dispensed_at),
        },
        {
            "stage": 6,
            "name": "Drug Administration",
            "role": "nurse",
            "started_at": rx_dispensed_at,
            "completed_at": rx_administered_at,
            "target_min": 15,
            "tat_min": diff_min(rx_dispensed_at, rx_administered_at),
        },
        {
            "stage": 7,
            "name": "Billing",
            "role": "billing",
            "started_at": visit.billing_completed_at,
            "completed_at": visit.discharged_at,
            "target_min": 15,
            "tat_min": diff_min(visit.billing_completed_at, visit.discharged_at),
        },
    ]

    total_tat = diff_min(visit.registered_at, end)
    return {
        "visit_id": visit.id,
        "visit_number": visit.visit_number,
        "patient_id": visit.patient_id,
        "current_status": visit.status,
        "bed_id": visit.bed_id,
        "stages": stages,
        "total_tat_min": total_tat,
        "target_total_min": 130,
        "is_complete": visit.discharged_at is not None,
    }


# Store (upsert) a consultation note on the visit document and update clinical fields.
async def add_consultation_note(
    visit_id: str, data: ConsultationNoteCreate, doctor_id: str, db: AsyncDatabase
) -> Optional[ConsultationNote]:
    try:
        obj_id = ObjectId(visit_id)
    except Exception:
        return None

    visit_doc = await db.visits.find_one({"_id": obj_id})
    if not visit_doc:
        return None

    now = datetime.now(timezone.utc)
    doctor_name = await _get_user_name(db, doctor_id)
    nurse_name = None
    if data.assisting_nurse_id:
        nurse_name = await _get_user_name(db, data.assisting_nurse_id)

    note = {
        "visit_id": visit_id,
        "patient_id": visit_doc.get("patient_id", ""),
        "doctor_id": doctor_id,
        "doctor_name": doctor_name,
        "consultation_room": data.consultation_room,
        "assisting_nurse_id": data.assisting_nurse_id,
        "assisting_nurse_name": nurse_name,
        "chief_complaint": data.chief_complaint or visit_doc.get("chief_complaint"),
        "clinical_findings": data.clinical_findings,
        "diagnosis": data.diagnosis,
        "recommendations": data.recommendations,
        "plan_of_care": data.plan_of_care,
        "follow_up_instructions": data.follow_up_instructions,
        "follow_up_date": data.follow_up_date,
        "created_at": now,
        "updated_at": now,
    }

    await db.consultation_notes.update_one(
        {"visit_id": visit_id},
        {"$set": note},
        upsert=True,
    )

    # The receptionist owns room/nurse assignment, so the consultation note
    # only records clinical fields back onto the visit.
    visit_update: dict = {
        "assigned_doctor_name": doctor_name,
        "diagnosis": data.diagnosis,
        "clinical_findings": data.clinical_findings,
        "recommendations": data.recommendations,
        "follow_up_instructions": data.follow_up_instructions,
        "consultation_ended_at": now,
        "updated_at": now,
    }
    await db.visits.update_one({"_id": obj_id}, {"$set": {k: v for k, v in visit_update.items() if v is not None}})

    note_doc = await db.consultation_notes.find_one({"visit_id": visit_id})
    if note_doc:
        note_doc["id"] = str(note_doc["_id"])
    return ConsultationNote(**{k: v for k, v in (note_doc or note).items() if k != "_id"}) if note_doc else ConsultationNote(**note)


# Retrieve the consultation note for a visit.
async def get_consultation_note(visit_id: str, db: AsyncDatabase) -> Optional[ConsultationNote]:
    doc = await db.consultation_notes.find_one({"visit_id": visit_id})
    if not doc:
        return None
    doc["id"] = str(doc["_id"])
    return ConsultationNote(**{k: v for k, v in doc.items() if k != "_id"})


# Link a prescription onto a visit.
async def add_prescription_to_visit(visit_id: str, prescription_id: str, db: AsyncDatabase) -> bool:
    try:
        obj_id = ObjectId(visit_id)
    except Exception:
        return False
    
    result = await db.visits.update_one(
        {"_id": obj_id},
        {
            "$addToSet": {"prescription_ids": prescription_id},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    return result.modified_count > 0
