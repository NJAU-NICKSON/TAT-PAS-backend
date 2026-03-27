from datetime import datetime, timezone
from typing import Optional, List
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.models.bed import (
    BedCreate,
    BedUpdate,
    BedInDB,
    BedWithPatient,
    BedAvailabilitySummary,
)


def doc_to_bed(doc: dict) -> BedInDB:
    doc["id"] = str(doc["_id"])
    return BedInDB(**doc)


async def get_all_beds(
    db: AsyncDatabase,
    department_id: Optional[str] = None,
    status: Optional[str] = None,
    bed_type: Optional[str] = None,
    ward_name: Optional[str] = None,
) -> List[BedInDB]:
    query = {}
    if department_id:
        query["department_id"] = department_id
    if status:
        query["status"] = status
    if bed_type:
        query["bed_type"] = bed_type
    if ward_name:
        query["ward_name"] = ward_name

    cursor = db.beds.find(query).sort([("ward_name", 1), ("room_number", 1), ("bed_number", 1)])
    beds = []
    async for doc in cursor:
        beds.append(doc_to_bed(doc))
    return beds


async def get_bed_by_id(db: AsyncDatabase, bed_id: str) -> Optional[BedInDB]:
    try:
        obj_id = ObjectId(bed_id)
    except Exception:
        return None

    doc = await db.beds.find_one({"_id": obj_id})
    if not doc:
        return None
    return doc_to_bed(doc)


async def get_bed_by_label(
    db: AsyncDatabase, department_id: str, bed_label: str
) -> Optional[BedInDB]:
    doc = await db.beds.find_one({"department_id": department_id, "bed_label": bed_label})
    if not doc:
        return None
    return doc_to_bed(doc)


async def get_beds_by_department(
    db: AsyncDatabase, department_id: str
) -> List[BedWithPatient]:
    pipeline = [
        {"$match": {"department_id": department_id}},
        {
            "$lookup": {
                "from": "patients",
                "let": {"patient_id": {"$toObjectId": "$current_patient_id"}},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$patient_id"]}}},
                    {"$project": {"first_name": 1, "last_name": 1, "mrn": 1}},
                ],
                "as": "patient_info",
            }
        },
        {"$sort": {"ward_name": 1, "room_number": 1, "bed_number": 1}},
    ]

    beds = []
    async for doc in await db.beds.aggregate(pipeline):
        doc["id"] = str(doc["_id"])
        patient_info = doc.get("patient_info", [])
        if patient_info:
            p = patient_info[0]
            doc["patient_name"] = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            doc["patient_mrn"] = p.get("mrn")
        else:
            doc["patient_name"] = None
            doc["patient_mrn"] = None
        del doc["patient_info"]
        beds.append(BedWithPatient(**doc))
    return beds


async def create_bed(db: AsyncDatabase, data: BedCreate) -> BedInDB:
    now = datetime.now(timezone.utc)
    doc = data.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = None
    doc["last_cleaned_at"] = None

    result = await db.beds.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc_to_bed(doc)


async def update_bed(
    db: AsyncDatabase, bed_id: str, data: BedUpdate
) -> Optional[BedInDB]:
    try:
        obj_id = ObjectId(bed_id)
    except Exception:
        return None

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        return await get_bed_by_id(db, bed_id)

    update_data["updated_at"] = datetime.now(timezone.utc)

    if data.status == "available" and data.current_patient_id is None:
        update_data["current_patient_id"] = None
        update_data["current_admission_id"] = None

    result = await db.beds.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        return None
    return doc_to_bed(result)


async def assign_patient_to_bed(
    db: AsyncDatabase,
    bed_id: str,
    patient_id: str,
    admission_id: Optional[str] = None,
) -> Optional[BedInDB]:
    try:
        obj_id = ObjectId(bed_id)
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    update_data = {
        "status": "occupied",
        "current_patient_id": patient_id,
        "current_admission_id": admission_id,
        "updated_at": now,
    }

    result = await db.beds.find_one_and_update(
        {"_id": obj_id, "status": {"$in": ["available", "reserved"]}},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        return None
    return doc_to_bed(result)


async def release_bed(db: AsyncDatabase, bed_id: str) -> Optional[BedInDB]:
    try:
        obj_id = ObjectId(bed_id)
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    update_data = {
        "status": "cleaning",
        "current_patient_id": None,
        "current_admission_id": None,
        "updated_at": now,
    }

    result = await db.beds.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        return None
    return doc_to_bed(result)


async def mark_bed_cleaned(db: AsyncDatabase, bed_id: str) -> Optional[BedInDB]:
    try:
        obj_id = ObjectId(bed_id)
    except Exception:
        return None

    now = datetime.now(timezone.utc)
    update_data = {
        "status": "available",
        "last_cleaned_at": now,
        "updated_at": now,
    }

    result = await db.beds.find_one_and_update(
        {"_id": obj_id, "status": "cleaning"},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        return None
    return doc_to_bed(result)


async def get_bed_availability_summary(
    db: AsyncDatabase,
) -> List[BedAvailabilitySummary]:
    pipeline = [
        {
            "$group": {
                "_id": {
                    "department_id": "$department_id",
                    "status": "$status",
                },
                "count": {"$sum": 1},
            }
        },
        {
            "$group": {
                "_id": "$_id.department_id",
                "statuses": {
                    "$push": {
                        "status": "$_id.status",
                        "count": "$count",
                    }
                },
            }
        },
    ]

    department_stats = {}
    async for doc in await db.beds.aggregate(pipeline):
        dept_id = doc["_id"]
        stats = {"available": 0, "occupied": 0, "reserved": 0, "cleaning": 0, "maintenance": 0}
        for s in doc["statuses"]:
            stats[s["status"]] = s["count"]
        stats["total"] = sum(stats.values())
        department_stats[dept_id] = stats

    dept_cursor = db.departments.find(
        {"_id": {"$in": [ObjectId(d) for d in department_stats.keys()]}}
    )
    dept_map = {}
    async for d in dept_cursor:
        dept_map[str(d["_id"])] = {"name": d["name"], "code": d["code"]}

    summaries = []
    for dept_id, stats in department_stats.items():
        dept_info = dept_map.get(dept_id, {"name": "Unknown", "code": "UNK"})
        summaries.append(
            BedAvailabilitySummary(
                department_id=dept_id,
                department_name=dept_info["name"],
                department_code=dept_info["code"],
                **stats,
            )
        )

    summaries.sort(key=lambda x: x.department_name)
    return summaries


async def get_available_beds_by_type(
    db: AsyncDatabase, bed_type: str, department_id: Optional[str] = None
) -> List[BedInDB]:
    query = {"status": "available", "bed_type": bed_type}
    if department_id:
        query["department_id"] = department_id

    cursor = db.beds.find(query).sort([("ward_name", 1), ("room_number", 1)])
    beds = []
    async for doc in cursor:
        beds.append(doc_to_bed(doc))
    return beds


async def bulk_create_beds(db: AsyncDatabase, beds_data: List[BedCreate]) -> int:
    if not beds_data:
        return 0

    now = datetime.now(timezone.utc)
    docs = []
    for bed in beds_data:
        doc = bed.model_dump()
        doc["created_at"] = now
        doc["updated_at"] = None
        doc["last_cleaned_at"] = None
        docs.append(doc)

    result = await db.beds.insert_many(docs)
    return len(result.inserted_ids)
