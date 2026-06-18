import re
from datetime import datetime, timezone, date
from typing import Optional, List
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException
from dateutil.relativedelta import relativedelta

from app.models.patient import (
    PatientCreate,
    PatientInDB,
    PatientUpdate,
    PatientResponse,
    PatientSummary,
    PatientSearchResult,
)


# Derive paediatric/neonate/adult flags from date of birth.
def _compute_age_flags(dob: Optional[datetime]) -> tuple[bool, bool]:
    if not dob:
        return False, False

    today = date.today()
    dob_date = dob.date() if isinstance(dob, datetime) else dob
    age_days = (today - dob_date).days
    age_years = relativedelta(today, dob_date).years

    is_neonate = age_days <= 28
    is_paediatric = age_years < 18

    return is_paediatric, is_neonate


# Convert a patient document to the full model.
def _doc_to_patient(doc: dict) -> PatientInDB:
    allergies = doc.get("allergies")
    if allergies:
        allergies = [a if isinstance(a, dict) else a for a in allergies]

    return PatientInDB(
        id=str(doc["_id"]),
        mrn=doc["mrn"],
        first_name=doc["first_name"],
        last_name=doc["last_name"],
        middle_name=doc.get("middle_name"),
        dob=doc.get("dob"),
        gender=doc.get("gender"),
        blood_group=doc.get("blood_group"),
        national_id=doc.get("national_id"),
        guardian_national_id=doc.get("guardian_national_id"),
        guardian_name=doc.get("guardian_name"),
        contact=doc.get("contact"),
        emergency_contact=doc.get("emergency_contact"),
        allergies=allergies,
        chronic_conditions=doc.get("chronic_conditions"),
        current_medications=doc.get("current_medications"),
        insurance=doc.get("insurance"),
        next_of_kin=doc.get("next_of_kin"),
        is_pregnant=doc.get("is_pregnant", False),
        is_paediatric=doc.get("is_paediatric", False),
        is_neonate=doc.get("is_neonate", False),
        registered_by=doc.get("registered_by"),
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at"),
    )


# Convert a patient document to the API response.
def _doc_to_response(doc: dict) -> PatientResponse:
    patient = _doc_to_patient(doc)
    return PatientResponse(**patient.model_dump())


# Convert a patient document to a list summary.
def _doc_to_summary(doc: dict) -> PatientSummary:
    allergies = doc.get("allergies", []) or []
    return PatientSummary(
        id=str(doc["_id"]),
        mrn=doc["mrn"],
        first_name=doc["first_name"],
        last_name=doc["last_name"],
        dob=doc.get("dob"),
        gender=doc.get("gender"),
        blood_group=doc.get("blood_group"),
        national_id=doc.get("national_id"),
        guardian_national_id=doc.get("guardian_national_id"),
        contact=doc.get("contact"),
        is_pregnant=doc.get("is_pregnant", False),
        is_paediatric=doc.get("is_paediatric", False),
        is_neonate=doc.get("is_neonate", False),
        allergies_count=len(allergies),
        has_allergies=len(allergies) > 0,
    )


# Produce the next medical record number.
async def generate_mrn(db: AsyncDatabase) -> str:
    today = datetime.now(timezone.utc)
    date_prefix = today.strftime("%Y%m%d")
    counter_id = f"mrn_{date_prefix}"

    for _ in range(20):
        result = await db.counters.find_one_and_update(
            {"_id": counter_id},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True,
        )
        seq = result["seq"]
        mrn = f"MRN-{date_prefix}-{seq:04d}"
        if not await db.patients.find_one({"mrn": mrn}):
            return mrn

    raise ValueError("Could not generate a unique MRN - too many patients registered today")


# Search patients by name, MRN, phone, or ID.
async def search_patients(
    db: AsyncDatabase,
    query: str = "",
    skip: int = 0,
    limit: int = 20,
    is_paediatric: Optional[bool] = None,
    is_pregnant: Optional[bool] = None,
    blood_group: Optional[str] = None,
) -> PatientSearchResult:
    filter_query: dict = {}

    if query:
        escaped = re.escape(query.strip())
        regex = {"$regex": escaped, "$options": "i"}
        filter_query["$or"] = [
            {"first_name": regex},
            {"last_name": regex},
            {"mrn": regex},
            {"contact.phone": regex},
        ]

    if is_paediatric is not None:
        filter_query["is_paediatric"] = is_paediatric

    if is_pregnant is not None:
        filter_query["is_pregnant"] = is_pregnant

    if blood_group:
        filter_query["blood_group"] = blood_group

    total = await db.patients.count_documents(filter_query)

    cursor = db.patients.find(filter_query).sort([("last_name", 1), ("first_name", 1)]).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)

    patients = [_doc_to_summary(doc) for doc in docs]

    return PatientSearchResult(
        patients=patients,
        total=total,
        page=(skip // limit) + 1 if limit > 0 else 1,
        page_size=limit,
    )


# List patients with paging.
async def get_all_patients(
    db: AsyncDatabase,
    skip: int = 0,
    limit: int = 50,
) -> List[PatientResponse]:
    cursor = db.patients.find().sort([("last_name", 1), ("first_name", 1)]).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_response(doc) for doc in docs]


# Fetch a patient by ID.
async def get_patient_by_id(
    db: AsyncDatabase, patient_id: str
) -> Optional[PatientResponse]:
    try:
        obj_id = ObjectId(patient_id)
    except Exception:
        return None

    doc = await db.patients.find_one({"_id": obj_id})
    if not doc:
        return None
    return _doc_to_response(doc)


# Fetch a patient by MRN.
async def get_patient_by_mrn(
    db: AsyncDatabase, mrn: str
) -> Optional[PatientResponse]:
    
    doc = await db.patients.find_one({"mrn": mrn})
    if not doc:
        return None
    return _doc_to_response(doc)


# Return an existing patient with the same National ID, or None.
async def find_id_duplicate(
    db: AsyncDatabase, patient: PatientCreate
) -> Optional[dict]:
    if patient.national_id and patient.national_id.strip():
        return await db.patients.find_one({"national_id": patient.national_id.strip()})
    return None


# Return an existing patient that looks like the same person, or None.
async def find_potential_duplicate(
    db: AsyncDatabase, patient: PatientCreate
) -> Optional[dict]:
    or_clauses: list[dict] = []

    if patient.first_name and patient.last_name:
        name_dob: dict = {
            "first_name": {"$regex": f"^{re.escape(patient.first_name.strip())}$", "$options": "i"},
            "last_name": {"$regex": f"^{re.escape(patient.last_name.strip())}$", "$options": "i"},
        }
        if patient.dob:
            name_dob["dob"] = patient.dob
        or_clauses.append(name_dob)

    phone = patient.contact.phone if patient.contact else None
    if phone and phone.strip():
        or_clauses.append({"contact.phone": phone.strip()})

    if not or_clauses:
        return None

    return await db.patients.find_one({"$or": or_clauses})


# Register a new patient, guarding against duplicates.
async def create_patient(
    db: AsyncDatabase,
    patient: PatientCreate,
    registered_by: Optional[str] = None,
    force: bool = False,
) -> PatientResponse:
    now = datetime.now(timezone.utc)

    id_dup = await find_id_duplicate(db, patient)
    if id_dup:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DUPLICATE_NATIONAL_ID",
                "message": (
                    f"National ID {patient.national_id} already belongs to "
                    f"'{id_dup.get('first_name','')} {id_dup.get('last_name','')}' "
                    f"(MRN {id_dup.get('mrn','')}). Open that record instead."
                ),
                "existing_patient_id": str(id_dup["_id"]),
                "existing_mrn": id_dup.get("mrn"),
            },
        )

    if not force:
        existing = await find_potential_duplicate(db, patient)
        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "POSSIBLE_DUPLICATE_PATIENT",
                    "message": (
                        f"A patient '{existing.get('first_name','')} {existing.get('last_name','')}' "
                        f"(MRN {existing.get('mrn','')}) already matches these details. "
                        "Open the existing record, or resubmit with force=true to register anyway."
                    ),
                    "existing_patient_id": str(existing["_id"]),
                    "existing_mrn": existing.get("mrn"),
                },
            )

    try:
        mrn = patient.mrn if patient.mrn else await generate_mrn(db)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    is_paediatric, is_neonate = _compute_age_flags(patient.dob)

    doc = {
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "middle_name": patient.middle_name,
        "dob": patient.dob,
        "gender": patient.gender,
        "blood_group": patient.blood_group,
        "national_id": patient.national_id,
        "guardian_national_id": patient.guardian_national_id,
        "guardian_name": patient.guardian_name,
        "contact": patient.contact.model_dump() if patient.contact else None,
        "emergency_contact": patient.emergency_contact.model_dump() if patient.emergency_contact else None,
        "allergies": [a.model_dump() for a in patient.allergies] if patient.allergies else None,
        "chronic_conditions": patient.chronic_conditions,
        "current_medications": patient.current_medications,
        "insurance": patient.insurance.model_dump() if patient.insurance else None,
        "next_of_kin": patient.next_of_kin.model_dump() if patient.next_of_kin else None,
        "is_pregnant": False,
        "is_paediatric": is_paediatric,
        "is_neonate": is_neonate,
        "registered_by": registered_by,
        "mrn": mrn,
        "created_at": now,
        "updated_at": None,
    }

    try:
        result = await db.patients.insert_one(doc)
    except DuplicateKeyError as exc:
        key = exc.details.get("keyPattern", {}) if exc.details else {}
        if "national_id" in key:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "DUPLICATE_NATIONAL_ID",
                    "message": f"National ID {patient.national_id} is already registered to another patient.",
                },
            )
        if "mrn" in key:
            raise HTTPException(status_code=409, detail=f"A patient with MRN '{mrn}' already exists")
        raise HTTPException(status_code=409, detail="Patient record already exists")
    doc["_id"] = result.inserted_id
    return _doc_to_response(doc)


# Update a patient's details.
async def update_patient(
    db: AsyncDatabase, patient_id: str, update: PatientUpdate
) -> Optional[PatientResponse]:
    try:
        obj_id = ObjectId(patient_id)
    except Exception:
        return None

    update_fields: dict = {}
    update_data = update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if value is not None:
            if key == "contact" and value:
                update_fields["contact"] = value
            elif key == "emergency_contact" and value:
                update_fields["emergency_contact"] = value
            elif key == "allergies" and value:
                update_fields["allergies"] = value
            elif key == "insurance" and value:
                update_fields["insurance"] = value
            elif key == "next_of_kin" and value:
                update_fields["next_of_kin"] = value
            else:
                update_fields[key] = value

    if "dob" in update_fields:
        is_paediatric, is_neonate = _compute_age_flags(update_fields["dob"])
        update_fields["is_paediatric"] = is_paediatric
        update_fields["is_neonate"] = is_neonate

    if not update_fields:
        doc = await db.patients.find_one({"_id": obj_id})
        if not doc:
            return None
        return _doc_to_response(doc)

    update_fields["updated_at"] = datetime.now(timezone.utc)

    result = await db.patients.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_fields},
        return_document=True,
    )
    if not result:
        return None
    return _doc_to_response(result)


# Add an allergy to a patient's record.
async def add_allergy(
    db: AsyncDatabase,
    patient_id: str,
    substance: str,
    reaction_type: Optional[str] = None,
    severity: str = "moderate",
) -> Optional[PatientResponse]:
    try:
        obj_id = ObjectId(patient_id)
    except Exception:
        return None

    allergy = {
        "substance": substance,
        "reaction_type": reaction_type,
        "severity": severity,
    }

    result = await db.patients.find_one_and_update(
        {"_id": obj_id},
        {
            "$push": {"allergies": allergy},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        return_document=True,
    )
    if not result:
        return None
    return _doc_to_response(result)


# Remove an allergy from a patient's record.
async def remove_allergy(
    db: AsyncDatabase,
    patient_id: str,
    substance: str,
) -> Optional[PatientResponse]:
    try:
        obj_id = ObjectId(patient_id)
    except Exception:
        return None

    result = await db.patients.find_one_and_update(
        {"_id": obj_id},
        {
            "$pull": {"allergies": {"substance": substance}},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        return_document=True,
    )
    if not result:
        return None
    return _doc_to_response(result)


# List patients who have recorded allergies.
async def get_patients_with_allergies(
    db: AsyncDatabase,
    skip: int = 0,
    limit: int = 50,
) -> List[PatientResponse]:
    cursor = db.patients.find(
        {"allergies": {"$exists": True, "$not": {"$size": 0}, "$ne": None}}
    ).sort([("last_name", 1)]).skip(skip).limit(limit)

    docs = await cursor.to_list(length=limit)
    return [_doc_to_response(doc) for doc in docs]


# List paediatric patients.
async def get_paediatric_patients(
    db: AsyncDatabase,
    skip: int = 0,
    limit: int = 50,
) -> List[PatientResponse]:
    cursor = db.patients.find({"is_paediatric": True}).sort([("last_name", 1)]).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_response(doc) for doc in docs]


# List pregnant patients.
async def get_pregnant_patients(
    db: AsyncDatabase,
    skip: int = 0,
    limit: int = 50,
) -> List[PatientResponse]:
    cursor = db.patients.find({"is_pregnant": True}).sort([("last_name", 1)]).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_response(doc) for doc in docs]


# List neonatal patients.
async def get_neonates(
    db: AsyncDatabase,
    skip: int = 0,
    limit: int = 50,
) -> List[PatientResponse]:
    cursor = db.patients.find({"is_neonate": True}).sort([("created_at", -1)]).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_response(doc) for doc in docs]


# Total number of patients.
async def count_patients(db: AsyncDatabase) -> int:
    return await db.patients.count_documents({})


# Count patients matching a filter.
async def count_patients_by_filter(
    db: AsyncDatabase,
    is_paediatric: Optional[bool] = None,
    is_pregnant: Optional[bool] = None,
    is_neonate: Optional[bool] = None,
) -> int:
    query = {}
    if is_paediatric is not None:
        query["is_paediatric"] = is_paediatric
    if is_pregnant is not None:
        query["is_pregnant"] = is_pregnant
    if is_neonate is not None:
        query["is_neonate"] = is_neonate

    return await db.patients.count_documents(query)
