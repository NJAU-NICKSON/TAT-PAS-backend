from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.db.client import get_database
from app.security.rbac import require_roles, Roles, get_current_user
from app.models.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    DepartmentWithBedSummary,
)
from app.services import department_service

router = APIRouter(prefix="/departments", tags=["departments"])


# List departments.
@router.get("", response_model=List[DepartmentResponse])
async def list_departments(
    is_active: Optional[bool] = Query(None),
    type_filter: Optional[str] = Query(None, alias="type"),
    floor: Optional[str] = Query(None),
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    departments = await department_service.get_all_departments(
        db, is_active=is_active, type_filter=type_filter, floor=floor
    )
    return departments


# List departments that accept emergencies.
@router.get("/emergency", response_model=List[DepartmentResponse])
async def list_emergency_departments(
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    departments = await department_service.get_departments_accepting_emergency(db)
    return departments


# Fetch one department by ID.
@router.get("/{department_id}", response_model=DepartmentWithBedSummary)
async def get_department(
    department_id: str,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    department = await department_service.get_department_with_bed_summary(db, department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    return department


# Add a department.
@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    data: DepartmentCreate,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.admin)),
):
    existing = await department_service.get_department_by_code(db, data.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with code '{data.code}' already exists",
        )
    department = await department_service.create_department(db, data)
    return department


# Update a department.
@router.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: str,
    data: DepartmentUpdate,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.admin)),
):
    department = await department_service.update_department(db, department_id, data)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    return department


# Remove a department.
@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: str,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.admin)),
):
    success = await department_service.delete_department(db, department_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )
    return None
