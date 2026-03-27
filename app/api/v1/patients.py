from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pymongo.asynchronous.database import AsyncDatabase

from app.db.client import get_database
from app.models.patient import (
    PatientCreate,
    PatientResponse,
    PatientUpdate,
    PatientSearchResult,
)
from app.security.rbac import Roles, get_current_user, require_roles
from app.services import patient_service

router = APIRouter(prefix="/patients", tags=["patients"])


class AllergyRequest(BaseModel):
    substance: str
    reaction_type: Optional[str] = None
    severity: str = "moderate"


@router.get("", response_model=PatientSearchResult)
async def list_patients(
    q: str = Query("", description="Search by name, MRN, or phone"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    is_paediatric: Optional[bool] = Query(None),
    is_pregnant: Optional[bool] = Query(None),
    blood_group: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    return await patient_service.search_patients(
        db,
        query=q,
        skip=skip,
        limit=limit,
        is_paediatric=is_paediatric,
        is_pregnant=is_pregnant,
        blood_group=blood_group,
    )


@router.get("/all", response_model=List[PatientResponse])
async def get_all_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    return await patient_service.get_all_patients(db, skip=skip, limit=limit)


@router.get("/paediatric", response_model=List[PatientResponse])
async def get_paediatric_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    return await patient_service.get_paediatric_patients(db, skip=skip, limit=limit)


@router.get("/pregnant", response_model=List[PatientResponse])
async def get_pregnant_patients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    return await patient_service.get_pregnant_patients(db, skip=skip, limit=limit)


@router.get("/neonates", response_model=List[PatientResponse])
async def get_neonates(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    return await patient_service.get_neonates(db, skip=skip, limit=limit)


@router.get("/with-allergies", response_model=List[PatientResponse])
async def get_patients_with_allergies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    return await patient_service.get_patients_with_allergies(db, skip=skip, limit=limit)


@router.get("/mrn/{mrn}", response_model=PatientResponse)
async def get_patient_by_mrn(
    mrn: str,
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    patient = await patient_service.get_patient_by_mrn(db, mrn)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return patient


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    patient = await patient_service.get_patient_by_id(db, patient_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return patient


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_new_patient(
    body: PatientCreate,
    current_user=Depends(require_roles(Roles.receptionist, Roles.admin, Roles.nurse)),
    db: AsyncDatabase = Depends(get_database),
):
    if body.mrn:
        existing = await db.patients.find_one({"mrn": body.mrn})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="MRN already exists",
            )
    return await patient_service.create_patient(db, body, registered_by=current_user.id)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_existing_patient(
    patient_id: str,
    body: PatientUpdate,
    current_user=Depends(require_roles(Roles.receptionist, Roles.admin, Roles.nurse, Roles.doctor)),
    db: AsyncDatabase = Depends(get_database),
):
    updated = await patient_service.update_patient(db, patient_id, body)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return updated


@router.post("/{patient_id}/allergies", response_model=PatientResponse)
async def add_patient_allergy(
    patient_id: str,
    body: AllergyRequest,
    current_user=Depends(require_roles(
        Roles.receptionist, Roles.admin, Roles.doctor, Roles.nurse, Roles.pharmacist
    )),
    db: AsyncDatabase = Depends(get_database),
):
    patient = await patient_service.add_allergy(
        db,
        patient_id,
        substance=body.substance,
        reaction_type=body.reaction_type,
        severity=body.severity,
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return patient


@router.delete("/{patient_id}/allergies/{substance}", response_model=PatientResponse)
async def remove_patient_allergy(
    patient_id: str,
    substance: str,
    current_user=Depends(require_roles(
        Roles.receptionist, Roles.admin, Roles.doctor
    )),
    db: AsyncDatabase = Depends(get_database),
):
    patient = await patient_service.remove_allergy(db, patient_id, substance)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return patient


@router.get("/count/total")
async def get_patient_count(
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    count = await patient_service.count_patients(db)
    return {"total": count}


@router.get("/count/filtered")
async def get_patient_count_filtered(
    is_paediatric: Optional[bool] = Query(None),
    is_pregnant: Optional[bool] = Query(None),
    is_neonate: Optional[bool] = Query(None),
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    count = await patient_service.count_patients_by_filter(
        db,
        is_paediatric=is_paediatric,
        is_pregnant=is_pregnant,
        is_neonate=is_neonate,
    )
    return {"count": count}
