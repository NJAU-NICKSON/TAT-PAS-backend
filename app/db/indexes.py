from pymongo.asynchronous.database import AsyncDatabase
from pymongo import ASCENDING, DESCENDING, TEXT

# Create all indexes idempotently - only creates if not already present.
async def create_indexes(db: AsyncDatabase) -> None:

    # Check if an index with the exact key pattern exists (ignoring name).
    async def index_exists(collection, keys):
        existing = await collection.index_information()
        for idx_name, idx_info in existing.items():
            if idx_name == "_id_":
                continue
            if idx_info.get("key") == keys:
                return True
        return False

    collection = db.users
    if not await index_exists(collection, [("username", ASCENDING)]):
        await collection.create_index("username", unique=True)
    if not await index_exists(collection, [("email", ASCENDING)]):
        await collection.create_index("email", unique=True)
    if not await index_exists(collection, [("role", ASCENDING)]):
        await collection.create_index("role")
    if not await index_exists(collection, [("department_id", ASCENDING)]):
        await collection.create_index("department_id", sparse=True)

    collection = db.departments
    if not await index_exists(collection, [("code", ASCENDING)]):
        await collection.create_index("code", unique=True)
    if not await index_exists(collection, [("type", ASCENDING)]):
        await collection.create_index("type")
    if not await index_exists(collection, [("floor", ASCENDING)]):
        await collection.create_index("floor")
    if not await index_exists(collection, [("is_active", ASCENDING)]):
        await collection.create_index("is_active")
    if not await index_exists(collection, [("accepts_emergency", ASCENDING)]):
        await collection.create_index("accepts_emergency")

    collection = db.beds
    if not await index_exists(collection, [("department_id", ASCENDING)]):
        await collection.create_index("department_id")
    if not await index_exists(collection, [("status", ASCENDING)]):
        await collection.create_index("status")
    if not await index_exists(collection, [("bed_type", ASCENDING)]):
        await collection.create_index("bed_type")
    if not await index_exists(collection, [("ward_name", ASCENDING)]):
        await collection.create_index("ward_name")
    if not await index_exists(collection, [("department_id", ASCENDING), ("bed_label", ASCENDING)]):
        await collection.create_index([("department_id", ASCENDING), ("bed_label", ASCENDING)], unique=True)
    if not await index_exists(collection, [("current_patient_id", ASCENDING)]):
        await collection.create_index("current_patient_id", sparse=True)

    collection = db.patients
    if not await index_exists(collection, [("mrn", ASCENDING)]):
        await collection.create_index("mrn", unique=True)
    # Unique only when national_id is a real string; a sparse index still collides on explicit nulls (minors).
    nid_info = (await collection.index_information())
    nid_existing = next((i for n, i in nid_info.items() if i.get("key") == [("national_id", ASCENDING)]), None)
    if nid_existing and "partialFilterExpression" not in nid_existing:
        await collection.drop_index(next(n for n, i in nid_info.items() if i.get("key") == [("national_id", ASCENDING)]))
        nid_existing = None
    if not nid_existing:
        await collection.create_index(
            "national_id",
            unique=True,
            partialFilterExpression={"national_id": {"$type": "string"}},
            name="national_id_unique",
        )
    if not await index_exists(collection, [("guardian_national_id", ASCENDING)]):
        await collection.create_index("guardian_national_id", sparse=True)
    if not await index_exists(collection, [("last_name", ASCENDING), ("first_name", ASCENDING)]):
        await collection.create_index([("last_name", ASCENDING), ("first_name", ASCENDING)])
    if not await index_exists(collection, [("contact.phone", ASCENDING)]):
        await collection.create_index("contact.phone", sparse=True)
    if not await index_exists(collection, [("dob", ASCENDING)]):
        await collection.create_index("dob", sparse=True)
    if not await index_exists(collection, [("is_paediatric", ASCENDING)]):
        await collection.create_index("is_paediatric")
    if not await index_exists(collection, [("is_pregnant", ASCENDING)]):
        await collection.create_index("is_pregnant")
    if not await index_exists(collection, [("is_neonate", ASCENDING)]):
        await collection.create_index("is_neonate")
    if not await index_exists(collection, [("blood_group", ASCENDING)]):
        await collection.create_index("blood_group", sparse=True)
   
    try:
        await collection.create_index([("first_name", TEXT), ("last_name", TEXT), ("mrn", TEXT)], name="patients_text_search")
    except Exception as e:
        print(f"Warning: could not create text index on patients: {e}")

    collection = db.prescriptions
    if not await index_exists(collection, [("patient_id", ASCENDING)]):
        await collection.create_index("patient_id")
    if not await index_exists(collection, [("doctor_id", ASCENDING)]):
        await collection.create_index("doctor_id")
    if not await index_exists(collection, [("status", ASCENDING)]):
        await collection.create_index("status")
    if not await index_exists(collection, [("ordered_at", DESCENDING)]):
        await collection.create_index([("ordered_at", DESCENDING)])
    if not await index_exists(collection, [("status", ASCENDING), ("ordered_at", DESCENDING)]):
        await collection.create_index([("status", ASCENDING), ("ordered_at", DESCENDING)])
    if not await index_exists(collection, [("flags", ASCENDING)]):
        await collection.create_index("flags", sparse=True)
    if not await index_exists(collection, [("visit_id", ASCENDING)]):
        await collection.create_index("visit_id", sparse=True)
    if not await index_exists(collection, [("rx_number", ASCENDING)]):
        await collection.create_index("rx_number", unique=True, sparse=True)
    if not await index_exists(collection, [("priority", ASCENDING)]):
        await collection.create_index("priority")
    if not await index_exists(collection, [("sla_breached", ASCENDING)]):
        await collection.create_index("sla_breached")
    if not await index_exists(collection, [("priority", ASCENDING), ("submitted_at", ASCENDING)]):
        await collection.create_index([("priority", ASCENDING), ("submitted_at", ASCENDING)])

    collection = db.audit_records
    if not await index_exists(collection, [("prescription_id", ASCENDING)]):
        await collection.create_index("prescription_id")
    if not await index_exists(collection, [("resolved", ASCENDING)]):
        await collection.create_index("resolved")
    if not await index_exists(collection, [("severity", ASCENDING)]):
        await collection.create_index("severity")
    if not await index_exists(collection, [("created_at", DESCENDING)]):
        await collection.create_index([("created_at", DESCENDING)])
    if not await index_exists(collection, [("prescription_id", ASCENDING), ("resolved", ASCENDING)]):
        await collection.create_index([("prescription_id", ASCENDING), ("resolved", ASCENDING)])
    if not await index_exists(collection, [("type", ASCENDING)]):
        await collection.create_index("type")
    if not await index_exists(collection, [("flag_code", ASCENDING)]):
        await collection.create_index("flag_code")
    if not await index_exists(collection, [("original_flag_id", ASCENDING)]):
        await collection.create_index("original_flag_id", sparse=True)
    if not await index_exists(collection, [("type", ASCENDING), ("original_flag_id", ASCENDING)]):
        await collection.create_index([("type", ASCENDING), ("original_flag_id", ASCENDING)], sparse=True)
    if not await index_exists(collection, [("is_security_event", ASCENDING)]):
        await collection.create_index("is_security_event")
    if not await index_exists(collection, [("is_security_event", ASCENDING), ("reviewed_at", ASCENDING)]):
        await collection.create_index([("is_security_event", ASCENDING), ("reviewed_at", ASCENDING)])

    collection = db.sla_config
    if not await index_exists(collection, [("priority", ASCENDING)]):
        await collection.create_index("priority", unique=True)

    collection = db.dose_limits
    if not await index_exists(collection, [("drug", ASCENDING)]):
        await collection.create_index("drug", unique=True)

    collection = db.activity_log
    if not await index_exists(collection, [("created_at", DESCENDING)]):
        await collection.create_index([("created_at", DESCENDING)], name="activity_created")
    if not await index_exists(collection, [("user_id", ASCENDING)]):
        await collection.create_index("user_id", name="activity_user")

    collection = db.price_catalogue
    if not await index_exists(collection, [("code", ASCENDING)]):
        await collection.create_index("code", unique=True)

    collection = db.daily_reports
    if not await index_exists(collection, [("date", ASCENDING)]):
        await collection.create_index([("date", ASCENDING)], unique=True)

    collection = db.visits
    if not await index_exists(collection, [("visit_number", ASCENDING)]):
        await collection.create_index("visit_number", unique=True, name="visits_number_unique")
    if not await index_exists(collection, [("patient_id", ASCENDING)]):
        await collection.create_index("patient_id", name="visits_patient")
    if not await index_exists(collection, [("status", ASCENDING)]):
        await collection.create_index("status", name="visits_status")
    if not await index_exists(collection, [("visit_type", ASCENDING)]):
        await collection.create_index("visit_type", name="visits_type")
    if not await index_exists(collection, [("department_id", ASCENDING)]):
        await collection.create_index("department_id", name="visits_department")
    if not await index_exists(collection, [("registered_at", DESCENDING)]):
        await collection.create_index([("registered_at", DESCENDING)], name="visits_registered_desc")
    if not await index_exists(collection, [("assigned_doctor_id", ASCENDING)]):
        await collection.create_index("assigned_doctor_id", sparse=True, name="visits_doctor")

    collection = db.bills
    if not await index_exists(collection, [("visit_id", ASCENDING)]):
        await collection.create_index("visit_id", unique=True, name="bills_visit_unique")
    if not await index_exists(collection, [("patient_id", ASCENDING)]):
        await collection.create_index("patient_id", name="bills_patient")
    if not await index_exists(collection, [("status", ASCENDING)]):
        await collection.create_index("status", name="bills_status")
    if not await index_exists(collection, [("created_at", DESCENDING)]):
        await collection.create_index([("created_at", DESCENDING)], name="bills_created_desc")