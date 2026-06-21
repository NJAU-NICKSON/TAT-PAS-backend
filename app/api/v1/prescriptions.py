from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from pymongo.asynchronous.database import AsyncDatabase
from app.db.client import get_database
from app.security.rbac import NURSING_ROLES, Roles, get_current_user, require_roles
from app.models.prescription import (
    PrescriptionCreate,
    PrescriptionInDB,
    PrescriptionUpdate,
)
from app.services.audit_service import create_audit_record
from app.services.prescription_service import (
    add_flag,
    advance_status,
    create_prescription,
    get_prescription_by_id,
    get_prescription_history,
    get_prescription_queue,
    get_prescriptions,
    run_automated_checks,
    _doc_to_prescription,
    _enrich_docs_with_names,
)
from app.services import flagging_service

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])

_PHARMACIST_VISIBLE = ["verified", "dispensed"]
_NURSE_VISIBLE = ["dispensed", "administered"]
_AUDITOR_VISIBLE = ["submitted", "flagged", "pending_amendment", "verified"]

nursing_role_values = [r.value for r in NURSING_ROLES]


# Active pharmacy queue: submitted and flagged prescriptions sorted by
@router.get("/queue", response_model=list[PrescriptionInDB])
async def prescription_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user=Depends(require_roles(Roles.pharmacist, Roles.admin, Roles.auditor)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_prescription_queue(db, skip=skip, limit=limit, role=current_user.role)


# Create a prescription and run safety checks.
@router.post("/", response_model=PrescriptionInDB, status_code=status.HTTP_201_CREATED)
async def create_prescription_endpoint(
    request: Request,
    body: PrescriptionCreate,
    current_user=Depends(require_roles(Roles.doctor, Roles.nurse)),
    db: AsyncDatabase = Depends(get_database),
):
    prescription = await create_prescription(db, body, current_user.id)

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    checks = run_automated_checks({"medications": [m.model_dump() for m in body.medications]})

    if body.patient_id:
        from bson import ObjectId
        patient_doc = await db.patients.find_one({"_id": ObjectId(body.patient_id)}) if ObjectId.is_valid(body.patient_id) else None
        if patient_doc:
            active_rxs_cursor = db.prescriptions.find({
                "patient_id": body.patient_id,
                "status": {"$in": ["submitted", "verified", "flagged"]},
                "id": {"$ne": prescription.id},
            })
            active_rxs = await active_rxs_cursor.to_list(length=50)
            rx_dict = {"medications": [m.model_dump() for m in body.medications]}
            advanced_flags = await flagging_service.check_all_rules(rx_dict, patient_doc, active_rxs, db)
            existing_codes = {c.get("flag_code") for c in checks}
            for flag in advanced_flags:
                if flag.code not in existing_codes:
                    checks.append({
                        "issue": flag.issue,
                        "severity": flag.severity.value if hasattr(flag.severity, "value") else str(flag.severity),
                        "recommendation": flag.recommendation,
                        "flag_code": flag.code,
                    })
                    existing_codes.add(flag.code)

    for check in checks:
        await create_audit_record(
            db=db,
            prescription_id=prescription.id,
            created_by=current_user.id,
            created_by_role=current_user.role,
            audit_type="automated",
            issue=check["issue"],
            severity=check["severity"],
            recommendation=check["recommendation"],
            flag_code=check.get("flag_code", "generic"),
            ip_address=ip,
            user_agent=ua,
        )
        await add_flag(db, prescription.id, check.get("flag_code", check["issue"]), ip_address=ip, user_agent=ua)

    if checks:
        prescription = await get_prescription_by_id(db, prescription.id)

    return prescription


# List prescriptions with filters.
@router.get("/", response_model=list[PrescriptionInDB])
async def list_prescriptions(
    status_filter: Optional[str] = Query(None, alias="status"),
    patient_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=500),
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    role = current_user.role
    doctor_id_filter: Optional[str] = None

    if role == Roles.doctor.value:
        doctor_id_filter = current_user.id
    elif role == Roles.pharmacist.value:
        if status_filter and status_filter not in _PHARMACIST_VISIBLE:
            return []
    elif role == Roles.auditor.value:
        if status_filter and status_filter not in _AUDITOR_VISIBLE:
            return []
    elif role in nursing_role_values:
        if status_filter and status_filter not in _NURSE_VISIBLE:
            return []

    query: dict = {}
    if doctor_id_filter:
        query["doctor_id"] = doctor_id_filter
    if status_filter:
        query["status"] = status_filter
    if patient_id:
        query["patient_id"] = patient_id
    if date_from or date_to:
        date_query: dict = {}
        if date_from:
            date_query["$gte"] = date_from
        if date_to:
            date_query["$lte"] = date_to
        query["ordered_at"] = date_query

    if role == Roles.pharmacist.value and not status_filter:
        query["status"] = {"$in": _PHARMACIST_VISIBLE}
    elif role == Roles.auditor.value and not status_filter:
        query["status"] = {"$in": _AUDITOR_VISIBLE}
    elif role in nursing_role_values and not status_filter:
        query["status"] = {"$in": _NURSE_VISIBLE}

    cursor = db.prescriptions.find(query).sort([("created_at", -1)]).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    docs = await _enrich_docs_with_names(db, docs)
    return [_doc_to_prescription(doc) for doc in docs]


# Full chronological audit trail for a prescription.
@router.get("/{prescription_id}/history")
async def get_history(
    prescription_id: str,
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_prescription_history(db, prescription_id)


# Fetch one prescription by ID.
@router.get("/{prescription_id}", response_model=PrescriptionInDB)
async def get_prescription(
    prescription_id: str,
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    prescription = await get_prescription_by_id(db, prescription_id)
    if not prescription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "PRESCRIPTION_NOT_FOUND",
                "message": "Prescription not found.",
                "details": {"prescription_id": prescription_id},
            },
        )
    return prescription


# Dedicated status-change endpoint used by auditors, pharmacists, and nurses.
@router.patch("/{prescription_id}/status", response_model=PrescriptionInDB)
async def update_prescription_status(
    request: Request,
    prescription_id: str,
    body: PrescriptionUpdate,
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    permitted_roles = [
        Roles.doctor.value,
        Roles.pharmacist.value,
        Roles.auditor.value,
        *nursing_role_values,
        Roles.admin.value,
    ]
    if current_user.role not in permitted_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")

    if not body.status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A target status is required.")

    update_data = {}
    for field in ("notes", "pharmacist_comment", "return_reason", "administered_dose",
                  "administered_route", "administered_time_actual", "administration_notes", "receipt_number"):
        val = getattr(body, field, None)
        if val is not None:
            update_data[field] = val

    updated = await advance_status(
        db=db,
        prescription_id=prescription_id,
        new_status=body.status.value,
        user_id=current_user.id,
        role=current_user.role,
        update_data=update_data,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescription not found.")
    return updated


# Change a prescription's status.
@router.patch("/{prescription_id}", response_model=PrescriptionInDB)
async def update_prescription(
    request: Request,
    prescription_id: str,
    body: PrescriptionUpdate,
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    permitted_roles = [
        Roles.doctor.value,
        Roles.pharmacist.value,
        *nursing_role_values,
        Roles.admin.value,
    ]
    if current_user.role not in permitted_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "UPDATE_FORBIDDEN",
                "message": "Insufficient permissions to update prescriptions.",
                "details": {"role": current_user.role},
            },
        )

    if not body.status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "STATUS_REQUIRED",
                "message": "A target status is required for prescription updates.",
                "details": {},
            },
        )

    update_data = {}
    if body.notes is not None:
        update_data["notes"] = body.notes
    if body.pharmacist_comment is not None:
        update_data["pharmacist_comment"] = body.pharmacist_comment

    updated = await advance_status(
        db=db,
        prescription_id=prescription_id,
        new_status=body.status.value,
        user_id=current_user.id,
        role=current_user.role,
        update_data=update_data,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "PRESCRIPTION_NOT_FOUND",
                "message": "Prescription not found.",
                "details": {"prescription_id": prescription_id},
            },
        )
    return updated


# Raise a simple flag on a prescription.
@router.post("/{prescription_id}/flag", response_model=PrescriptionInDB)
async def flag_prescription(
    request: Request,
    prescription_id: str,
    flag: str = Body(..., embed=True),
    current_user=Depends(require_roles(Roles.pharmacist, Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    updated = await add_flag(
        db,
        prescription_id,
        flag,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "PRESCRIPTION_NOT_FOUND",
                "message": "Prescription not found.",
                "details": {"prescription_id": prescription_id},
            },
        )
    return updated


# Raise a detailed flag on a prescription.
@router.post("/{prescription_id}/flags", response_model=PrescriptionInDB)
async def flag_prescription_detailed(
    request: Request,
    prescription_id: str,
    issue: str = Body(...),
    severity: str = Body(...),
    recommendation: str = Body(...),
    flag_code: str = Body("manual_flag"),
    current_user=Depends(require_roles(Roles.pharmacist, Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    await create_audit_record(
        db=db,
        prescription_id=prescription_id,
        created_by=current_user.id,
        created_by_role=current_user.role,
        audit_type="manual",
        issue=issue,
        severity=severity,
        recommendation=recommendation,
        flag_code=flag_code,
        ip_address=ip,
        user_agent=ua,
    )

    updated = await add_flag(db, prescription_id, flag_code, ip_address=ip, user_agent=ua)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "PRESCRIPTION_NOT_FOUND",
                "message": "Prescription not found.",
                "details": {"prescription_id": prescription_id},
            },
        )
    return updated
