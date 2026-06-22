"""
seed_simulation.py
Standalone simulation data seeder for the hospital TAT and Prescription Audit system.
Usage:
  python backend/seed_simulation.py           # seed if collections empty
  python backend/seed_simulation.py --fresh   # drop all docs and re-seed
"""

import os
import sys
from datetime import datetime, timedelta
from bson import ObjectId
from passlib.context import CryptContext
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("ERROR: MONGO_URI environment variable not set. Check backend/.env", file=sys.stderr)
    sys.exit(1)
MONGO_DB  = os.getenv("MONGO_DB", "tatpas")

pwd_ctx = CryptContext(schemes=["bcrypt"])

# Hash a seed password.
def hp(plain):
    return pwd_ctx.hash(plain)

NOW = datetime.utcnow()


# Return a naive UTC datetime offset from NOW going into the past.
def dt(days=0, hours=0, minutes=0):
    return NOW - timedelta(days=days, hours=hours, minutes=minutes)


# Make a fresh ObjectId.
def oid():
    return ObjectId()


# ObjectId → string.
def sid(o):
    return str(o)


# Build the seed staff accounts.
def build_users():
    users = []

    # Add one seed user.
    def u(username, password, full_name, role, email=None):
        _id = oid()
        users.append({
            "_id": _id,
            "username": username,
            "email": email or f"{username}@scionhospital.co.ke",
            "password_hash": hp(password),
            "role": role,
            "full_name": full_name,
            "is_active": True,
            "created_at": dt(days=60),
        })
        return _id

    admin_id        = u("admin",        "adminpass",       "Robert Njoroge",   "admin")
    receptionist_id = u("receptionist", "receptionpass",   "Alice Kamau",      "receptionist")
    pharmacist_id   = u("pharmacist",   "pharmpass",       "Kevin Oduya",      "pharmacist")
    billing_id      = u("billing",      "billingpass",     "Hellen Waweru",    "billing")
    auditor_id      = u("auditor",      "auditpass",       "Francis Muthui",   "auditor")
    doc1_id         = u("doctor1",      "doctor1pass",     "Dr. James Mwangi", "doctor")
    doc2_id         = u("doctor2",      "doctor2pass",     "Dr. Amina Hassan", "doctor")
    doc3_id         = u("doctor3",      "doctor3pass",     "Dr. Peter Otieno", "doctor")
    nurse1_id       = u("nurse1",       "nurse1pass",      "Grace Wanjiku",    "nurse")
    nurse2_id       = u("nurse2",       "nurse2pass",      "Samuel Kipchoge",  "nurse")
    nurse3_id       = u("nurse3",       "nurse3pass",      "Faith Achieng",    "nurse")

    return users, {
        "receptionist": receptionist_id,
        "admin": admin_id,
        "pharmacist": pharmacist_id,
        "billing": billing_id,
        "auditor": auditor_id,
        "doctors": [doc1_id, doc2_id, doc3_id],
        "nurses": [nurse1_id, nurse2_id, nurse3_id],
    }


# Build the seed departments.
def build_departments():
    depts = []
    dept_map = {}
    for name, code, dtype, floor in [
        ("Outpatient Department", "OPD",   "clinical",       "Ground"),
        ("Emergency Department",  "ED",    "clinical",       "Ground"),
        ("General Ward",          "GW",    "clinical",       "First"),
        ("Pharmacy",              "PHARM", "support",        "Ground"),
        ("ICU",                   "ICU",   "clinical",       "Second"),
    ]:
        _id = oid()
        depts.append({
            "_id": _id,
            "name": name,
            "code": code,
            "type": dtype,
            "floor": floor,
            "is_active": True,
            "created_at": dt(days=60),
        })
        dept_map[code] = _id
    return depts, dept_map


# Build the seed ward beds.
def build_beds(dept_map):
    beds = []
    bed_ids = {"GW": [], "ICU": [], "MAT": [], "PED": []}

    # Add one seed bed.
    def bed(dept_code, ward, room, num, label, btype, status):
        _id = oid()
        beds.append({
            "_id": _id,
            "department_id": sid(dept_map[dept_code]),
            "ward_name": ward,
            "room_number": room,
            "bed_number": num,
            "bed_label": label,
            "bed_type": btype,
            "status": status,
            "created_at": dt(days=60),
        })
        return _id

    gw_statuses  = ["available", "occupied", "occupied", "available", "occupied", "available"]
    icu_statuses = ["occupied", "available", "occupied"]

    for i, st in enumerate(gw_statuses, 1):
        bid = bed("GW", "General Ward", f"G{i:02d}", f"GW-{i:03d}", f"GW-{i:03d}", "general", st)
        bed_ids["GW"].append(bid)

    for i, st in enumerate(icu_statuses, 1):
        bid = bed("ICU", "Intensive Care Unit", f"I{i:02d}", f"ICU-{i:03d}", f"ICU-{i:03d}", "icu", st)
        bed_ids["ICU"].append(bid)

    for i in range(1, 4):
        bid = bed("GW", "Maternity Ward", f"M{i:02d}", f"MAT-{i:03d}", f"MAT-{i:03d}", "maternity", "available")
        bed_ids["MAT"].append(bid)

    for i in range(1, 4):
        bid = bed("GW", "Paediatric Ward", f"P{i:02d}", f"PED-{i:03d}", f"PED-{i:03d}", "paediatric", "available")
        bed_ids["PED"].append(bid)

    return beds, bed_ids


# Build the seed consultation rooms with doctor/nurse pairs.
def build_consultation_rooms(dept_map, user_ids):
    rooms = []
    doctors = user_ids["doctors"]
    nurses  = user_ids["nurses"]

    # Add one seed consultation room.
    def room(dept_code, number, name, floor, status, doctor_id=None, nurse_id=None, notes=None):
        rooms.append({
            "_id": oid(),
            "department_id": sid(dept_map[dept_code]),
            "room_number": number,
            "room_name": name,
            "floor": floor,
            "status": status,
            "current_doctor_id": sid(doctor_id) if doctor_id else None,
            "current_nurse_id": sid(nurse_id) if nurse_id else None,
            "current_patient_id": None,
            "notes": notes,
            "created_at": dt(days=60),
            "updated_at": None,
        })

    room("OPD", "OPD-CR-01", "Consultation Room 1", "G", "available", doctors[0], nurses[0])
    room("OPD", "OPD-CR-02", "Consultation Room 2", "G", "available", doctors[1], nurses[1])
    room("OPD", "OPD-CR-03", "Consultation Room 3", "G", "available", doctors[2], nurses[2])

    room("OPD", "OPD-CR-04", "Consultation Room 4", "G", "available", None, None, "Vacant - ready to assign a doctor and nurse")
    room("OPD", "OPD-CR-05", "Consultation Room 5", "G", "available", None, None, "Vacant - ready to assign a doctor and nurse")
    room("OPD", "OPD-CR-06", "Consultation Room 6", "G", "available", None, None, "Vacant - ready to assign a doctor and nurse")

    room("ED", "AE-CR-01", "Triage Room 1", "G", "available")
    room("ED", "AE-CR-02", "Triage Room 2", "G", "available")

    return rooms


# Populate the database with simulation data.
def seed(fresh=False):
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]

    collections = ["users","departments","beds","consultation_rooms","patients","visits",
                   "prescriptions","audit_records","bills"]

    if not fresh:
        non_empty = [c for c in collections if db[c].count_documents({}) > 0]
        if non_empty:
            print("Already seeded. Collections with data:", ", ".join(non_empty))
            print("Run with --fresh to drop and re-seed.")
            return

    if fresh:
        for c in collections:
            db[c].delete_many({})
        print("Cleared all simulation collections.\n")

    import seed_data

    users, user_ids            = build_users()
    departments, dept_map      = build_departments()
    beds, bed_ids              = build_beds(dept_map)
    consultation_rooms         = build_consultation_rooms(dept_map, user_ids)
    patients, patient_ids      = seed_data.build_patients()
    visits, visit_ids          = seed_data.build_visits(patient_ids, dept_map, user_ids, bed_ids)
    prescriptions, rx_ids      = seed_data.build_prescriptions(patient_ids, visit_ids, visits, dept_map, user_ids)
    audit_records              = seed_data.build_audit_records(rx_ids, prescriptions, user_ids)
    bills                      = seed_data.build_bills(visit_ids, visits)

    visit_rx_map = {}
    for rx in prescriptions:
        vid = rx.get("visit_id")
        if vid:
            visit_rx_map.setdefault(vid, []).append(rx["_id"])

    for v in visits:
        v_sid = sid(v["_id"])
        if v_sid in visit_rx_map:
            v["prescription_ids"] = [sid(r) for r in visit_rx_map[v_sid]]

    occupied_bed_ids = {v["bed_id"] for v in visits
                        if v.get("bed_id") and v["status"] in ("admitted", "in_ward", "ready_for_discharge")}
    bed_patient = {v["bed_id"]: v["patient_id"] for v in visits
                   if v.get("bed_id") and v["status"] in ("admitted", "in_ward", "ready_for_discharge")}
    for b in beds:
        bid = sid(b["_id"])
        if bid in occupied_bed_ids:
            b["status"] = "occupied"
            b["current_patient_id"] = bed_patient.get(bid)

    from app.services.audit_service import compute_record_hash, GENESIS_HASH
    audit_records.sort(key=lambda r: (r.get("created_at"), str(r["_id"])))
    prev_hash = GENESIS_HASH
    for rec in audit_records:
        rec["prev_hash"] = prev_hash
        rec["record_hash"] = compute_record_hash(rec, prev_hash)
        prev_hash = rec["record_hash"]

    results = {}
    for name, docs in [
        ("users",          users),
        ("departments",    departments),
        ("beds",           beds),
        ("consultation_rooms", consultation_rooms),
        ("patients",       patients),
        ("visits",         visits),
        ("prescriptions",  prescriptions),
        ("audit_records",  audit_records),
        ("bills",          bills),
    ]:
        if docs:
            r = db[name].insert_many(docs)
            results[name] = len(r.inserted_ids)
        else:
            results[name] = 0

    client.close()

    print("=" * 45)
    print(f"{'Collection':<20} {'Inserted':>10}")
    print("-" * 45)
    total = 0
    for name, count in results.items():
        print(f"{name:<20} {count:>10}")
        total += count
    print("-" * 45)
    print(f"{'TOTAL':<20} {total:>10}")
    print("=" * 45)
    print("Simulation data seeded successfully.")


if __name__ == "__main__":
    fresh_flag = "--fresh" in sys.argv
    seed(fresh=fresh_flag)