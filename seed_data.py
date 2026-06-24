
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

# Per-patient outcome profile, one per patient in _SCENARIO_PEOPLE order.
_PROFILES = [
    {"outcome": "discharged", "flag": "none",    "acuity": "normal",
     "complaint": "Lower abdominal pain", "diagnosis": "Acute gastroenteritis",
     "meds": [("Metronidazole", "400mg", "oral", "TDS", 5)]},
    {"outcome": "discharged", "flag": "on_time", "acuity": "normal",
     "complaint": "Persistent cough and fever", "diagnosis": "Acute pharyngitis",
     "meds": [("Amoxicillin", "500mg", "oral", "TDS", 7)]},
    {"outcome": "discharged", "flag": "amended", "acuity": "urgent",
     "complaint": "High fever and irritability", "diagnosis": "Febrile illness",
     "meds": [("Ibuprofen", "400mg", "oral", "TDS", 5)]},
    {"outcome": "ward",       "flag": "late",    "acuity": "urgent",
     "complaint": "Wheezing and shortness of breath", "diagnosis": "Acute exacerbation of asthma",
     "meds": [("Ceftriaxone", "1g", "iv", "OD", 5)]},
    {"outcome": "discharged", "flag": "none",    "acuity": "normal",
     "complaint": "Headache and body aches", "diagnosis": "Viral illness",
     "meds": [("Paracetamol", "1g", "oral", "QDS", 3)]},

    {"outcome": "discharged", "flag": "on_time", "acuity": "normal",
     "complaint": "Burning on urination", "diagnosis": "Urinary tract infection",
     "meds": [("Nitrofurantoin", "100mg", "oral", "BD", 5)]},
    {"outcome": "discharged", "flag": "none",    "acuity": "normal",
     "complaint": "Sore throat", "diagnosis": "Tonsillitis",
     "meds": [("Amoxicillin", "500mg", "oral", "TDS", 7)]},
    {"outcome": "ward",       "flag": "amended", "acuity": "urgent",
     "complaint": "High fever and irritability", "diagnosis": "Febrile illness",
     "meds": [("Ibuprofen", "200mg", "oral", "TDS", 5)]},
    {"outcome": "discharged", "flag": "late",    "acuity": "urgent",
     "complaint": "Shortness of breath", "diagnosis": "COPD exacerbation",
     "meds": [("Prednisolone", "30mg", "oral", "OD", 5)]},
    {"outcome": "discharged", "flag": "none",    "acuity": "normal",
     "complaint": "Skin rash", "diagnosis": "Allergic dermatitis",
     "meds": [("Cetirizine", "10mg", "oral", "OD", 7)]},

    {"outcome": "discharged", "flag": "on_time", "acuity": "normal",
     "complaint": "Severe headache and high blood pressure", "diagnosis": "Hypertensive urgency",
     "meds": [("Amlodipine", "10mg", "oral", "OD", 30)]},
    {"outcome": "discharged", "flag": "none",    "acuity": "normal",
     "complaint": "Diarrhoea and vomiting", "diagnosis": "Acute gastroenteritis",
     "meds": [("Oral Rehydration Salts", "1 sachet", "oral", "PRN", 3)]},
    {"outcome": "ward",       "flag": "on_time", "acuity": "urgent",
     "complaint": "Severe abdominal pain", "diagnosis": "Acute appendicitis",
     "meds": [("Ceftriaxone", "1g", "iv", "OD", 5)]},
    {"outcome": "discharged", "flag": "none",    "acuity": "normal",
     "complaint": "Routine diabetic review", "diagnosis": "Type 2 diabetes mellitus",
     "meds": [("Metformin", "500mg", "oral", "BD", 30)]},
    {"outcome": "ward",       "flag": "late",    "acuity": "critical",
     "complaint": "Chest pain and breathlessness", "diagnosis": "Community-acquired pneumonia",
     "meds": [("Ceftriaxone", "2g", "iv", "OD", 7)]},
]

# Friendly text used when the dose check flags Ibuprofen for a child.
_AMEND_ISSUE = ("Dose exceeds weight-based limit: 120.0 mg/kg/day for Ibuprofen "
                "(age band 1-12, max 30 mg/kg/day)")
_AMEND_REC = ("Accepted range for a child this age is up to 30 mg/kg/day "
              "(abs 800 mg/day). Recalculate for the patient's weight.")


def _monday_of_this_week():
    # Most recent Monday whose week is fully in the past (avoids negative TAT).
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
    billing = user_ids.get("billing", reception)

    monday = _monday_of_this_week()

    name_by_id = {sid(u["_id"]): u["full_name"] for u in _ALL_USERS_CACHE}

    def minutes(a, b):
        return round((b - a).total_seconds() / 60.0, 1)

    patients, visits, prescriptions, audit_records, bills, activity_log = [], [], [], [], [], []
    mrn_counters, visit_counters = {}, {}
    rx_n = bill_n = 1

    # Spread the visits across the two-week window without going past today.
    span_days = (NOW - monday).days
    day_offsets = []
    for i in range(len(_SCENARIO_PEOPLE)):
        off = i % (span_days + 1) if span_days >= 0 else 0
        day_offsets.append(off)

    for i, person in enumerate(_SCENARIO_PEOPLE):
        first, last, dob, gender, blood, weight, allergy_codes, chronic = person
        doctor_idx = i // 5
        profile = _PROFILES[i]
        doctor_id = sid(doctors[doctor_idx])
        nurse_id = sid(nurses[doctor_idx])

        reg_day = monday + timedelta(days=day_offsets[i])
        reg_at = reg_day + timedelta(hours=8 + (i % 6), minutes=(i * 7) % 60)
        # Safety: never allow a registration time in the future.
        if reg_at > NOW - timedelta(hours=5):
            reg_at = NOW - timedelta(days=1 + (i % 3), hours=(i % 6), minutes=(i * 7) % 60)
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

        outcome = profile["outcome"]
        flagkind = profile["flag"]
        acuity = profile["acuity"]
        dept_code = "ED" if acuity == "critical" else "OPD"
        priority = {"normal": "routine", "urgent": "urgent", "critical": "stat"}[acuity]
        sla = SLA_BY_PRIORITY.get(priority, 60)

        def log(action, role_name, actor_id, when, entity_type, entity_id, detail):
            activity_log.append({
                "_id": oid(),
                "action": action,
                "user_id": actor_id,
                "user_role": role_name,
                "user_name": name_by_id.get(actor_id, role_name.title()),
                "entity_type": entity_type,
                "entity_id": entity_id,
                "detail": detail,
                "ip_address": "10.0.0.20",
                "user_agent": "seed",
                "created_at": when,
            })

        # Journey timeline.
        vid = oid()
        triaged_at = reg_at + timedelta(minutes=12)
        consult_started = triaged_at + timedelta(minutes=20)
        consult_ended = consult_started + timedelta(minutes=18)

        # Final visit status depends on the outcome.
        vstatus = "discharged" if outcome == "discharged" else "in_ward"

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
            "chief_complaint": profile["complaint"],
            "diagnosis": profile["diagnosis"],
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
        log("patient_registered", "receptionist", sid(reception), reg_at, "visit", sid(vid),
            f"Registered {first} {last} ({mrn}), visit {visit_number}")
        log("triage_recorded", "nurse", nurse_id, triaged_at, "visit", sid(vid),
            f"Triage vitals recorded; assigned to {name_by_id.get(doctor_id)}")
        log("consultation_completed", "doctor", doctor_id, consult_ended, "visit", sid(vid),
            f"Consultation completed; diagnosis: {profile['diagnosis']}")

        # Prescription, advanced through the full workflow.
        meds = [{"name": m[0], "dose": m[1], "route": m[2], "frequency": m[3], "duration_days": m[4]}
                for m in profile["meds"]]
        ordered_at = consult_ended
        rxid = oid()
        rx_number = f"RX-2026-{rx_n:04d}"
        rx = {
            "_id": rxid,
            "rx_number": rx_number,
            "patient_id": sid(pid),
            "doctor_id": doctor_id,
            "visit_id": sid(vid),
            "department_id": sid(dept_map[dept_code]),
            "medications": meds,
            "status": "administered",          
            "order_source": vrec["visit_type"],
            "priority": priority,
            "flags": [],
            "sla_threshold_min": sla,
            "sla_breached": False,
            "notes": f"Prescribed for: {profile['complaint']}",
            "ordered_at": ordered_at,
            "created_at": ordered_at,
            "updated_at": ordered_at,
        }
        rx_n += 1
        log("prescription_created", "doctor", doctor_id, ordered_at, "prescription", sid(rxid),
            f"{rx_number} ordered: " + ", ".join(m["name"] for m in meds))

        submitted_at = ordered_at + timedelta(minutes=6)
        rx["submitted_at"] = submitted_at
        rx["tat_order_to_submit_min"] = minutes(ordered_at, submitted_at)
        log("prescription_submitted", "doctor", doctor_id, submitted_at, "prescription", sid(rxid),
            f"{rx_number} submitted for audit review")

        # Flag and resolution. verify_at is set after any flag hold.
        if flagkind == "none":
            verify_at = submitted_at + timedelta(minutes=12)
        else:
            flag_at = submitted_at + timedelta(minutes=1)
            is_amend = flagkind == "amended"
            issue = _AMEND_ISSUE if is_amend else (
                f"{priority.upper()} prescription approaching its {sla}-min SLA threshold")
            rec = _AMEND_REC if is_amend else "Expedite review to stay within the SLA target."
            # Hold time before the auditor acts.
            hold = {"on_time": 9, "late": sla + 30, "amended": 16}[flagkind]
            resolved_at = flag_at + timedelta(minutes=hold)
            res_type = {"on_time": "false_positive", "late": "accepted_risk",
                        "amended": "dose_adjusted"}[flagkind]
            res_note = {
                "on_time": "Reviewed against the catalogue; within acceptable range. No change required.",
                "late": "Reviewed and accepted after confirming the clinical indication with the doctor.",
                "amended": "Returned to the prescriber; dose recalculated for the patient's weight.",
            }[flagkind]

            audit_records.append({
                "_id": oid(),
                "prescription_id": sid(rxid),
                "visit_id": sid(vid),
                "patient_id": sid(pid),
                "flag_code": "high_dose" if is_amend else "sla_warning",
                "type": "automated" if is_amend else "sla_breach",
                "issue": issue,
                "severity": "high" if is_amend else "medium",
                "resolved": True,
                "resolved_by": sid(auditor),
                "resolved_at": resolved_at,
                "resolution_type": res_type,
                "resolution_note": res_note,
                "created_by": "system",
                "created_by_role": "system",
                "created_at": flag_at,
                "recommendation": rec,
                "drug_name": meds[0]["name"],
                "dose": meds[0]["dose"],
                "patient_age": age,
                "countersigned": False,
            })
            log("flag_raised", "system", "system", flag_at, "prescription", sid(rxid),
                f"{rx_number}: {issue}")

            if is_amend:
                # Doctor amendment loop: returned -> amended -> resubmitted.
                returned_at = flag_at + timedelta(minutes=4)
                amended_at = returned_at + timedelta(minutes=6)
                resubmitted_at = amended_at + timedelta(minutes=3)
                log("prescription_returned", "auditor", sid(auditor), returned_at, "prescription", sid(rxid),
                    f"{rx_number} returned to prescriber for amendment")
                log("prescription_amended", "doctor", doctor_id, amended_at, "prescription", sid(rxid),
                    f"{rx_number} amended: dose adjusted for patient weight")
                log("prescription_resubmitted", "doctor", doctor_id, resubmitted_at, "prescription", sid(rxid),
                    f"{rx_number} resubmitted after amendment")
                rx["amended_at"] = amended_at
                rx["amendment_note"] = "Dose adjusted for patient weight following audit flag."
                verify_at = max(resolved_at, resubmitted_at) + timedelta(minutes=2)
            else:
                verify_at = resolved_at + timedelta(minutes=2)
                if flagkind == "late":
                    rx["sla_breached"] = True
                    rx["sla_breach_duration_min"] = float(hold - sla)
                    rx["tat_breached_at"] = flag_at + timedelta(minutes=sla)

            log("flag_resolved", "auditor", sid(auditor), resolved_at, "prescription", sid(rxid),
                f"{rx_number} flag resolved ({res_type})")

        # Verify, dispense, administer.
        rx["verified_at"] = verify_at
        rx["auditor_approved_at"] = verify_at
        rx["auditor_id"] = sid(auditor)
        rx["tat_submit_to_verify_min"] = minutes(submitted_at, verify_at)
        log("prescription_verified", "auditor", sid(auditor), verify_at, "prescription", sid(rxid),
            f"{rx_number} verified and approved for pharmacy")

        disp_at = verify_at + timedelta(minutes=14)
        rx["dispensed_at"] = disp_at
        rx["dispensed_by_id"] = sid(pharmacist)
        rx["dispensed_by_name"] = name_by_id.get(sid(pharmacist))
        rx["receipt_number"] = f"RCP-{day_key}-{rx_n:04d}"
        rx["tat_verify_to_dispense_min"] = minutes(verify_at, disp_at)
        log("prescription_dispensed", "pharmacist", sid(pharmacist), disp_at, "prescription", sid(rxid),
            f"{rx_number} dispensed")

        admin_at = disp_at + timedelta(minutes=22)
        rx["administered_at"] = admin_at
        rx["administered_by_id"] = nurse_id
        rx["administered_by_name"] = name_by_id.get(nurse_id)
        rx["administered_dose"] = meds[0]["dose"]
        rx["administered_route"] = meds[0]["route"]
        rx["tat_dispense_to_admin_min"] = minutes(disp_at, admin_at)
        rx["tat_total_min"] = minutes(ordered_at, admin_at)
        log("prescription_administered", "nurse", nurse_id, admin_at, "prescription", sid(rxid),
            f"{rx_number} administered to patient")

        prescriptions.append(rx)
        vrec["prescription_ids"] = [sid(rxid)]

        # Bill: paid for discharged patients, unpaid for those on the ward.
        med_desc = f"{meds[0]['name']} {meds[0]['dose']}"
        line_items = [
            {"category": "consultation", "description": "OPD Consultation",
             "quantity": 1, "unit_price": 800.0, "total_price": 800.0},
            {"category": "pharmacy", "description": med_desc,
             "quantity": 1, "unit_price": 900.0, "total_price": 900.0},
            {"category": "lab", "description": "Laboratory tests",
             "quantity": 1, "unit_price": 400.0, "total_price": 400.0},
        ]
        if outcome == "ward":
            line_items.append({"category": "ward", "description": "Inpatient bed (per day)",
                               "quantity": 1, "unit_price": 2500.0, "total_price": 2500.0})
        subtotal = sum(li["total_price"] for li in line_items)
        bill_created = admin_at + timedelta(minutes=20)
        bill = {
            "_id": oid(),
            "bill_number": f"BILL-2026-{bill_n:04d}",
            "visit_id": sid(vid),
            "visit_number": visit_number,
            "patient_id": sid(pid),
            "line_items": line_items,
            "subtotal": float(subtotal),
            "discount_amount": 0.0,
            "tax_amount": 0.0,
            "total_amount": float(subtotal),
            "created_at": bill_created,
        }
        if outcome == "discharged":
            
            # Settled in full, then discharged.
            paid_at = bill_created + timedelta(minutes=25)
            bill["status"] = "paid"
            bill["payments"] = [{"amount": float(subtotal), "method": "mpesa", "received_at": paid_at}]
            vrec["billing_completed_at"] = paid_at
            vrec["discharged_at"] = paid_at + timedelta(minutes=15)
            vrec["status"] = "discharged"
            log("payment_received", "billing", sid(billing), paid_at, "bill", sid(bill["_id"]),
                f"{bill['bill_number']} paid in full (KES {subtotal:,.0f})")
            log("patient_discharged", "nurse", nurse_id, vrec["discharged_at"], "visit", sid(vid),
                f"{first} {last} discharged")
        else:
            # On the ward: bill raised but not yet settled.
            bill["status"] = "finalized"
            bill["payments"] = []
            log("bill_finalized", "billing", sid(billing), bill_created, "bill", sid(bill["_id"]),
                f"{bill['bill_number']} finalized (KES {subtotal:,.0f}); payment pending at discharge")
        bills.append(bill)
        bill_n += 1

        visits.append(vrec)

    # Seed per-day counters so live registrations continue the sequence.
    counters = []
    for day_key, seq in mrn_counters.items():
        counters.append({"_id": f"mrn_{day_key}", "seq": seq})
    for day_key, seq in visit_counters.items():
        counters.append({"_id": f"visit_{day_key}", "seq": seq})

    return patients, visits, prescriptions, audit_records, bills, activity_log, counters


_ALL_USERS_CACHE = []
