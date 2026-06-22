
import random
from datetime import datetime, timedelta
from bson import ObjectId

random.seed(2026)

NOW = datetime.utcnow()
# Window spans roughly April-June so all three recent months are represented.
WINDOW_DAYS = 83


def oid():
    return ObjectId()


def sid(o):
    return str(o)


PEOPLE = [
    ("Mary", "Wanjiru Kamau", "1985-03-12", "female", "A+", 68, ["Penicillin:severe"], ["Hypertension"]),
    ("John", "Otieno Odhiambo", "1972-07-22", "male", "O+", 82, [], ["Diabetes Type 2", "Hypertension"]),
    ("Faith", "Chebet Korir", "1990-11-05", "female", "B+", 58, ["Sulfonamides:moderate"], []),
    ("David", "Mwangi Waweru", "1965-01-30", "male", "AB+", 90, [], ["CKD Stage 3", "Hypertension"]),
    ("Grace", "Akinyi Oloo", "2018-06-14", "female", "O-", 22, [], ["Asthma"]),
    ("Samuel", "Kiprop Bett", "1958-09-08", "male", "A-", 75, ["Aspirin:mild"], ["COPD", "Hypertension"]),
    ("Mercy", "Wanjiku Ngugi", "1995-04-20", "female", "B-", 60, [], []),
    ("Peter", "Maina Kariuki", "1980-12-15", "male", "O+", 78, ["Penicillin:severe", "Sulfonamides:moderate"], ["Diabetes Type 2"]),
    ("Esther", "Jepkemboi Rono", "1989-08-03", "female", "A+", 65, [], []),
    ("Brian", "Kamau Njoroge", "2020-02-28", "male", "B+", 14, [], []),
    ("Rose", "Auma Odongo", "1970-05-17", "female", "O+", 70, ["Morphine:severe"], ["Arthritis"]),
    ("James", "Kiprotich Sang", "1945-11-02", "male", "AB-", 68, [], ["Diabetes Type 2", "Heart Failure", "CKD"]),
    ("Lucy", "Wambui Gichuki", "2000-09-25", "female", "A+", 52, [], []),
    ("Hassan", "Omar Noor", "1978-03-11", "male", "O-", 85, ["Codeine:moderate"], ["Hypertension"]),
    ("Anne", "Cherono Korir", "1992-07-07", "female", "B+", 58, [], []),
    ("Stephen", "Njuguna Mwangi", "1955-12-20", "male", "A+", 80, [], ["COPD", "Heart Failure"]),
    ("Miriam", "Atieno Ochieng", "2021-04-10", "female", "O+", 11, [], []),
    ("Daniel", "Mutua Musyoka", "1983-08-30", "male", "B-", 74, [], []),
    ("Josephine", "Nyambura Thuo", "1968-06-15", "female", "A-", 63, ["Penicillin:moderate"], ["Hypertension", "Diabetes Type 2"]),
    ("Kevin", "Omondi Oluoch", "1998-01-22", "male", "O+", 71, [], []),
    ("Catherine", "Njeri Kimani", "1976-10-04", "female", "A+", 66, [], ["Hypertension"]),
    ("Patrick", "Kibet Langat", "1987-02-19", "male", "B+", 79, ["Latex:mild"], []),
    ("Susan", "Adhiambo Were", "1993-06-28", "female", "O-", 57, [], []),
    ("George", "Muriithi Karanja", "1962-09-13", "male", "AB+", 88, [], ["Diabetes Type 2", "Hypertension"]),
    ("Janet", "Wairimu Macharia", "2019-11-30", "female", "A+", 18, [], ["Asthma"]),
    ("Robert", "Onyango Ouma", "1971-05-06", "male", "O+", 81, [], ["Hypertension"]),
    ("Nancy", "Chepkoech Ruto", "1996-03-17", "female", "B-", 59, [], []),
    ("Joseph", "Wekesa Barasa", "1959-07-24", "male", "A-", 77, ["Iodine:moderate"], ["COPD"]),
    ("Beatrice", "Moraa Nyaboke", "1984-12-09", "female", "O+", 64, [], []),
    ("Charles", "Gitonga Mwangi", "1950-08-21", "male", "AB-", 70, [], ["Heart Failure", "CKD"]),
    ("Sarah", "Nasimiyu Wafula", "2017-01-15", "female", "A+", 24, [], []),
    ("Anthony", "Kiplagat Cheruiyot", "1981-04-03", "male", "O-", 83, [], []),
    ("Eunice", "Wangari Ndungu", "1973-11-11", "female", "B+", 61, ["Penicillin:moderate"], ["Hypertension"]),
    ("Vincent", "Odhiambo Owino", "1990-02-26", "male", "A+", 76, [], []),
    ("Lydia", "Jelagat Kosgei", "1986-09-02", "female", "O+", 60, [], []),
    ("Francis", "Njoroge Kibe", "1967-06-19", "male", "B-", 84, ["Aspirin:moderate"], ["Diabetes Type 2"]),
    ("Pauline", "Achieng Otieno", "1994-10-27", "female", "A-", 56, [], []),
    ("Dennis", "Mutiso Kioko", "2016-05-08", "male", "O+", 27, [], []),
    ("Caroline", "Wanjala Simiyu", "1979-03-14", "female", "B+", 62, [], ["Hypertension"]),
    ("Martin", "Kiptoo Tanui", "1963-12-01", "male", "AB+", 86, [], ["COPD", "Hypertension"]),
    ("Joyce", "Nduta Kamau", "1991-07-30", "female", "O-", 58, [], []),
    ("Edwin", "Ochieng Aluoch", "1988-01-09", "male", "A+", 80, [], []),
    ("Agnes", "Wambui Kago", "1957-04-22", "female", "B+", 67, ["Sulfonamides:mild"], ["Arthritis", "Hypertension"]),
    ("Collins", "Kemboi Rotich", "1997-08-16", "male", "O+", 73, [], []),
    ("Veronica", "Anyango Okoth", "1982-11-25", "female", "A+", 63, [], ["Diabetes Type 2"]),
]

NAIROBI_ESTATES = [
    "Mwiki", "Kasarani", "Roysambu", "Zimmerman", "Githurai 45", "Kahawa West",
    "Kahawa Sukari", "Ruaraka", "Clay City", "Sunton", "Hunters", "Mwihoko",
    "Kahawa Wendani", "Lucky Summer", "Babadogo", "Githurai 44", "Mirema",
    "Thome", "Garden Estate", "Ridgeways", "Maziwa", "Marurui", "Njathaini",
]

KIN_FIRST = ["John", "Mary", "Peter", "Jane", "Paul", "Mercy", "David", "Alice",
             "Simon", "Ruth", "James", "Hannah", "Mark", "Faith", "Joseph",
             "Beatrice", "Thomas", "Esther", "George", "Lilian", "Daniel", "Nancy"]
KIN_RELS = ["spouse", "parent", "sibling", "child"]


def _phone(i):
    return f"07{(10000000 + i * 137911) % 100000000:08d}"


def build_patients():
    patients = []
    patient_ids = []

    for i, (first, last, dob, gender, blood, weight, allergy_codes, chronic) in enumerate(PEOPLE):
        _id = oid()
        dob_dt = datetime.strptime(dob, "%Y-%m-%d")
        age = (NOW - dob_dt).days // 365

        allergies = []
        for code in allergy_codes:
            sub, sev = code.split(":")
            allergies.append({"substance": sub, "severity": sev})

        estate = NAIROBI_ESTATES[i % len(NAIROBI_ESTATES)]
        kin_name = f"{KIN_FIRST[i % len(KIN_FIRST)]} {last.split()[-1]}"

        rec = {
            "_id": _id,
            "mrn": f"MRN-2026-{i + 1:04d}",
            "first_name": first,
            "last_name": last,
            "dob": dob_dt,
            "gender": gender,
            "blood_group": blood,
            "weight_kg": weight,
            "allergies": allergies,
            "chronic_conditions": chronic,
            "contact": {
                "phone": _phone(i),
                "email": f"{first.lower()}.{last.split()[-1].lower()}@gmail.com",
                "address": f"{estate}, P.O. Box {1000 + i * 7}, Nairobi",
                "city": "Nairobi",
            },
            "next_of_kin": {
                "name": kin_name,
                "relationship": KIN_RELS[i % len(KIN_RELS)],
                "phone": _phone(i + 5),
            },
            # Patient records created within the 2-month window, spread across it.
            "created_at": NOW - timedelta(days=(i % WINDOW_DAYS), hours=random.randint(0, 23)),
        }

        if i % 2 == 0:
            rec["insurance"] = {"provider": "SHA", "member_number": f"SHA{100000 + i}", "is_active": True}

        if age >= 18:
            rec["national_id"] = str(20000000 + i)
        else:
            rec["guardian_national_id"] = str(30000000 + i)
            rec["guardian_name"] = kin_name

        if gender == "female" and 20 <= age <= 40 and i in (2, 8, 22, 36):
            rec["is_pregnant"] = True
        if age < 13:
            rec["is_paediatric"] = True
            rec["is_neonate"] = age < 1

        patients.append(rec)
        patient_ids.append(_id)

    return patients, patient_ids


COMPLAINTS = [
    "Persistent headache and dizziness", "Elevated blood sugar and fatigue",
    "Nausea and lower abdominal pain", "Swollen ankles and reduced urine output",
    "Wheezing and shortness of breath", "Chronic cough and breathlessness",
    "Fever and sore throat", "Blurred vision and increased thirst",
    "Lower back pain and contractions", "Persistent cough and fever",
    "Severe joint pain", "Chest pain and shortness of breath",
    "Abdominal cramps and diarrhoea", "Severe headache and high blood pressure",
    "Menstrual cramps and lower back pain", "Progressive breathlessness",
    "High fever and irritability", "Lower back pain after lifting",
    "Headache and palpitations", "Cough and chest tightness",
    "Dizziness and fainting episode", "Painful urination",
    "Vomiting and dehydration", "Skin rash and itching",
    "Ear pain and reduced hearing",
]

DIAGNOSES = [
    "Hypertensive urgency", "Uncontrolled Type 2 Diabetes Mellitus",
    "Threatened preterm labour", "Acute-on-chronic kidney disease",
    "Acute exacerbation of asthma", "Acute exacerbation of COPD",
    "Acute pharyngitis", "Diabetic ketoacidosis", "Preterm labour",
    "Upper respiratory tract infection", "Rheumatoid arthritis flare",
    "Decompensated heart failure", "Acute gastroenteritis",
    "Malignant hypertension", "Primary dysmenorrhoea",
    "Congestive cardiac failure", "Febrile illness", "Mechanical low back pain",
    "Hypertensive heart disease", "Acute bronchitis", "Vasovagal syncope",
    "Urinary tract infection", "Acute gastroenteritis with dehydration",
    "Allergic dermatitis", "Acute otitis media",
]


def _vitals(weight, severity="normal"):
    if severity == "critical":
        return {"blood_pressure_systolic": 188, "blood_pressure_diastolic": 112,
                "temperature_celsius": 39.4, "pulse_rate": 122, "oxygen_saturation": 89,
                "weight_kg": weight, "respiratory_rate": 28}
    if severity == "urgent":
        return {"blood_pressure_systolic": 158, "blood_pressure_diastolic": 96,
                "temperature_celsius": 38.3, "pulse_rate": 104, "oxygen_saturation": 94,
                "weight_kg": weight, "respiratory_rate": 22}
    return {"blood_pressure_systolic": 122, "blood_pressure_diastolic": 78,
            "temperature_celsius": 36.7, "pulse_rate": 76, "oxygen_saturation": 98,
            "weight_kg": weight, "respiratory_rate": 16}


STATE_PLAN = (
    ["discharged"] * 26 +
    ["ready_for_discharge"] * 3 +
    ["in_ward"] * 4 +
    ["admitted"] * 2 +
    ["treatment_in_progress"] * 4 +
    ["awaiting_results"] * 3 +
    ["in_consultation"] * 4 +
    ["waiting_for_doctor"] * 4 +
    ["triaged"] * 3 +
    ["registered"] * 4 +
    ["cancelled"] * 3
)


def build_visits(patient_ids, dept_map, user_ids, bed_ids):
    doctors = user_ids["doctors"]
    nurses = user_ids["nurses"]
    reception = user_ids["receptionist"]
    n_patients = len(patient_ids)

    visits, visit_ids = [], []
    gw_beds = list(bed_ids.get("GW", []))

    plan = list(STATE_PLAN)
    random.shuffle(plan)

    active_states = {"registered", "triaged", "waiting_for_doctor",
                     "in_consultation", "awaiting_results",
                     "treatment_in_progress", "admitted", "in_ward",
                     "ready_for_discharge"}

    for idx, status in enumerate(plan):
        _id = oid()
        if status in active_states:
            days_ago = random.randint(0, 2)
        else:
            days_ago = random.randint(1, WINDOW_DAYS)

        reg_at = (NOW - timedelta(days=days_ago)).replace(
            hour=random.randint(8, 16), minute=random.randint(0, 59),
            second=0, microsecond=0)

        p_idx = idx % n_patients
        pid = patient_ids[p_idx]

        acuity = "normal"
        if idx % 11 == 0:
            acuity = "critical"
        elif idx % 7 == 0:
            acuity = "urgent"

        if status in ("admitted", "in_ward", "ready_for_discharge"):
            dept_code, vtype = "GW", "ipd"
        elif acuity == "critical":
            dept_code, vtype = "ED", "emergency"
        else:
            dept_code, vtype = "OPD", "opd"

        rec = {
            "_id": _id,
            "patient_id": sid(pid),
            "visit_number": f"VN-2026-{idx + 1:04d}",
            "visit_type": vtype,
            "department_id": sid(dept_map[dept_code]),
            "status": status,
            "priority": {"normal": "routine", "urgent": "urgent", "critical": "critical"}[acuity],
            "registered_at": reg_at,
            "registered_by_id": sid(reception),
            "chief_complaint": COMPLAINTS[p_idx % len(COMPLAINTS)],
            "prescription_ids": [],
            "created_at": reg_at,
            "updated_at": reg_at,
        }

        t = reg_at

        if status not in ("registered", "cancelled"):
            t = t + timedelta(minutes=random.randint(5, 20))
            rec["triaged_at"] = t
            rec["triage_nurse_id"] = sid(nurses[idx % 3])
            rec["vitals"] = _vitals(PEOPLE[p_idx][5], acuity)

        if status not in ("registered", "triaged", "cancelled"):
            wait = random.randint(15, 75) if acuity == "normal" else random.randint(5, 25)
            t = t + timedelta(minutes=wait)
            rec["doctor_assigned_at"] = t
            rec["assigned_doctor_id"] = sid(doctors[idx % 3])
            rec["consultation_room"] = f"Consultation Room {idx % 3 + 1}"
            rec["consultation_nurse_id"] = sid(nurses[idx % 3])
            t = t + timedelta(minutes=random.randint(2, 8))
            rec["consultation_started_at"] = t

        if status in ("in_consultation", "awaiting_results", "treatment_in_progress",
                      "admitted", "in_ward", "ready_for_discharge", "discharged"):
            rec["diagnosis"] = DIAGNOSES[p_idx % len(DIAGNOSES)]

        if status in ("awaiting_results", "treatment_in_progress", "admitted",
                      "in_ward", "ready_for_discharge", "discharged"):
            t = t + timedelta(minutes=random.randint(10, 25))
            rec["consultation_ended_at"] = t

        if status in ("admitted", "in_ward", "ready_for_discharge"):
            t = t + timedelta(minutes=random.randint(20, 90))
            rec["admitted_at"] = t
            if gw_beds:
                rec["bed_id"] = sid(gw_beds.pop(0))
                rec["ward_name"] = "General Ward"
            rec["visit_type"] = "ipd"

        if status in ("ready_for_discharge", "discharged"):
            t = t + timedelta(minutes=random.randint(30, 180))
            rec["billing_completed_at"] = t
        if status == "discharged":
            t = t + timedelta(minutes=random.randint(20, 120))
            rec["discharged_at"] = t

        visits.append(rec)
        visit_ids.append(_id)

    return visits, visit_ids


MEDS_CATALOGUE = [
    [("Amoxicillin", "500mg", "oral", "TDS", 7)],
    [("Metformin", "500mg", "oral", "BD", 30)],
    [("Salbutamol", "2.5mg", "nebulisation", "PRN", 5)],
    [("Lisinopril", "10mg", "oral", "OD", 30)],
    [("Prednisolone", "20mg", "oral", "OD", 7)],
    [("Omeprazole", "20mg", "oral", "OD", 14)],
    [("Paracetamol", "1g", "oral", "QDS", 5)],
    [("Atorvastatin", "40mg", "oral", "OD", 30)],
    [("Ibuprofen", "400mg", "oral", "TDS", 5)],
    [("Ceftriaxone", "1g", "iv", "OD", 5)],
    [("Insulin", "20IU", "sc", "OD", 30)],
    [("Furosemide", "40mg", "oral", "BD", 14)],
    [("Amlodipine", "5mg", "oral", "OD", 30)],
    [("Azithromycin", "500mg", "oral", "OD", 3)],
    [("Diclofenac", "50mg", "oral", "BD", 5)],
]

SLA_BY_PRIORITY = {"stat": 15, "urgent": 30, "routine": 60, "discharge": 45, "nicu": 20, "chemo": 120, "critical": 15}


def build_prescriptions(patient_ids, visit_ids, visits, dept_map, user_ids):
    doctors = user_ids["doctors"]
    pharmacist = user_ids["pharmacist"]
    nurses = user_ids["nurses"]

    rxs, rx_ids = [], []
    rx_n = 1

    eligible = [v for v in visits if v.get("consultation_started_at")
                and v["status"] not in ("cancelled",)]

    def minutes(a, b):
        return round((b - a).total_seconds() / 60.0, 1)

    for n, vis in enumerate(eligible):
        _id = oid()
        p_idx = patient_ids.index(ObjectId(vis["patient_id"])) if ObjectId(vis["patient_id"]) in patient_ids else n % len(patient_ids)
        priority = "stat" if vis["priority"] == "critical" else ("urgent" if vis["priority"] == "urgent" else "routine")
        sla = SLA_BY_PRIORITY.get(priority, 120)
        meds = [{"name": m[0], "dose": m[1], "route": m[2], "frequency": m[3], "duration_days": m[4]}
                for m in MEDS_CATALOGUE[n % len(MEDS_CATALOGUE)]]

        ordered_at = vis.get("consultation_ended_at") or (vis["consultation_started_at"] + timedelta(minutes=random.randint(10, 20)))

        vstatus = vis["status"]
        if vstatus in ("in_consultation",):
            rx_status = random.choice(["draft", "submitted"])
        elif vstatus in ("awaiting_results", "treatment_in_progress", "waiting_for_doctor"):
            rx_status = random.choice(["submitted", "flagged", "verified"])
        else:
            rx_status = random.choice(["verified", "dispensed", "administered", "administered"])

        # Paediatric patients get a clear per-kg overdose so the age-banded
        # dose check is visible in the seeded data.
        person = PEOPLE[p_idx]
        is_child = person[2] >= "2014"  # dob year -> roughly under ~12
        flags = []
        if is_child and n % 3 == 0:
            meds = [{"name": "Ibuprofen", "dose": "400mg", "route": "oral", "frequency": "TDS", "duration_days": 5}]
            flags = ["high_dose"]
            rx_status = random.choice(["submitted", "flagged"])
        elif n % 6 == 2:
            flags = [random.choice(["high_dose", "drug_interaction", "allergy_match"])]
            if rx_status in ("draft",):
                rx_status = "flagged"

        rec = {
            "_id": _id,
            "rx_number": f"RX-2026-{rx_n:04d}",
            "patient_id": vis["patient_id"],
            "doctor_id": vis.get("assigned_doctor_id") or sid(doctors[n % 3]),
            "visit_id": sid(vis["_id"]),
            "department_id": vis["department_id"],
            "medications": meds,
            "status": rx_status,
            "order_source": vis["visit_type"],
            "priority": priority,
            "flags": flags,
            "sla_threshold_min": sla,
            "sla_breached": False,
            "notes": f"Prescribed for: {vis.get('chief_complaint', 'review')}",
            "ordered_at": ordered_at,
            "created_at": ordered_at,
            "updated_at": ordered_at,
        }
        rx_n += 1

        t = ordered_at
        if rx_status != "draft":
            t = t + timedelta(minutes=random.randint(3, 12))
            rec["submitted_at"] = t
            rec["tat_order_to_submit_min"] = minutes(ordered_at, t)

        flag_hold = 0
        if flags and rx_status in ("verified", "dispensed", "administered"):
            flag_hold = random.randint(20, 90)

        slow = (n % 5 in (1, 3, 4))
        slow_extra = random.randint(50, 110) if slow else 0

        if rx_status in ("verified", "dispensed", "administered"):
            submit_t = rec["submitted_at"]
            verify_gap = random.randint(8, 40) + flag_hold + slow_extra
            t = submit_t + timedelta(minutes=verify_gap)
            rec["verified_at"] = t
            rec["auditor_approved_at"] = t
            rec["auditor_id"] = sid(user_ids["auditor"])
            rec["tat_submit_to_verify_min"] = minutes(submit_t, t)
            if flag_hold:
                rec["tat_flag_hold_min"] = float(flag_hold)

        if rx_status in ("dispensed", "administered"):
            verify_t = rec["verified_at"]
            disp_gap = random.randint(6, 28) + (random.randint(20, 50) if slow else 0)
            t = verify_t + timedelta(minutes=disp_gap)
            rec["dispensed_at"] = t
            rec["dispensed_by_id"] = sid(pharmacist)
            rec["receipt_number"] = f"RCP-{rx_n:04d}"
            rec["tat_verify_to_dispense_min"] = minutes(verify_t, t)

        if rx_status == "administered":
            disp_t = rec["dispensed_at"]
            t = disp_t + timedelta(minutes=random.randint(10, 45))
            rec["administered_at"] = t
            rec["administered_by_id"] = sid(nurses[n % 3])
            rec["administered_dose"] = meds[0]["dose"]
            rec["administered_route"] = meds[0]["route"]
            rec["tat_dispense_to_admin_min"] = minutes(disp_t, t)

        if rec.get("dispensed_at"):
            tat_pharm = minutes(rec["submitted_at"], rec["dispensed_at"])
            rec["tat_pharmacy_min"] = tat_pharm
            total = minutes(ordered_at, rec.get("administered_at") or rec["dispensed_at"])
            rec["tat_total_min"] = total
            if tat_pharm > sla:
                rec["sla_breached"] = True
                rec["sla_breach_duration_min"] = round(tat_pharm - sla, 1)
                rec["tat_breached_at"] = rec["submitted_at"] + timedelta(minutes=sla)

        if flags and rx_status == "flagged":
            rec["pharmacist_comment"] = "Flagged for clinical review - verify before dispensing."

        rxs.append(rec)
        rx_ids.append(_id)

    return rxs, rx_ids


FLAG_DETAIL = {
    "high_dose": ("high", "Dose exceeds the weight-based limit (mg/kg/day) for the patient's age band"),
    "allergy_match": ("critical", "Prescribed drug matches a documented patient allergy"),
    "drug_interaction": ("high", "Potential major interaction with the patient's other drugs"),
}


def build_audit_records(rx_ids, rxs, user_ids):
    auditor = user_ids["auditor"]
    pharmacist = user_ids["pharmacist"]
    records = []

    for rx in rxs:
        for code in rx.get("flags", []):
            severity, issue = FLAG_DETAIL.get(code, ("medium", "Clinical review required"))
            created = rx.get("submitted_at", rx["created_at"]) + timedelta(minutes=random.randint(2, 8))
            resolved = rx["status"] in ("verified", "dispensed", "administered")
            rec = {
                "_id": oid(),
                "prescription_id": sid(rx["_id"]),
                "visit_id": rx.get("visit_id"),
                "patient_id": rx.get("patient_id"),
                "flag_code": code,
                "type": "automated",
                "issue": issue,
                "severity": severity,
                "resolved": resolved,
                "created_by": "system",
                "created_by_role": "system",
                "created_at": created,
                "recommendation": "Review with the prescribing doctor before dispensing.",
                "countersigned": False,
            }
            if resolved:
                rtype = random.choice(["accepted_risk", "dose_adjusted", "drug_changed", "false_positive"])
                rec["resolved_by"] = sid(auditor)
                rec["resolved_at"] = created + timedelta(minutes=random.randint(20, 120))
                rec["resolution_type"] = rtype
                rec["resolution_note"] = f"Reviewed by auditor. Action taken: {rtype.replace('_', ' ')}."
                if severity == "critical":
                    rec["countersigned"] = True
                    rec["countersigned_by"] = sid(pharmacist)
                    rec["countersigned_at"] = rec["resolved_at"] + timedelta(minutes=15)
                    rec["countersign_note"] = "Countersigned after dose verification."
            records.append(rec)

        if rx.get("sla_breached"):
            created = rx.get("tat_breached_at") or rx["created_at"]
            records.append({
                "_id": oid(),
                "prescription_id": sid(rx["_id"]),
                "visit_id": rx.get("visit_id"),
                "patient_id": rx.get("patient_id"),
                "flag_code": "sla_exceeded",
                "type": "sla_breach",
                "issue": f"{rx['priority'].upper()} prescription exceeded its {rx['sla_threshold_min']}-min SLA",
                "severity": "high",
                "resolved": rx["status"] in ("dispensed", "administered"),
                "created_by": "system",
                "created_by_role": "system",
                "created_at": created,
                "countersigned": False,
            })

    return records


PAYMENT_METHODS = ["sha", "mpesa", "cash", "card"]


def build_bills(visit_ids, visits):
    bills = []
    bill_n = 1

    consult_prices = {"opd": ("OPD Consultation", 800), "emergency": ("Emergency Consultation", 1500),
                      "ipd": ("Inpatient Consultation", 1200)}
    pharm_items = [("Amoxicillin 500mg x21", 1200), ("Metformin 500mg x60", 900),
                   ("Salbutamol Inhaler", 1800), ("IV Antibiotics", 3000),
                   ("Insulin 30 days", 2200), ("Oral Medications", 1500)]
    lab_items = [("Full Blood Count", 1200), ("Renal Function Tests", 1800),
                 ("Blood Glucose", 400), ("Liver Function Tests", 2000)]

    billable = [v for v in visits if v.get("billing_completed_at")
                or v["status"] in ("treatment_in_progress", "awaiting_results", "in_ward")]

    for k, vis in enumerate(billable):
        _id = oid()
        vtype = vis["visit_type"]
        line_items = []

        cname, cprice = consult_prices.get(vtype, ("OPD Consultation", 800))
        line_items.append({"category": "consultation", "description": cname,
                           "quantity": 1, "unit_price": float(cprice), "total_price": float(cprice)})

        pname, pprice = pharm_items[k % len(pharm_items)]
        line_items.append({"category": "pharmacy", "description": pname,
                           "quantity": 1, "unit_price": float(pprice), "total_price": float(pprice)})

        if k % 3 == 0:
            lname, lprice = lab_items[k % len(lab_items)]
            line_items.append({"category": "lab", "description": lname,
                               "quantity": 1, "unit_price": float(lprice), "total_price": float(lprice)})

        if vtype == "ipd":
            days = random.randint(1, 3)
            line_items.append({"category": "ward", "description": f"General Ward - {days} Day(s)",
                               "quantity": days, "unit_price": 2500.0, "total_price": float(2500 * days)})

        subtotal = sum(li["total_price"] for li in line_items)

        billing_done = bool(vis.get("billing_completed_at"))
        if billing_done:
            status = "paid"
        elif k % 4 == 0:
            status = "partially_paid"
        else:
            status = "open"

        discount = 0.0
        total = subtotal - discount
        created_at = (vis.get("consultation_ended_at") or vis["registered_at"]) + timedelta(minutes=random.randint(20, 90))

        payments = []
        if status == "paid":
            method = PAYMENT_METHODS[k % len(PAYMENT_METHODS)]
            paid_at = vis.get("billing_completed_at") or (created_at + timedelta(minutes=30))
            if method == "sha" and k % 2 == 0 and total > 2000:
                sha_part = round(total * 0.7, 2)
                payments = [
                    {"amount": sha_part, "method": "sha", "received_at": paid_at},
                    {"amount": round(total - sha_part, 2), "method": "cash", "received_at": paid_at + timedelta(minutes=5)},
                ]
            else:
                payments = [{"amount": float(total), "method": method, "received_at": paid_at}]
        elif status == "partially_paid":
            paid_at = created_at + timedelta(minutes=40)
            payments = [{"amount": round(total * 0.5, 2), "method": PAYMENT_METHODS[k % len(PAYMENT_METHODS)], "received_at": paid_at}]

        bills.append({
            "_id": _id,
            "bill_number": f"BILL-2026-{bill_n:04d}",
            "visit_id": sid(vis["_id"]),
            "visit_number": vis.get("visit_number", ""),
            "patient_id": vis.get("patient_id", ""),
            "status": status,
            "line_items": line_items,
            "subtotal": float(subtotal),
            "discount_amount": float(discount),
            "tax_amount": 0.0,
            "total_amount": float(total),
            "payments": payments,
            "created_at": created_at,
        })
        bill_n += 1

    return bills
