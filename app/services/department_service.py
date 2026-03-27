from datetime import datetime, timezone
from typing import Optional, List
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.models.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentInDB,
    DepartmentWithBedSummary,
)


def doc_to_department(doc: dict) -> DepartmentInDB:
    doc["id"] = str(doc["_id"])
    return DepartmentInDB(**doc)


async def get_all_departments(
    db: AsyncDatabase,
    is_active: Optional[bool] = None,
    type_filter: Optional[str] = None,
    floor: Optional[str] = None,
) -> List[DepartmentInDB]:
    query = {}
    if is_active is not None:
        query["is_active"] = is_active
    if type_filter:
        query["type"] = type_filter
    if floor:
        query["floor"] = floor

    cursor = db.departments.find(query).sort("name", 1)
    departments = []
    async for doc in cursor:
        departments.append(doc_to_department(doc))
    return departments


async def get_department_by_id(
    db: AsyncDatabase, department_id: str
) -> Optional[DepartmentInDB]:
    try:
        obj_id = ObjectId(department_id)
    except Exception:
        return None

    doc = await db.departments.find_one({"_id": obj_id})
    if not doc:
        return None
    return doc_to_department(doc)


async def get_department_by_code(
    db: AsyncDatabase, code: str
) -> Optional[DepartmentInDB]:
    doc = await db.departments.find_one({"code": code})
    if not doc:
        return None
    return doc_to_department(doc)


async def get_department_with_bed_summary(
    db: AsyncDatabase, department_id: str
) -> Optional[DepartmentWithBedSummary]:
    department = await get_department_by_id(db, department_id)
    if not department:
        return None

    pipeline = [
        {"$match": {"department_id": department_id}},
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
            }
        },
    ]

    status_counts = {}
    async for doc in await db.beds.aggregate(pipeline):
        status_counts[doc["_id"]] = doc["count"]

    total = sum(status_counts.values())
    available = status_counts.get("available", 0)
    occupied = status_counts.get("occupied", 0)
    reserved = status_counts.get("reserved", 0)
    cleaning = status_counts.get("cleaning", 0)
    maintenance = status_counts.get("maintenance", 0)

    return DepartmentWithBedSummary(
        **department.model_dump(),
        total_beds=total,
        available_beds=available,
        occupied_beds=occupied,
        reserved_beds=reserved,
        cleaning_beds=cleaning,
        maintenance_beds=maintenance,
    )


async def create_department(
    db: AsyncDatabase, data: DepartmentCreate
) -> DepartmentInDB:
    now = datetime.now(timezone.utc)
    doc = data.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = None

    result = await db.departments.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc_to_department(doc)


async def update_department(
    db: AsyncDatabase, department_id: str, data: DepartmentUpdate
) -> Optional[DepartmentInDB]:
    try:
        obj_id = ObjectId(department_id)
    except Exception:
        return None

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        return await get_department_by_id(db, department_id)

    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db.departments.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        return None
    return doc_to_department(result)


async def delete_department(db: AsyncDatabase, department_id: str) -> bool:
    try:
        obj_id = ObjectId(department_id)
    except Exception:
        return False

    result = await db.departments.delete_one({"_id": obj_id})
    return result.deleted_count > 0


async def get_departments_accepting_emergency(
    db: AsyncDatabase,
) -> List[DepartmentInDB]:
    cursor = db.departments.find({"accepts_emergency": True, "is_active": True})
    departments = []
    async for doc in cursor:
        departments.append(doc_to_department(doc))
    return departments
