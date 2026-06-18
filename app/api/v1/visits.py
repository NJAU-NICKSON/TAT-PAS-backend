from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.asynchronous.database import AsyncDatabase
from app.db.client import get_database
from app.models.visit import VisitCreate, VisitResponse, VisitUpdate, VisitStatus, TriageSubmit, AdmitPatient, ConsultationNote, ConsultationNoteCreate
from app.models.user import UserInDB
from app.security.rbac import get_current_user
from app.services import visit_service


router = APIRouter(prefix="/visits", tags=["visits"])


# Register a new visit.
@router.post("", response_model=VisitResponse)
async def create_visit(
    data: VisitCreate,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    if current_user.role not in ["receptionist", "nurse", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to create visits")
    
    visit = await visit_service.create_visit(data, current_user.id, db)
    return visit


# List visits with filters.
@router.get("", response_model=list[VisitResponse])
async def list_visits(
    patient_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    visit_type: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    visits = await visit_service.list_visits(
        patient_id, status, visit_type, department_id, date_from, date_to, skip, limit, db
    )
    return visits


# Fetch one visit by ID.
@router.get("/{visit_id}", response_model=VisitResponse)
async def get_visit(
    visit_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    visit = await visit_service.get_visit(visit_id, db)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


# Update a visit's status or clinical fields.
@router.patch("/{visit_id}", response_model=VisitResponse)
async def update_visit(
    visit_id: str,
    data: VisitUpdate,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    visit = await visit_service.update_visit(visit_id, data, current_user.id, db)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


# Save the doctor's consultation note.
@router.post("/{visit_id}/consultation-note", response_model=ConsultationNote)
async def add_consultation_note(
    visit_id: str,
    data: ConsultationNoteCreate,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    if current_user.role not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Only doctors can add consultation notes")
    note = await visit_service.add_consultation_note(visit_id, data, current_user.id, db)
    if not note:
        raise HTTPException(status_code=404, detail="Visit not found")
    return note


# Fetch a visit's consultation note.
@router.get("/{visit_id}/consultation-note", response_model=ConsultationNote)
async def get_consultation_note(
    visit_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    note = await visit_service.get_consultation_note(visit_id, db)
    if not note:
        raise HTTPException(status_code=404, detail="Consultation note not found")
    return note


# Record triage and assign a doctor/room.
@router.post("/{visit_id}/triage", response_model=VisitResponse)
async def triage_visit(
    visit_id: str,
    data: TriageSubmit,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    if current_user.role not in ["nurse", "admin"]:
        raise HTTPException(status_code=403, detail="Only nurses can submit triage")
    visit = await visit_service.triage_visit(visit_id, data, current_user.id, db)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


# Admit a patient: assign bed + mark visit as admitted.
@router.post("/{visit_id}/admit", response_model=VisitResponse)
async def admit_patient(
    visit_id: str,
    data: AdmitPatient,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    if current_user.role not in ["nurse", "admin", "doctor", "receptionist"]:
        raise HTTPException(status_code=403, detail="Not authorized to admit patients")
    visit = await visit_service.admit_patient(visit_id, data, current_user.id, db)
    if visit is None:
        raise HTTPException(status_code=400, detail="Visit not found, bed unavailable, or bed not in visit department")
    return visit


# Discharge patient and release their bed back to cleaning.
@router.post("/{visit_id}/discharge", response_model=VisitResponse)
async def discharge_patient(
    visit_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    if current_user.role not in ["receptionist", "nurse", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to discharge patients")
    try:
        visit = await visit_service.discharge_patient(visit_id, current_user.id, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


# Stage-by-stage journey and TAT for a visit.
@router.get("/{visit_id}/journey")
async def get_visit_journey(
    visit_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    visit = await visit_service.get_visit(visit_id, db)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    return await visit_service.build_journey_summary(visit, db)


# List prescriptions on a visit.
@router.get("/{visit_id}/prescriptions")
async def get_visit_prescriptions(
    visit_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database)
):
    visit = await visit_service.get_visit(visit_id, db)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    
    if not visit.prescription_ids:
        return []

    from bson import ObjectId
    valid_ids = [ObjectId(str(rx_id)) for rx_id in visit.prescription_ids if ObjectId.is_valid(str(rx_id))]
    prescriptions = []
    async for rx in db.prescriptions.find({"_id": {"$in": valid_ids}}):
        rx["id"] = str(rx["_id"])
        prescriptions.append(rx)

    return prescriptions
