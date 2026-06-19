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


# Build the seed patients.
def build_patients():
    raw = [
        ("Mary",      "Njoki Kamau",      "1985-03-12", "female", "A+",  68, [{"substance":"Penicillin","severity":"severe"}],   ["Hypertension"],                     {}),
        ("John",      "Otieno Odhiambo",  "1972-07-22", "male",   "O+",  82, [],                                                ["Diabetes Type 2","Hypertension"],   {}),
        ("Fatuma",    "Abdi Hassan",      "1990-11-05", "female", "B+",  55, [{"substance":"Sulfonamides","severity":"moderate"}],[],                                    {"is_pregnant":True}),
        ("David",     "Muthoni Waweru",   "1965-01-30", "male",   "AB+", 90, [],                                                ["CKD Stage 3","Hypertension"],        {}),
        ("Grace",     "Akinyi Oloo",      "2018-06-14", "female", "O-",  22, [],                                                ["Asthma"],                            {"is_paediatric":True}),
        ("Samuel",    "Kiprop Bett",      "1958-09-08", "male",   "A-",  75, [{"substance":"Aspirin","severity":"mild"}],       ["COPD","Hypertension"],               {}),
        ("Amina",     "Wanjiku Ngugi",    "1995-04-20", "female", "B-",  60, [],                                                [],                                    {}),
        ("Peter",     "Maina Kariuki",    "1980-12-15", "male",   "O+",  78, [{"substance":"Penicillin","severity":"severe"},{"substance":"Sulfonamides","severity":"moderate"}], ["Diabetes Type 2"], {}),
        ("Esther",    "Chebet Rono",      "1988-08-03", "female", "A+",  65, [],                                                [],                                    {"is_pregnant":True}),
        ("Michael",   "Kamande Njoroge",  "2020-02-28", "male",   "B+",  14, [],                                                [],                                    {"is_paediatric":True,"is_neonate":False}),
        ("Rose",      "Auma Odongo",      "1970-05-17", "female", "O+",  70, [{"substance":"Morphine","severity":"severe"}],    ["Arthritis"],                         {}),
        ("James",     "Kiprotich Sang",   "1945-11-02", "male",   "AB-", 68, [],                                                ["Diabetes Type 2","Heart Failure","CKD"], {}),
        ("Lucy",      "Wambui Gichuki",   "2000-09-25", "female", "A+",  52, [],                                                [],                                    {}),
        ("Hassan",    "Omar Abdi",        "1978-03-11", "male",   "O-",  85, [{"substance":"Codeine","severity":"moderate"}],   ["Hypertension"],                      {}),
        ("Anne",      "Cherotich Korir",  "1992-07-07", "female", "B+",  58, [],                                                [],                                    {}),
        ("Stephen",   "Njuguna Mwangi",   "1955-12-20", "male",   "A+",  80, [],                                                ["COPD","Heart Failure"],              {}),
        ("Miriam",    "Atieno Ochieng",   "2021-04-10", "female", "O+",  11, [],                                                [],                                    {"is_paediatric":True,"is_neonate":False}),
        ("Daniel",    "Mutua Masila",     "1983-08-30", "male",   "B-",  74, [],                                                [],                                    {}),
        ("Josephine", "Nyambura Thuo",    "1968-06-15", "female", "A-",  63, [{"substance":"Penicillin","severity":"moderate"}],["Hypertension","Diabetes Type 2"],    {}),
        ("Brian",     "Omondi Oluoch",    "1998-01-22", "male",   "O+",  71, [],                                                [],                                    {}),
    ]

    phones = [
        "0712345678","0723456789","0734567890","0745678901","0756789012",
        "0767890123","0778901234","0789012345","0790123456","0701234567",
        "0711223344","0722334455","0733445566","0744556677","0755667788",
        "0766778899","0777889900","0788990011","0799001122","0710112233",
    ]
    cities = ["Nairobi"] * 20
    estates = ["Mwiki","Kasarani","Roysambu","Zimmerman","Githurai 45","Kahawa West",
               "Kahawa Sukari","Ruaraka","Clay City","Sunton","Hunters","Mwihoko",
               "Kahawa Wendani","Lucky Summer","Babadogo","Githurai 44","Mirema",
               "Thome","Garden Estate","Ridgeways"]
    kin_names = [
        "John Kamau","Mary Odhiambo","Ahmed Hassan","Jane Waweru","Patrick Oloo",
        "Mercy Bett","David Ngugi","Alice Kariuki","Simon Rono","Ruth Njoroge",
        "Paul Odongo","Hannah Sang","Mark Gichuki","Fatuma Abdi","Joseph Korir",
        "Beatrice Mwangi","Thomas Ochieng","Esther Masila","George Thuo","Lilian Oluoch",
    ]
    kin_rels = [
        "spouse","spouse","sibling","child","parent","sibling","spouse","sibling",
        "spouse","parent","child","sibling","spouse","sibling","spouse",
        "child","parent","spouse","child","sibling",
    ]

    patients = []
    patient_ids = []

    for i, (first, last, dob, gender, blood, weight, allergies, chronic, flags) in enumerate(raw):
        _id = oid()
        mrn = f"MRN-2024-{i+1:04d}"
        ins = {"provider": "SHA", "member_number": f"SHA{10000+i}", "is_active": True} if i % 2 == 0 else None

        dob_dt = datetime.strptime(dob, "%Y-%m-%d")
        age_years = (NOW - dob_dt).days // 365

        rec = {
            "_id": _id,
            "mrn": mrn,
            "first_name": first,
            "last_name": last,
            "dob": dob_dt,
            "gender": gender,
            "blood_group": blood,
            "weight_kg": weight,
            "allergies": allergies,
            "chronic_conditions": chronic,
            "contact": {
                "phone": phones[i],
                "email": f"{first.lower()}.{last.lower().replace(' ','.')}@gmail.com",
                "address": f"{estates[i]} Estate, P.O. Box {1000 + i * 7}, {cities[i]}",
                "city": cities[i],
            },
            "next_of_kin": {
                "name": kin_names[i],
                "relationship": kin_rels[i],
                "phone": phones[(i+3) % 20],
            },
            "created_at": dt(days=30 + i),
        }
        if ins:
            rec["insurance"] = ins

        if age_years >= 18:
            rec["national_id"] = str(20000000 + i)
        else:
            rec["guardian_national_id"] = str(30000000 + i)
            rec["guardian_name"] = kin_names[i]

        rec.update(flags)
        patients.append(rec)
        patient_ids.append(_id)

    return patients, patient_ids


# Build the seed visits.
def build_visits(patient_ids, dept_map, user_ids):
    doctors = user_ids["doctors"]
    nurses  = user_ids["nurses"]

    visits = []
    visit_ids = []
    vn = 1

    # Make a seed visit number.
    def vnum():
        nonlocal vn
        n = f"VN-2024-{vn:04d}"
        vn += 1
        return n

    # Make a set of seed triage vitals.
    def vitals(weight):
        return {
            "blood_pressure_systolic": 120,
            "blood_pressure_diastolic": 80,
            "temperature_celsius": 36.8,
            "pulse_rate": 78,
            "oxygen_saturation": 98,
            "weight_kg": weight,
            "respiratory_rate": 16,
        }

    weights = [68,82,55,90,22,75,60,78,65,14,70,68,52,85,58,80,11,74,63,71]
    complaints = [
        "Persistent headache and dizziness",
        "Elevated blood sugar and fatigue",
        "Nausea and lower abdominal pain",
        "Swollen ankles and reduced urine output",
        "Wheezing and shortness of breath",
        "Chronic cough and breathlessness",
        "Fever and sore throat",
        "Uncontrolled diabetes and blurred vision",
        "Back pain and contractions",
        "Persistent cough and fever",
        "Severe joint pain",
        "Chest pain and shortness of breath",
        "Abdominal cramps and diarrhoea",
        "Severe headache",
        "Menstrual cramps and lower back pain",
        "Progressive breathlessness",
        "High fever and irritability",
        "Lower back pain",
        "High blood pressure and headache",
        "Cough and chest tightness",
    ]
    diagnoses = [
        "Hypertensive urgency",
        "Uncontrolled Type 2 Diabetes Mellitus",
        "Threatened preterm labour",
        "Acute-on-chronic kidney disease",
        "Acute exacerbation of asthma",
        "Acute exacerbation of COPD",
        "Pharyngitis",
        "Diabetic ketoacidosis",
        "Preterm labour",
        "Upper respiratory tract infection",
        "Rheumatoid arthritis flare",
        "Decompensated heart failure",
        "Acute gastroenteritis",
        "Malignant hypertension",
        "Primary dysmenorrhoea",
        "Acute-on-chronic heart failure",
        "Febrile seizure",
        "Lumbar strain",
        "Hypertensive crisis with end-organ damage",
        "Bronchitis",
    ]

    status_plan = (
        ["registered"] * 5 +
        ["triaged"] * 3 +
        ["waiting_for_doctor"] * 4 +
        ["in_consultation"] * 3 +
        ["awaiting_results"] * 2 +
        ["treatment_in_progress"] * 3 +
        ["admitted", "in_ward"] +
        ["discharged"] * 5 +
        ["cancelled"] * 2 +
        ["ready_for_discharge"]
    )
    patient_visit_map = []
    for i in range(10):
        patient_visit_map.append(i)
        patient_visit_map.append(i)
    for i in range(10, 20):
        patient_visit_map.append(i)

    dept_codes = (["OPD"] * 18 + ["ED"] * 7 + ["GW"] * 5)[:30]
    visit_types_map = {"OPD": "opd", "ED": "emergency", "GW": "ipd"}

    triage_delay_indices = {0, 1, 2}
    doctor_wait_indices  = {3, 4, 5}
    emergency_priority   = {6, 7}

    for idx in range(30):
        _id = oid()
        p_idx = patient_visit_map[idx]
        pid = patient_ids[p_idx]
        status = status_plan[idx]
        dept_code = dept_codes[idx]
        dept_id = dept_map[dept_code]
        vtype = visit_types_map.get(dept_code, "opd")
        reg_at = dt(days=28 - idx % 28, hours=8)

        rec = {
            "_id": _id,
            "patient_id": sid(pid),
            "visit_number": vnum(),
            "visit_type": vtype,
            "department_id": sid(dept_id),
            "status": status,
            "registered_at": reg_at,
            "chief_complaint": complaints[p_idx],
            "created_at": reg_at,
        }

        if status not in ["registered", "cancelled"]:
            delay_min = 60 if idx in triage_delay_indices else 20
            triaged_at = reg_at + timedelta(minutes=delay_min)
            rec["triaged_at"] = triaged_at
            rec["triage_nurse_id"] = sid(nurses[idx % 3])
            rec["vitals"] = vitals(weights[p_idx])

            if status not in ["triaged"]:
                wait_min = 120 if idx in doctor_wait_indices else 40
                consult_start = triaged_at + timedelta(minutes=wait_min)
                rec["consultation_started_at"] = consult_start
                rec["assigned_doctor_id"] = sid(doctors[idx % 3])

                if status in ["in_consultation", "awaiting_results", "treatment_in_progress",
                               "admitted", "in_ward", "ready_for_discharge", "discharged"]:
                    rec["diagnosis"] = diagnoses[p_idx]

                if status in ["awaiting_results", "treatment_in_progress", "admitted", "in_ward",
                               "ready_for_discharge", "discharged"]:
                    consult_end = consult_start + timedelta(minutes=30)
                    rec["consultation_ended_at"] = consult_end

                if status in ["admitted", "in_ward"]:
                    rec["admitted_at"] = consult_start + timedelta(hours=2)

                if status == "discharged":
                    consult_end = consult_start + timedelta(minutes=30)
                    rec["consultation_ended_at"] = consult_end
                    rec["discharged_at"] = consult_end + timedelta(hours=4)
                    rec["billing_completed_at"] = consult_end + timedelta(hours=5)

        if idx in emergency_priority:
            rec["priority"] = "immediate"
            rec["visit_type"] = "emergency"

        rec["prescription_ids"] = []

        visits.append(rec)
        visit_ids.append(_id)

    return visits, visit_ids


# Build the seed prescriptions.
def build_prescriptions(patient_ids, visit_ids, visits, dept_map, user_ids):
    doctors    = user_ids["doctors"]
    pharmacist = user_ids["pharmacist"]

    rxs = []
    rx_ids = []
    rx_n = 1

    # Make a seed prescription number.
    def rxnum():
        nonlocal rx_n
        n = f"RX-2024-{rx_n:04d}"
        rx_n += 1
        return n

    # Make a seed medication line.
    def med(name, dose, route, freq, days, **kw):
        m = {"name": name, "dose": dose, "route": route, "frequency": freq, "duration_days": days}
        m.update(kw)
        return m

    status_plan = (
        ["draft"] * 2 +
        ["submitted"] * 4 +
        ["pending_amendment"] * 3 +
        ["flagged"] * 6 +
        ["verified"] * 5 +
        ["dispensed"] * 5 +
        ["administered"] * 3 +
        ["archived"] * 2
    )

    sources    = ["opd","opd","emergency","ipd","opd","opd","emergency","opd","maternity",
                  "paediatric","opd","ipd","opd","opd","opd","ipd","paediatric","opd","opd","opd",
                  "opd","opd","emergency","ipd","opd","opd","emergency","opd","maternity","paediatric"]
    priorities = ["routine","routine","stat","urgent","routine","routine","stat","urgent","urgent",
                  "stat","routine","urgent","routine","routine","routine","urgent","stat","routine",
                  "urgent","routine","routine","routine","stat","urgent","routine","routine","stat",
                  "urgent","urgent","stat"]

    sla_map = {"stat": 30, "urgent": 60, "routine": 120, "discharge": 90, "nicu": 45, "chemo": 60}

    sla_breach_indices = {17, 20, 22, 25, 28}

    high_dose_indices        = {6, 13, 19}
    allergy_match_indices    = {0, 7, 18}
    drug_interaction_indices = {3, 14}
    controlled_indices       = {10, 11}
    high_alert_indices       = {15, 16}

    meds_catalogue = [
        [med("Amoxicillin","500mg","oral","TDS",7)],
        [med("Metformin","500mg","oral","BD",30)],
        [med("Salbutamol","2.5mg","nebulisation","PRN",5)],
        [med("Lisinopril","10mg","oral","OD",30), med("Warfarin","5mg","oral","OD",30), med("Aspirin","300mg","oral","OD",30)],
        [med("Prednisolone","20mg","oral","OD",7)],
        [med("Omeprazole","20mg","oral","OD",14)],
        [med("Morphine","1500mg","iv","Q4H",3, is_controlled=True)],
        [med("Amoxicillin","500mg","oral","TDS",7)],
        [med("Salbutamol","2.5mg","nebulisation","Q6H",5), med("Prednisolone","10mg","oral","OD",3)],
        [med("Paracetamol","500mg","oral","QDS",5)],
        [med("Tramadol","100mg","oral","TDS",5, is_controlled=True)],
        [med("Morphine","10mg","iv","Q4H",3, is_controlled=True)],
        [med("Atorvastatin","40mg","oral","OD",30)],
        [med("Paracetamol","2000mg","oral","QDS",5)],
        [med("Warfarin","5mg","oral","OD",30), med("Aspirin","300mg","oral","OD",30)],
        [med("Heparin","5000IU","sc","BD",7, is_high_alert=True)],
        [med("Insulin","20IU","sc","OD",30, is_high_alert=True)],
        [med("Ibuprofen","400mg","oral","TDS",5)],
        [med("Amoxicillin","500mg","oral","TDS",7)],
        [med("Paracetamol","2000mg","oral","QDS",3)],
        [med("Metformin","1000mg","oral","BD",30)],
        [med("Lisinopril","5mg","oral","OD",30)],
        [med("Salbutamol","5mg","nebulisation","Q4H",3)],
        [med("Omeprazole","40mg","oral","OD",14)],
        [med("Atorvastatin","20mg","oral","OD",30)],
        [med("Amoxicillin","500mg","oral","TDS",7)],
        [med("Paracetamol","1g","iv","QDS",3)],
        [med("Metformin","500mg","oral","BD",30)],
        [med("Salbutamol","2.5mg","nebulisation","TDS",5)],
        [med("Prednisolone","5mg","oral","OD",7)],
    ]

    allergy_patient_map = {0: 0, 7: 7, 18: 18}

    for idx in range(30):
        _id = oid()
        status = status_plan[idx]
        vis = visits[idx]
        p_idx = idx % 20
        pid = patient_ids[p_idx]
        doctor_id = doctors[idx % 3]
        source = sources[idx]
        priority = priorities[idx]
        sla_thresh = sla_map.get(priority, 120)
        if "consultation_ended_at" in vis:
            ordered_at = vis["consultation_ended_at"]
        elif "consultation_started_at" in vis:
            ordered_at = vis["consultation_started_at"] + timedelta(minutes=25)
        elif "triaged_at" in vis:
            ordered_at = vis["triaged_at"] + timedelta(minutes=60)
        else:
            ordered_at = vis["registered_at"] + timedelta(minutes=90)

        flags = []
        if idx in high_dose_indices:
            flags.append("high_dose")
        if idx in allergy_match_indices:
            flags.append("allergy_match")
            pid = patient_ids[allergy_patient_map[idx]]
        if idx in drug_interaction_indices:
            flags.append("drug_interaction")
        if idx in controlled_indices:
            flags.append("controlled_substance")
        if idx in high_alert_indices:
            flags.append("high_alert")

        medications = meds_catalogue[idx]

        rec = {
            "_id": _id,
            "rx_number": rxnum(),
            "patient_id": sid(pid),
            "doctor_id": sid(doctor_id),
            "visit_id": sid(vis["_id"]),
            "department_id": sid(vis["department_id"]),
            "medications": medications,
            "status": status,
            "order_source": source,
            "priority": priority,
            "flags": flags,
            "sla_threshold_min": sla_thresh,
            "sla_breached": False,
            "notes": f"Prescribed for: {vis.get('chief_complaint','N/A')}",
            "ordered_at": ordered_at,
            "created_at": ordered_at,
            "updated_at": ordered_at,
        }

        if status in ["verified", "dispensed", "administered", "archived"]:
            o2s = 15 + (idx % 30)
            s2v = 25 + (idx % 90) if idx not in {5, 9, 12, 17, 22} else 130
            v2d = 10 + (idx % 20)
            d2a = 15 + (idx % 45) if status in ["administered", "archived"] else None
            flag_hold = (40 + idx * 3) if flags else 0

            tat_pharmacy = s2v + v2d
            tat_total = o2s + s2v + v2d + (d2a or 0) + flag_hold

            rec["tat_order_to_submit_min"]   = float(o2s)
            rec["tat_submit_to_verify_min"]  = float(s2v)
            rec["tat_verify_to_dispense_min"]= float(v2d)
            rec["tat_pharmacy_min"]          = float(tat_pharmacy)
            rec["tat_total_min"]             = float(tat_total)

            if flag_hold:
                rec["tat_flag_hold_min"] = float(flag_hold)
            if d2a:
                rec["tat_dispense_to_admin_min"] = float(d2a)

            if idx in sla_breach_indices:
                breach_dur = tat_pharmacy - sla_thresh
                if breach_dur > 0:
                    rec["sla_breached"] = True
                    rec["sla_breach_duration_min"] = float(breach_dur)
                    rec["tat_breached_at"] = ordered_at + timedelta(minutes=sla_thresh)

            submitted_at  = ordered_at + timedelta(minutes=o2s)
            verified_at   = submitted_at + timedelta(minutes=s2v)
            dispensed_at  = verified_at + timedelta(minutes=v2d)

            rec["submitted_at"] = submitted_at
            rec["verified_at"]  = verified_at
            rec["dispensed_at"] = dispensed_at
            rec["dispensed_by_id"] = sid(pharmacist)

            if d2a:
                rec["administered_at"]   = dispensed_at + timedelta(minutes=d2a)
                rec["administered_by_id"]= sid(user_ids["nurses"][idx % 3])

        elif status in ["submitted", "flagged", "pending_amendment"]:
            submitted_at = ordered_at + timedelta(minutes=15 + idx % 20)
            rec["submitted_at"] = submitted_at
            rec["tat_order_to_submit_min"] = float(15 + idx % 20)
            if flags:
                rec["tat_flag_hold_min"] = float(30 + idx * 2)

        if status in ["flagged", "pending_amendment"] and flags:
            rec["pharmacist_comment"] = "Flagged for clinical review - please verify before dispensing."

        rxs.append(rec)
        rx_ids.append(_id)

    return rxs, rx_ids


# Build the seed audit records.
def build_audit_records(rx_ids, rxs, user_ids):
    auditor    = user_ids["auditor"]
    pharmacist = user_ids["pharmacist"]

    records = []

    configs = [
        ("critical", "automated",     "high_dose",          "Morphine dose exceeds safe threshold",               "system",     True,  True),
        ("critical", "automated",     "allergy_match",       "Penicillin prescribed to patient with known allergy","system",     True,  True),
        ("critical", "sla_breach",    "sla_exceeded",        "Prescription TAT exceeded SLA by >60 minutes",       "system",     True,  False),
        ("critical", "manual",        "controlled_substance","Controlled substance dispensed without counter-sign", "auditor",    True,  True),
        ("critical", "automated",     "high_dose",          "Paracetamol 2000mg exceeds max daily dose",           "system",     False, False),

        ("high", "automated",     "drug_interaction",   "Warfarin + Aspirin: major bleeding risk",            "system",     True,  False),
        ("high", "automated",     "drug_interaction",   "Warfarin + Aspirin: INR monitoring required",        "system",     True,  True),
        ("high", "sla_breach",    "sla_exceeded",       "Urgent prescription exceeded 60-min SLA",            "system",     True,  False),
        ("high", "sla_breach",    "sla_exceeded",       "STAT prescription exceeded 30-min SLA",              "system",     False, False),
        ("high", "manual",        "high_alert",         "Heparin administered without weight-based check",    "pharmacist", True,  False),
        ("high", "automated",     "high_alert",         "Insulin prescribed without glucose check documented","system",     True,  False),
        ("high", "manual",        "allergy_match",      "Amoxicillin allergy cross-reactivity risk noted",    "auditor",    False, False),
        ("high", "sla_breach",    "sla_exceeded",       "Routine prescription TAT >2 hours",                  "system",     True,  False),

        ("medium", "automated",   "controlled_substance","Tramadol prescribed beyond standard duration",      "system",     True,  False),
        ("medium", "manual",      "underdose",           "Metformin dose below therapeutic range",            "auditor",    True,  False),
        ("medium", "sla_warning", "sla_approaching",    "Prescription approaching SLA threshold (75%)",       "system",     True,  False),
        ("medium", "sla_warning", "sla_approaching",    "Urgent order at 80% of SLA window",                  "system",     False, False),
        ("medium", "manual",      "incomplete_info",    "Missing diagnosis code on prescription",             "auditor",    True,  False),
        ("medium", "automated",   "duplicate_order",    "Possible duplicate order detected within 24h",       "system",     True,  False),
        ("medium", "sla_warning", "sla_approaching",    "STAT order nearing 30-min SLA boundary",             "system",     False, False),

        ("low", "status_change",  "status_update",      "Prescription status changed from verified to dispensed","system",  True,  False),
        ("low", "manual",         "note_added",         "Pharmacist added dispensing note",                   "pharmacist", True,  False),
        ("low", "automated",      "route_mismatch",     "IV route prescribed for outpatient setting",         "system",     True,  False),
        ("low", "automated",      "route_mismatch",     "Nebulisation ordered; confirm device availability",  "system",     False, False),
        ("low", "manual",         "general_review",     "Routine audit: all items reviewed and compliant",    "auditor",    True,  False),
    ]

    resolution_types = [
        "dose_adjusted", "prescription_cancelled", "accepted_risk", "drug_changed", "false_positive",
        "dose_adjusted", "accepted_risk", "accepted_risk", None, "drug_changed",
        "dose_adjusted", "drug_changed", "accepted_risk",
        "dose_adjusted", "dose_adjusted", "false_positive", None, "false_positive",
        "false_positive", None,
        "false_positive", "false_positive", "false_positive", None, "accepted_risk",
    ]

    recommendations = {
        "critical": "Immediate clinical review required. Escalate to prescribing physician and pharmacy lead.",
        "high":     "Review prescription with prescribing doctor. Document outcome and re-verify before dispensing.",
    }

    cs_idx = 0
    countersign_users = [user_ids["auditor"], user_ids["pharmacist"]]

    for i, (severity, atype, flag_code, issue, by_role, resolved, countersigned) in enumerate(configs):
        _id = oid()
        rx_obj = rxs[i % len(rxs)]
        rx_id  = rx_ids[i % len(rx_ids)]

        if by_role == "system":
            created_by = "system"
        elif by_role == "auditor":
            created_by = sid(auditor)
        else:
            created_by = sid(pharmacist)

        rec = {
            "_id": _id,
            "prescription_id": sid(rx_id),
            "visit_id": rx_obj.get("visit_id"),
            "patient_id": rx_obj.get("patient_id"),
            "flag_code": flag_code,
            "type": atype,
            "issue": issue,
            "severity": severity,
            "resolved": resolved,
            "created_by": created_by,
            "created_by_role": by_role,
            "created_at": rx_obj["created_at"] + timedelta(minutes=5 + i * 3),
        }

        if severity in ("critical", "high"):
            rec["recommendation"] = recommendations[severity]

        if resolved:
            rtype = resolution_types[i]
            rec["resolved_by"]       = sid(auditor)
            rec["resolved_at"]       = rec["created_at"] + timedelta(hours=2 + i % 12)
            rec["resolution_type"]   = rtype
            rec["resolution_note"]   = f"Issue reviewed and addressed. Action: {rtype or 'N/A'}."

        if countersigned:
            cs_user = countersign_users[cs_idx % 2]
            cs_idx += 1
            rec["countersigned"]      = True
            rec["countersigned_by"]   = sid(cs_user)
            rec["countersigned_at"]   = rec["created_at"] + timedelta(hours=3 + i % 8)
            rec["countersign_note"]   = "Countersigned following clinical review and dose verification."
        else:
            rec["countersigned"] = False

        records.append(rec)

    return records


# Build the seed bills.
def build_bills(visit_ids, visits):
    bills = []
    status_plan = ["paid","paid","paid","paid","paid",
                   "open","open","open","open",
                   "partially_paid","partially_paid","partially_paid",
                   "finalized","finalized",
                   "waived"]

    bill_n = 1
    # Make a seed bill number.
    def bnum():
        nonlocal bill_n
        n = f"BILL-2024-{bill_n:04d}"
        bill_n += 1
        return n

    line_sets = [
        [("consultation","OPD Consultation",1,800,800),("pharmacy","Amoxicillin 500mg x21",1,1200,1200)],
        [("consultation","Specialist Consultation",1,1500,1500),("lab","FBC + RFT",1,1800,1800),("pharmacy","Metformin 500mg x60",1,900,900)],
        [("consultation","Emergency Consultation",1,1200,1200),("procedure","IV Line Insertion",1,1500,1500),("pharmacy","IV Fluids + Drugs",1,2500,2500)],
        [("consultation","OPD Consultation",1,800,800),("pharmacy","Lisinopril 10mg x30",1,750,750),("lab","Renal Function Tests",1,1200,1200)],
        [("ward","General Ward - 2 Days",2,2500,5000),("pharmacy","IV Antibiotics",1,3000,3000),("procedure","Wound Dressing",2,800,1600)],
        [("consultation","OPD Consultation",1,500,500),("pharmacy","Salbutamol Inhaler",1,1800,1800)],
        [("consultation","Paediatric Consultation",1,800,800),("pharmacy","Prednisolone Syrup",1,600,600)],
        [("consultation","Emergency Consultation",1,1200,1200),("lab","Blood Glucose",1,400,400),("pharmacy","Insulin",1,2200,2200)],
        [("consultation","OPD Consultation",1,800,800),("radiology","Chest X-Ray",1,1500,1500)],
        [("consultation","OPD Consultation",1,500,500),("pharmacy","Paracetamol",1,300,300)],
        [("ward","ICU - 1 Day",1,4000,4000),("procedure","Central Line",1,8000,8000),("pharmacy","Morphine + Adjuncts",1,5000,5000)],
        [("ward","General Ward - 3 Days",3,2000,6000),("pharmacy","Oral Medications",1,1500,1500)],
        [("consultation","OPD Consultation",1,1000,1000),("lab","LFT + RFT",1,2000,2000)],
        [("consultation","OPD Consultation",1,800,800),("pharmacy","Atorvastatin 20mg",1,700,700)],
        [("consultation","Maternity Consultation",1,1500,1500),("procedure","Antenatal Ultrasound",1,2500,2500),("pharmacy","Antenatal Supplements",1,800,800)],
    ]

    payments_data = [
        [{"amount":2000,"method":"sha"},{"amount":1200,"method":"cash"}],
        [{"amount":4200,"method":"sha"}],
        [{"amount":5200,"method":"mpesa"}],
        [{"amount":2750,"method":"sha"},{"amount":500,"method":"cash"}],
        [{"amount":9600,"method":"sha"},{"amount":2600,"method":"card"}],
        None, None, None, None,
        [{"amount":3000,"method":"cash"}],
        [{"amount":5000,"method":"sha"}],
        [{"amount":4000,"method":"mpesa"}],
        None, None,
        [],
    ]

    for i in range(15):
        _id = oid()
        v_idx = i % len(visit_ids)
        vis = visits[v_idx]
        status = status_plan[i]
        lines_raw = line_sets[i]

        line_items = []
        subtotal = 0
        for cat, desc, qty, unit, total in lines_raw:
            line_items.append({
                "category": cat,
                "description": desc,
                "quantity": qty,
                "unit_price": float(unit),
                "total_price": float(total),
            })
            subtotal += total

        discount = subtotal if status == "waived" else 0
        total_amount = subtotal - discount

        rec = {
            "_id": _id,
            "bill_number": bnum(),
            "visit_id": sid(visit_ids[v_idx]),
            "visit_number": vis.get("visit_number",""),
            "patient_id": vis.get("patient_id",""),
            "status": status,
            "line_items": line_items,
            "subtotal": float(subtotal),
            "discount_amount": float(discount),
            "tax_amount": 0.0,
            "total_amount": float(total_amount),
            "created_at": vis["registered_at"] + timedelta(hours=5),
        }

        pmts_raw = payments_data[i]
        rec["payments"] = [
            {"amount": float(p["amount"]), "method": p["method"],
             "received_at": rec["created_at"] + timedelta(hours=1)}
            for p in pmts_raw
        ] if pmts_raw else []

        bills.append(rec)

    return bills


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

    # Build the tamper-evident hash chain for audit records using the same
    # function the live app uses, so /audits/verify-integrity recomputes the
    # identical hashes and reports the chain as intact.
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