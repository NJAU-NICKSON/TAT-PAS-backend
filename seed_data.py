
from datetime import datetime, timedelta
from bson import ObjectId

NOW = datetime.utcnow()


def oid():
    return ObjectId()


def sid(o):
    return str(o)


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

SLA_BY_PRIORITY = {"stat": 15, "urgent": 30, "routine": 60, "discharge": 45, "nicu": 20, "chemo": 120, "critical": 15}


def _phone(i):
    return f"07{(10000000 + i * 137911) % 100000000:08d}"


# Vitals preset for an acuity level.
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


# 5 patients per doctor (3 doctors = 15). Each block of 5 maps to the roles below.
_SCENARIO_PEOPLE = [
    ("Mary", "Wanjiru Kamau", "1985-03-12", "female", "A+", 68, ["Penicillin:severe"], ["Hypertension"]),
    ("John", "Otieno Odhiambo", "1972-07-22", "male", "O+", 82, [], ["Diabetes Type 2"]),
    ("Brian", "Kamau Njoroge", "2020-02-28", "male", "B+", 14, [], []),
    ("David", "Mwangi Waweru", "1965-01-30", "male", "AB+", 90, [], ["CKD Stage 3"]),
    ("Faith", "Chebet Korir", "1990-11-05", "female", "B+", 58, [], []),

    ("Peter", "Maina Kariuki", "1980-12-15", "male", "O+", 78, ["Sulfonamides:moderate"], ["Diabetes Type 2"]),
    ("Esther", "Jepkemboi Rono", "1989-08-03", "female", "A+", 65, [], []),
    ("Miriam", "Atieno Ochieng", "2021-04-10", "female", "O+", 11, [], []),
    ("Stephen", "Njuguna Mwangi", "1955-12-20", "male", "A+", 80, [], ["COPD"]),
    ("Lucy", "Wambui Gichuki", "2000-09-25", "female", "A+", 52, [], []),

    ("Hassan", "Omar Noor", "1978-03-11", "male", "O-", 85, ["Codeine:moderate"], ["Hypertension"]),
    ("Anne", "Cherono Korir", "1992-07-07", "female", "B+", 58, [], []),
    ("Sarah", "Nasimiyu Wafula", "2017-01-15", "female", "A+", 24, [], []),
    ("George", "Muriithi Karanja", "1962-09-13", "male", "AB+", 88, [], ["Diabetes Type 2"]),
    ("Nancy", "Chepkoech Ruto", "1996-03-17", "female", "B-", 59, [], []),
]

# Each doctor's five patients, in order.
_SCENARIO_ROLES = ["tat_flag", "rx_flag", "awaiting_pharmacy", "awaiting_nurse", "discharged"]

_SCENARIO_COMPLAINTS = {
    "tat_flag":          "Severe headache and high blood pressure",
    "rx_flag":           "High fever and irritability",
    "awaiting_pharmacy": "Persistent cough and fever",
    "awaiting_nurse":    "Wheezing and shortness of breath",
    "discharged":        "Lower abdominal pain",
}
_SCENARIO_DIAGNOSES = {
    "tat_flag":          "Hypertensive urgency",
    "rx_flag":           "Febrile illness",
    "awaiting_pharmacy": "Acute pharyngitis",
    "awaiting_nurse":    "Acute exacerbation of asthma",
    "discharged":        "Acute gastroenteritis",
}
_SCENARIO_MEDS = {
    "tat_flag":          [("Amoxicillin", "500mg", "oral", "TDS", 7)],
    "rx_flag":           [("Ibuprofen", "400mg", "oral", "TDS", 5)],
    "awaiting_pharmacy": [("Amoxicillin", "500mg", "oral", "TDS", 7)],
    "awaiting_nurse":    [("Ceftriaxone", "1g", "iv", "OD", 5)],
    "discharged":        [("Metformin", "500mg", "oral", "BD", 30)],
}


def _monday_of_this_week():
    # Anchor the simulated week to the most recent Monday that keeps every
    # working day (Mon-Fri) in the past, so turnaround times are never negative.
    midnight = datetime(NOW.year, NOW.month, NOW.day)
    this_monday = midnight - timedelta(days=midnight.weekday())
    # If Friday of this week is still in the future, use last week instead.
    if this_monday + timedelta(days=4) > NOW:
        return this_monday - timedelta(days=7)
    return this_monday


def build_scenario(dept_map, user_ids):
    doctors = user_ids["doctors"]
    nurses = user_ids["nurses"]
    reception = user_ids["receptionist"]
    auditor = user_ids["auditor"]
    pharmacist = user_ids["pharmacist"]

    monday = _monday_of_this_week()

    name_by_id = {sid(u["_id"]): u["full_name"] for u in _ALL_USERS_CACHE}

    def minutes(a, b):
        return round((b - a).total_seconds() / 60.0, 1)

    patients, visits, prescriptions, audit_records, bills = [], [], [], [], []
    mrn_counters, visit_counters = {}, {}
    rx_n = bill_n = 1

    for i, person in enumerate(_SCENARIO_PEOPLE):
        first, last, dob, gender, blood, weight, allergy_codes, chronic = person
        doctor_idx = i // 5
        role = _SCENARIO_ROLES[i % 5]
        doctor_id = sid(doctors[doctor_idx])
        nurse_id = sid(nurses[doctor_idx])

        reg_day = monday + timedelta(days=(i % 5))
        reg_at = reg_day + timedelta(hours=8 + (i % 6), minutes=(i * 7) % 60)
        day_key = reg_at.strftime("%Y%m%d")

        mrn_counters[day_key] = mrn_counters.get(day_key, 0) + 1
        visit_counters[day_key] = visit_counters.get(day_key, 0) + 1
        mrn = f"MRN-{day_key}-{mrn_counters[day_key]:04d}"
        visit_number = f"V-{day_key}-{visit_counters[day_key]:04d}"

        dob_dt = datetime.strptime(dob, "%Y-%m-%d")
        age = (NOW - dob_dt).days // 365
        allergies = [{"substance": s, "severity": sev}
                     for s, sev in (c.split(":") for c in allergy_codes)]
        estate = NAIROBI_ESTATES[i % len(NAIROBI_ESTATES)]
        kin_name = f"{KIN_FIRST[i % len(KIN_FIRST)]} {last.split()[-1]}"

        pid = oid()
        prec = {
            "_id": pid,
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
                "phone": _phone(i),
                "email": f"{first.lower()}.{last.split()[-1].lower()}@gmail.com",
                "address": f"{estate}, P.O. Box {1000 + i * 7}, Nairobi",
                "city": "Nairobi",
            },
            "next_of_kin": {"name": kin_name, "relationship": KIN_RELS[i % len(KIN_RELS)], "phone": _phone(i + 5)},
            "created_at": reg_at,
        }
        if age >= 18:
            prec["national_id"] = str(20000000 + i)
        else:
            prec["guardian_national_id"] = str(30000000 + i)
            prec["guardian_name"] = kin_name
        if age < 13:
            prec["is_paediatric"] = True
            prec["is_neonate"] = age < 1
        patients.append(prec)

        acuity = "critical" if role == "tat_flag" else ("urgent" if role == "awaiting_nurse" else "normal")
        dept_code = "ED" if acuity == "critical" else "OPD"
        vstatus = {
            "tat_flag":          "waiting_for_doctor",
            "rx_flag":           "waiting_for_doctor",
            "awaiting_pharmacy": "treatment_in_progress",
            "awaiting_nurse":    "treatment_in_progress",
            "discharged":        "discharged",
        }[role]

        vid = oid()
        triaged_at = reg_at + timedelta(minutes=12)
        consult_started = triaged_at + timedelta(minutes=20)
        consult_ended = consult_started + timedelta(minutes=18)

        vrec = {
            "_id": vid,
            "visit_number": visit_number,
            "patient_id": sid(pid),
            "visit_type": "emergency" if dept_code == "ED" else "opd",
            "department_id": sid(dept_map[dept_code]),
            "status": vstatus,
            "priority": {"normal": "routine", "urgent": "urgent", "critical": "critical"}[acuity],
            "registered_at": reg_at,
            "registered_by_id": sid(reception),
            "registered_by_name": name_by_id.get(sid(reception)),
            "chief_complaint": _SCENARIO_COMPLAINTS[role],
            "assigned_doctor_id": doctor_id,
            "assigned_doctor_name": name_by_id.get(doctor_id),
            "doctor_assigned_at": reg_at,
            "triage_nurse_id": nurse_id,
            "triage_nurse_name": name_by_id.get(nurse_id),
            "triaged_at": triaged_at,
            "vitals": _vitals(weight, acuity),
            "consultation_nurse_id": nurse_id,
            "consultation_nurse_name": name_by_id.get(nurse_id),
            "consultation_room": f"Consultation Room {doctor_idx + 1}",
            "consultation_started_at": consult_started,
            "consultation_ended_at": consult_ended,
            "prescription_ids": [],
            "created_at": reg_at,
            "updated_at": reg_at,
        }
        if role == "discharged":
            vrec["diagnosis"] = _SCENARIO_DIAGNOSES[role]
            vrec["billing_completed_at"] = consult_ended + timedelta(hours=2)
            vrec["discharged_at"] = consult_ended + timedelta(hours=3)
        elif role in ("awaiting_pharmacy", "awaiting_nurse"):
            vrec["diagnosis"] = _SCENARIO_DIAGNOSES[role]
        visits.append(vrec)

        priority = "stat" if acuity == "critical" else ("urgent" if acuity == "urgent" else "routine")
        sla = SLA_BY_PRIORITY.get(priority, 60)
        meds = [{"name": m[0], "dose": m[1], "route": m[2], "frequency": m[3], "duration_days": m[4]}
                for m in _SCENARIO_MEDS[role]]
        ordered_at = consult_ended
        rx_status = {
            "tat_flag":          "submitted",
            "rx_flag":           "flagged",
            "awaiting_pharmacy": "verified",
            "awaiting_nurse":    "dispensed",
            "discharged":        "administered",
        }[role]
        flags = ["high_dose"] if role == "rx_flag" else []

        rxid = oid()
        rx = {
            "_id": rxid,
            "rx_number": f"RX-2026-{rx_n:04d}",
            "patient_id": sid(pid),
            "doctor_id": doctor_id,
            "visit_id": sid(vid),
            "department_id": sid(dept_map[dept_code]),
            "medications": meds,
            "status": rx_status,
            "order_source": vrec["visit_type"],
            "priority": priority,
            "flags": flags,
            "sla_threshold_min": sla,
            "sla_breached": False,
            "notes": f"Prescribed for: {vrec['chief_complaint']}",
            "ordered_at": ordered_at,
            "created_at": ordered_at,
            "updated_at": ordered_at,
        }
        rx_n += 1

        submitted_at = ordered_at + timedelta(minutes=6)
        rx["submitted_at"] = submitted_at
        rx["tat_order_to_submit_min"] = minutes(ordered_at, submitted_at)

        if role == "tat_flag":
            over = sla + 90
            rx["sla_breached"] = True
            rx["sla_breach_duration_min"] = float(over - sla)
            rx["tat_breached_at"] = submitted_at + timedelta(minutes=sla)
        elif role == "rx_flag":
            rx["pharmacist_comment"] = "Flagged for clinical review - verify before dispensing."

        if role in ("awaiting_pharmacy", "awaiting_nurse", "discharged"):
            verify_at = submitted_at + timedelta(minutes=18)
            rx["verified_at"] = verify_at
            rx["auditor_approved_at"] = verify_at
            rx["auditor_id"] = sid(auditor)
            rx["tat_submit_to_verify_min"] = minutes(submitted_at, verify_at)

        if role in ("awaiting_nurse", "discharged"):
            disp_at = rx["verified_at"] + timedelta(minutes=14)
            rx["dispensed_at"] = disp_at
            rx["dispensed_by_id"] = sid(pharmacist)
            rx["dispensed_by_name"] = name_by_id.get(sid(pharmacist))
            rx["receipt_number"] = f"RCP-{day_key}-{rx_n:04d}"
            rx["tat_verify_to_dispense_min"] = minutes(rx["verified_at"], disp_at)

        if role == "discharged":
            admin_at = rx["dispensed_at"] + timedelta(minutes=22)
            rx["administered_at"] = admin_at
            rx["administered_by_id"] = nurse_id
            rx["administered_by_name"] = name_by_id.get(nurse_id)
            rx["administered_dose"] = meds[0]["dose"]
            rx["administered_route"] = meds[0]["route"]
            rx["tat_dispense_to_admin_min"] = minutes(rx["dispensed_at"], admin_at)
            rx["tat_total_min"] = minutes(ordered_at, admin_at)

        prescriptions.append(rx)
        vrec["prescription_ids"] = [sid(rxid)]

        # Unresolved flags awaiting auditor review.
        if role == "rx_flag":
            audit_records.append({
                "_id": oid(),
                "prescription_id": sid(rxid),
                "visit_id": sid(vid),
                "patient_id": sid(pid),
                "flag_code": "high_dose",
                "type": "automated",
                "issue": ("Dose exceeds weight-based limit: 120.0 mg/kg/day for Ibuprofen "
                          "(age band 1-12, max 30 mg/kg/day)"),
                "severity": "high",
                "resolved": False,
                "created_by": "system",
                "created_by_role": "system",
                "created_at": submitted_at + timedelta(minutes=1),
                "recommendation": ("Accepted range for a child this age is up to 30 mg/kg/day "
                                   "(abs 800 mg/day). Recalculate for the patient's weight."),
                "drug_name": "Ibuprofen",
                "dose": "400mg",
                "countersigned": False,
            })
        if role == "tat_flag":
            audit_records.append({
                "_id": oid(),
                "prescription_id": sid(rxid),
                "visit_id": sid(vid),
                "patient_id": sid(pid),
                "flag_code": "sla_exceeded",
                "type": "sla_breach",
                "issue": f"{priority.upper()} prescription exceeded its {sla}-min SLA",
                "severity": "high",
                "resolved": False,
                "created_by": "system",
                "created_by_role": "system",
                "created_at": rx["tat_breached_at"],
                "countersigned": False,
            })

        # Discharged patient: partially paid bill.
        if role == "discharged":
            line_items = [
                {"category": "consultation", "description": "OPD Consultation",
                 "quantity": 1, "unit_price": 800.0, "total_price": 800.0},
                {"category": "pharmacy", "description": "Metformin 500mg x60",
                 "quantity": 1, "unit_price": 900.0, "total_price": 900.0},
                {"category": "lab", "description": "Blood Glucose",
                 "quantity": 1, "unit_price": 400.0, "total_price": 400.0},
            ]
            subtotal = sum(li["total_price"] for li in line_items)
            created_at = consult_ended + timedelta(minutes=40)
            bills.append({
                "_id": oid(),
                "bill_number": f"BILL-2026-{bill_n:04d}",
                "visit_id": sid(vid),
                "visit_number": visit_number,
                "patient_id": sid(pid),
                "status": "partially_paid",
                "line_items": line_items,
                "subtotal": float(subtotal),
                "discount_amount": 0.0,
                "tax_amount": 0.0,
                "total_amount": float(subtotal),
                "payments": [{"amount": round(subtotal * 0.5, 2), "method": "mpesa",
                              "received_at": created_at + timedelta(minutes=20)}],
                "created_at": created_at,
            })
            bill_n += 1

    # Seed per-day counters so live registrations continue the sequence.
    counters = []
    for day_key, seq in mrn_counters.items():
        counters.append({"_id": f"mrn_{day_key}", "seq": seq})
    for day_key, seq in visit_counters.items():
        counters.append({"_id": f"visit_{day_key}", "seq": seq})

    return patients, visits, prescriptions, audit_records, bills, counters


# Populated by the runner so the scenario builder can resolve staff names.
_ALL_USERS_CACHE = []
