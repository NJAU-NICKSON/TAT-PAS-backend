from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.db.client import get_database
from app.security.rbac import require_roles, Roles, get_current_user
from app.models.consultation_room import (
    ConsultationRoomCreate,
    ConsultationRoomUpdate,
    ConsultationRoomResponse,
    ConsultationRoomWithOccupants,
)
from app.services import consultation_room_service

router = APIRouter(prefix="/consultation-rooms", tags=["consultation-rooms"])


# List consultation rooms.
@router.get("", response_model=List[ConsultationRoomWithOccupants])
async def list_rooms(
    department_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    return await consultation_room_service.get_all_rooms(
        db, department_id=department_id, status=status
    )


# Fetch one room by ID.
@router.get("/{room_id}", response_model=ConsultationRoomWithOccupants)
async def get_room(
    room_id: str,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    room = await consultation_room_service.get_room_by_id(db, room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


# Add a consultation room.
@router.post("", response_model=ConsultationRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    data: ConsultationRoomCreate,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.admin)),
):
    return await consultation_room_service.create_room(db, data)


# Update a consultation room.
@router.patch("/{room_id}", response_model=ConsultationRoomWithOccupants)
async def update_room(
    room_id: str,
    data: ConsultationRoomUpdate,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.nurse, Roles.receptionist, Roles.doctor, Roles.admin)),
):
    room = await consultation_room_service.update_room(db, room_id, data)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


# Remove a consultation room.
@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: str,
    db: AsyncDatabase = Depends(get_database),
    current_user=Depends(require_roles(Roles.admin)),
):
    deleted = await consultation_room_service.delete_room(db, room_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
