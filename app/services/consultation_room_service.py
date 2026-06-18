from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.models.consultation_room import (
    ConsultationRoomCreate,
    ConsultationRoomUpdate,
    ConsultationRoomWithOccupants,
)


# Turn a room document's ObjectIds into strings.
def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    if doc.get("department_id"):
        doc["department_id"] = str(doc["department_id"]) if isinstance(doc["department_id"], ObjectId) else doc["department_id"]
    return doc


# Attach department, doctor, nurse, and patient names to rooms.
async def _enrich(db: AsyncDatabase, rooms: list[dict]) -> list[dict]:
    doctor_ids = {r["current_doctor_id"] for r in rooms if r.get("current_doctor_id")}
    nurse_ids = {r["current_nurse_id"] for r in rooms if r.get("current_nurse_id")}
    patient_ids = {r["current_patient_id"] for r in rooms if r.get("current_patient_id")}
    dept_ids = {r["department_id"] for r in rooms if r.get("department_id")}

    staff_ids = doctor_ids | nurse_ids
    staff_map: dict[str, str] = {}
    patient_map: dict[str, str] = {}
    dept_map: dict[str, str] = {}

    if dept_ids:
        docs = await db.departments.find(
            {"_id": {"$in": [ObjectId(i) for i in dept_ids if len(i) == 24]}},
            {"_id": 1, "name": 1},
        ).to_list(length=len(dept_ids))
        dept_map = {str(d["_id"]): d.get("name", "") for d in docs}

    if staff_ids:
        docs = await db.users.find(
            {"_id": {"$in": [ObjectId(i) for i in staff_ids if len(i) == 24]}},
            {"_id": 1, "full_name": 1},
        ).to_list(length=len(staff_ids))
        staff_map = {str(d["_id"]): d.get("full_name", "") for d in docs}

    if patient_ids:
        docs = await db.patients.find(
            {"_id": {"$in": [ObjectId(i) for i in patient_ids if len(i) == 24]}},
            {"_id": 1, "first_name": 1, "last_name": 1},
        ).to_list(length=len(patient_ids))
        patient_map = {str(p["_id"]): f"{p.get('first_name','')} {p.get('last_name','')}".strip() for p in docs}

    for room in rooms:
        room["department_name"] = dept_map.get(room.get("department_id", ""))
        room["current_doctor_name"] = staff_map.get(room.get("current_doctor_id", ""))
        room["current_nurse_name"] = staff_map.get(room.get("current_nurse_id", ""))
        room["current_patient_name"] = patient_map.get(room.get("current_patient_id", ""))

    return rooms


# List consultation rooms, optionally filtered.
async def get_all_rooms(
    db: AsyncDatabase,
    department_id: Optional[str] = None,
    status: Optional[str] = None,
) -> list[ConsultationRoomWithOccupants]:
    query: dict = {}
    if department_id:
        query["department_id"] = department_id
    if status:
        query["status"] = status

    cursor = db.consultation_rooms.find(query).sort("room_number", 1)
    docs = [_serialize(d) async for d in cursor]
    docs = await _enrich(db, docs)
    return [ConsultationRoomWithOccupants(**d) for d in docs]


# Fetch one consultation room by ID.
async def get_room_by_id(db: AsyncDatabase, room_id: str) -> Optional[ConsultationRoomWithOccupants]:
    if len(room_id) != 24:
        return None
    doc = await db.consultation_rooms.find_one({"_id": ObjectId(room_id)})
    if not doc:
        return None
    doc = _serialize(doc)
    docs = await _enrich(db, [doc])
    return ConsultationRoomWithOccupants(**docs[0])


# Add a new consultation room.
async def create_room(db: AsyncDatabase, data: ConsultationRoomCreate) -> ConsultationRoomWithOccupants:
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        **data.model_dump(),
        "created_at": now,
        "updated_at": None,
    }
    await db.consultation_rooms.insert_one(doc)
    doc = _serialize(doc)
    docs = await _enrich(db, [doc])
    return ConsultationRoomWithOccupants(**docs[0])


# Update a consultation room (status, occupants, notes).
async def update_room(
    db: AsyncDatabase,
    room_id: str,
    data: ConsultationRoomUpdate,
) -> Optional[ConsultationRoomWithOccupants]:
    if len(room_id) != 24:
        return None
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        return await get_room_by_id(db, room_id)
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db.consultation_rooms.find_one_and_update(
        {"_id": ObjectId(room_id)},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        return None
    result = _serialize(result)
    docs = await _enrich(db, [result])
    return ConsultationRoomWithOccupants(**docs[0])


# Remove a consultation room.
async def delete_room(db: AsyncDatabase, room_id: str) -> bool:
    if len(room_id) != 24:
        return False
    result = await db.consultation_rooms.delete_one({"_id": ObjectId(room_id)})
    return result.deleted_count > 0
