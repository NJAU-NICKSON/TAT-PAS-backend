from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from pymongo.asynchronous.database import AsyncDatabase
from pydantic import BaseModel, Field
from datetime import date
from app.db.client import get_database
from app.models.audit import AuditRecordResponse, CountersignRequest, ResolutionType
from app.security.rbac import Roles, require_roles
from app.services.audit_service import (
    get_audit_by_id,
    get_audit_records,
    get_audit_log,
    get_unresolved_audit_records,
    resolve_audit_record,
    countersign_audit,
    get_security_events_for_day,
    mark_events_reviewed,
    create_audit_record,
    verify_chain_integrity,
    verify_prescription_integrity,
)
from app.services.prescription_service import add_flag

router = APIRouter(prefix="/audits", tags=["audits"])


# Request body to resolve a prescription's flags.
class ResolveAuditRequest(BaseModel):
    resolution_note: str = Field(..., min_length=3)
    resolution_type: ResolutionType


# Request body to mark security events reviewed.
class ReviewSecurityRequest(BaseModel):
    event_ids: List[str]


# Request body to raise a manual flag.
class FlagCreateRequest(BaseModel):
    prescription_id: str
    issue: str = Field(..., min_length=5)
    severity: str
    recommendation: str = Field(..., min_length=5)
    flag_code: str = "manual_flag"
    drug_name: Optional[str] = None
    dose: Optional[str] = None


# Create a manual audit flag on a prescription.
@router.post("/flag", response_model=AuditRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_flag(
    body: FlagCreateRequest,
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    record = await create_audit_record(
        db=db,
        prescription_id=body.prescription_id,
        created_by=current_user.id,
        created_by_role=current_user.role,
        audit_type="manual",
        issue=body.issue,
        severity=body.severity,
        recommendation=body.recommendation,
        flag_code=body.flag_code,
        drug_name=body.drug_name,
        dose=body.dose,
    )
    await add_flag(db, body.prescription_id, body.flag_code)
    return record


# All unresolved clinical flags, sorted by severity then age.
@router.get("/unresolved", response_model=list[AuditRecordResponse])
async def list_unresolved(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_unresolved_audit_records(db, skip=skip, limit=limit)


# Verify the tamper-evident hash chain over all audit records.
@router.get("/verify-integrity")
async def verify_integrity(
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await verify_chain_integrity(db)


# Verify integrity for a single prescription (by rx_number or id) and return its trail.
@router.get("/verify-integrity/{identifier}")
async def verify_prescription_integrity_endpoint(
    identifier: str,
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await verify_prescription_integrity(db, identifier)


# Full immutable audit log. Append-only. Filterable. Paginated.
@router.get("/log", response_model=list[AuditRecordResponse])
async def audit_log(
    prescription_id: Optional[str] = Query(None),
    flag_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_audit_log(
        db,
        skip=skip,
        limit=limit,
        prescription_id=prescription_id,
        flag_type=flag_type,
        severity=severity,
        resolved=resolved,
        date_from=date_from,
        date_to=date_to,
    )


# List audit records with filters and paging.
@router.get("/", response_model=list[AuditRecordResponse])
async def list_audits(
    prescription_id: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_audit_records(
        db, prescription_id=prescription_id, resolved=resolved, skip=skip, limit=limit
    )


# Security events for a given day.
@router.get("/security/daily", response_model=list[AuditRecordResponse])
async def get_daily_security_events(
    review_date: date = Query(..., description="Date in YYYY-MM-DD format"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_security_events_for_day(db, review_date, skip=skip, limit=limit)


# Mark security events as reviewed.
@router.post("/security/review", status_code=status.HTTP_200_OK)
async def review_security_events(
    body: ReviewSecurityRequest,
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    count = await mark_events_reviewed(db, body.event_ids, current_user.id)
    return {"reviewed_count": count}


# Countersign a HIGH or CRITICAL severity flag.
@router.post("/countersign", response_model=AuditRecordResponse, status_code=status.HTTP_201_CREATED)
async def countersign_flag(
    body: CountersignRequest,
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await countersign_audit(
        db=db,
        flag_id=body.flag_id,
        countersigner_id=current_user.id,
        countersigner_role=current_user.role,
        note=body.note,
    )


# Fetch one audit record by ID.
@router.get("/{audit_id}", response_model=AuditRecordResponse)
async def get_audit(
    audit_id: str,
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    record = await get_audit_by_id(db, audit_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "AUDIT_NOT_FOUND",
                "message": "Audit record not found.",
                "details": {"audit_id": audit_id},
            },
        )
    return record


# Resolve all open flags on a prescription.
@router.post("/{prescription_id}/resolve", response_model=list[AuditRecordResponse])
async def resolve_prescription_audits(
    prescription_id: str,
    body: ResolveAuditRequest = Body(...),
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await resolve_audit_record(
        prescription_id=prescription_id,
        resolution_note=body.resolution_note,
        resolution_type=body.resolution_type.value,
        auditor=current_user,
        db=db,
    )
