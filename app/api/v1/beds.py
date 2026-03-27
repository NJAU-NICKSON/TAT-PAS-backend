from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.db.client import get_database
from app.security.rbac import require_roles, Roles, get_current_user
from app.models.bed import (
    BedCreate,
    BedUpdate,
    BedResponse,
    BedWithPatient,
    BedAvailabilitySummary,
)
from app.services import bed_service, department_service

router = APIRouter(prefix="/beds", tags=["beds"])


@router.get("", response_model=List[BedResponse])
async def list_beds(
    department_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    bed_type: Optional[str] = Query(None),
    ward_name: Optional[str] = Query(None),
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    beds = await bed_service.get_all_beds(
        db,
        department_id=department_id,
        status=status,
        bed_type=bed_type,
        ward_name=ward_name,
    )
    return beds


@router.get("/availability-summary", response_model=List[BedAvailabilitySummary])
async def get_bed_availability_summary(
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    summary = await bed_service.get_bed_availability_summary(db)
    return summary


@router.get("/available", response_model=List[BedResponse])
async def get_available_beds(
    bed_type: str = Query(...),
    department_id: Optional[str] = Query(None),
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    beds = await bed_service.get_available_beds_by_type(db, bed_type, department_id)
    return beds


@router.get("/department/{department_id}", response_model=List[BedWithPatient])
async def get_beds_by_department(
    department_id: str,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    department = await department_service.get_department_by_id(db, department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    beds = await bed_service.get_beds_by_department(db, department_id)
    return beds


@router.get("/{bed_id}", response_model=BedResponse)
async def get_bed(
    bed_id: str,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    bed = await bed_service.get_bed_by_id(db, bed_id)
    if not bed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bed not found",
        )
    return bed


@router.post("", response_model=BedResponse, status_code=status.HTTP_201_CREATED)
async def create_bed(
    data: BedCreate,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.admin)),
):
    department = await department_service.get_department_by_id(db, data.department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department not found",
        )

    existing = await bed_service.get_bed_by_label(db, data.department_id, data.bed_label)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bed with label '{data.bed_label}' already exists in this department",
        )

    bed = await bed_service.create_bed(db, data)
    return bed


@router.patch("/{bed_id}", response_model=BedResponse)
async def update_bed(
    bed_id: str,
    data: BedUpdate,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.nurse, Roles.admin)),
):
    bed = await bed_service.update_bed(db, bed_id, data)
    if not bed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bed not found",
        )
    return bed


@router.post("/{bed_id}/assign", response_model=BedResponse)
async def assign_patient_to_bed(
    bed_id: str,
    patient_id: str = Query(...),
    admission_id: Optional[str] = Query(None),
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.nurse, Roles.receptionist, Roles.admin)),
):
    bed = await bed_service.assign_patient_to_bed(db, bed_id, patient_id, admission_id)
    if not bed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bed not available for assignment or not found",
        )
    return bed


@router.post("/{bed_id}/release", response_model=BedResponse)
async def release_bed(
    bed_id: str,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.nurse, Roles.admin)),
):
    bed = await bed_service.release_bed(db, bed_id)
    if not bed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bed not found",
        )
    return bed


@router.post("/{bed_id}/cleaned", response_model=BedResponse)
async def mark_bed_cleaned(
    bed_id: str,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.nurse, Roles.admin)),
):
    bed = await bed_service.mark_bed_cleaned(db, bed_id)
    if not bed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bed not found or not in cleaning status",
        )
    return bed
