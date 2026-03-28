"""
TAT-PAS Database Setup Script
==============================
Creates all MongoDB collections with JSON Schema validation and indexes.
Also seeds reference data (SLA config, drug safety rules).

Usage:
    python backend/setup_db.py

Environment variables:
    MONGO_URI   - MongoDB connection string  (default: mongodb://localhost:27017)
    MONGO_DB    - Database name              (default: tatpas)
"""

import os
import sys
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid, OperationFailure

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB",  "tatpas")

ROLES = ["receptionist", "nurse", "doctor", "admin", "pharmacist", "billing", "auditor"]

BED_TYPES    = ["general", "icu", "hdu", "nicu", "isolation", "maternity", "birthing", "paediatric", "day_case", "consultation", "procedure_room"]
BED_STATUSES = ["available", "occupied", "reserved", "cleaning", "maintenance"]

ORDER_SOURCES  = ["opd", "ipd", "emergency", "theatre", "maternity", "paediatric", "nicu", "discharge"]
PRIORITIES     = ["stat", "urgent", "routine", "discharge", "nicu", "chemo"]
VISIT_TYPES    = ["opd", "ipd", "emergency", "day_surgery", "maternity", "paediatric", "nicu"]
VISIT_STATUSES = [
    "registered", "triaged", "waiting_for_doctor", "in_consultation",
    "awaiting_results", "treatment_in_progress", "admitted", "in_ward",
    "ready_for_discharge", "discharged", "cancelled",
]
AUDIT_TYPES      = ["automated", "manual", "sla_breach", "sla_warning", "status_change"]
RESOLUTION_TYPES = ["accepted_risk", "dose_adjusted", "drug_changed", "prescription_cancelled", "false_positive"]

COLLECTIONS = {
    "users": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["username", "email", "password_hash", "role", "created_at"],
                "additionalProperties": True,
                "properties": {
                    "username":      {"bsonType": "string", "minLength": 3, "maxLength": 64},
                    "full_name":     {"bsonType": ["string", "null"], "maxLength": 128},
                    "email":         {"bsonType": "string", "pattern": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"},
                    "password_hash": {"bsonType": "string"},
                    "role":          {"bsonType": "string", "enum": ROLES},
                    "department_id": {"bsonType": ["string", "null"]},
                    "is_active":     {"bsonType": "bool"},
                    "created_at":    {"bsonType": "date"},
                    "last_login":    {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("username", ASCENDING)],    "options": {"unique": True, "name": "users_username_unique"}},
            {"keys": [("email", ASCENDING)],       "options": {"unique": True, "name": "users_email_unique"}},
            {"keys": [("role", ASCENDING)],        "options": {"name": "users_role"}},
            {"keys": [("department_id", ASCENDING)], "options": {"name": "users_department", "sparse": True}},
        ],
    },

    "departments": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "code", "type", "floor", "is_active", "created_at"],
                "additionalProperties": True,
                "properties": {
                    "name":              {"bsonType": "string", "minLength": 1, "maxLength": 200},
                    "code":              {"bsonType": "string", "minLength": 1, "maxLength": 20},
                    "type":              {"bsonType": "string", "enum": ["clinical", "diagnostic", "support", "administrative"]},
                    "floor":             {"bsonType": "string"},
                    "wing":              {"bsonType": ["string", "null"]},
                    "description":       {"bsonType": ["string", "null"]},
                    "head_user_id":      {"bsonType": ["string", "null"]},
                    "accepts_emergency": {"bsonType": "bool"},
                    "is_active":         {"bsonType": "bool"},
                    "bed_count":         {"bsonType": ["int", "null"]},
                    "created_at":        {"bsonType": "date"},
                    "updated_at":        {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("code", ASCENDING)],              "options": {"unique": True, "name": "departments_code_unique"}},
            {"keys": [("type", ASCENDING)],              "options": {"name": "departments_type"}},
            {"keys": [("is_active", ASCENDING)],         "options": {"name": "departments_active"}},
            {"keys": [("accepts_emergency", ASCENDING)], "options": {"name": "departments_emergency"}},
        ],
    },

    "beds": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["department_id", "ward_name", "room_number", "bed_number", "bed_label", "bed_type", "status", "created_at"],
                "additionalProperties": True,
                "properties": {
                    "department_id":       {"bsonType": "string"},
                    "ward_name":           {"bsonType": "string"},
                    "room_number":         {"bsonType": "string"},
                    "bed_number":          {"bsonType": "string"},
                    "bed_label":           {"bsonType": "string"},
                    "bed_type":            {"bsonType": "string", "enum": BED_TYPES},
                    "status":              {"bsonType": "string", "enum": BED_STATUSES},
                    "current_patient_id":  {"bsonType": ["string", "null"]},
                    "current_admission_id":{"bsonType": ["string", "null"]},
                    "last_cleaned_at":     {"bsonType": ["date", "null"]},
                    "notes":               {"bsonType": ["string", "null"]},
                    "created_at":          {"bsonType": "date"},
                    "updated_at":          {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("department_id", ASCENDING)], "options": {"name": "beds_department"}},
            {"keys": [("status", ASCENDING)],        "options": {"name": "beds_status"}},
            {"keys": [("bed_type", ASCENDING)],      "options": {"name": "beds_type"}},
            {"keys": [("department_id", ASCENDING), ("bed_label", ASCENDING)], "options": {"unique": True, "name": "beds_dept_label_unique"}},
            {"keys": [("current_patient_id", ASCENDING)], "options": {"name": "beds_patient", "sparse": True}},
        ],
    },

    "patients": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["mrn", "first_name", "last_name", "created_at"],
                "additionalProperties": True,
                "properties": {
                    "mrn":        {"bsonType": "string"},
                    "first_name": {"bsonType": "string", "minLength": 1, "maxLength": 100},
                    "last_name":  {"bsonType": "string", "minLength": 1, "maxLength": 100},
                    "middle_name":{"bsonType": ["string", "null"]},
                    "dob":        {"bsonType": ["date", "null"]},
                    "gender":     {"bsonType": ["string", "null"], "enum": ["male", "female", "other", None]},
                    "blood_group":{"bsonType": ["string", "null"], "enum": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown", None]},
                    "weight_kg":  {"bsonType": ["double", "int", "null"]},
                    "contact":    {"bsonType": ["object", "null"]},
                    "emergency_contact": {"bsonType": ["object", "null"]},
                    "allergies":          {"bsonType": ["array", "null"]},
                    "chronic_conditions": {"bsonType": ["array", "null"]},
                    "current_medications":{"bsonType": ["array", "null"]},
                    "insurance":   {"bsonType": ["object", "null"]},
                    "next_of_kin": {"bsonType": ["object", "null"]},
                    "is_pregnant":  {"bsonType": ["bool", "null"]},
                    "is_paediatric":{"bsonType": ["bool", "null"]},
                    "is_neonate":   {"bsonType": ["bool", "null"]},
                    "registered_by":{"bsonType": ["string", "null"]},
                    "created_at":   {"bsonType": "date"},
                    "updated_at":   {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("mrn", ASCENDING)],                                  "options": {"unique": True, "name": "patients_mrn_unique"}},
            {"keys": [("last_name", ASCENDING), ("first_name", ASCENDING)], "options": {"name": "patients_name"}},
            {"keys": [("contact.phone", ASCENDING)],                        "options": {"name": "patients_phone", "sparse": True}},
            {"keys": [("dob", ASCENDING)],                                  "options": {"name": "patients_dob", "sparse": True}},
        ],
    },

    "visits": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["patient_id", "visit_number", "visit_type", "department_id", "status", "registered_at", "created_at"],
                "additionalProperties": True,
                "properties": {
                    "patient_id":   {"bsonType": ["objectId", "string"]},
                    "visit_number": {"bsonType": "string"},
                    "visit_type":   {"bsonType": "string", "enum": VISIT_TYPES},
                    "department_id":{"bsonType": "string"},
                    "chief_complaint":{"bsonType": ["string", "null"]},
                    "priority":     {"bsonType": ["string", "null"], "enum": ["routine", "urgent", "critical", "immediate", None]},
                    "status":       {"bsonType": "string", "enum": VISIT_STATUSES},
                    "assigned_doctor_id": {"bsonType": ["string", "null"]},
                    "triage_nurse_id":    {"bsonType": ["string", "null"]},
                    "bed_id":             {"bsonType": ["string", "null"]},
                    "prescription_ids":   {"bsonType": "array"},
                    "registered_at":           {"bsonType": "date"},
                    "triaged_at":              {"bsonType": ["date", "null"]},
                    "consultation_started_at": {"bsonType": ["date", "null"]},
                    "consultation_ended_at":   {"bsonType": ["date", "null"]},
                    "admitted_at":             {"bsonType": ["date", "null"]},
                    "discharged_at":           {"bsonType": ["date", "null"]},
                    "created_at":  {"bsonType": "date"},
                    "updated_at":  {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("visit_number", ASCENDING)],    "options": {"unique": True, "name": "visits_number_unique"}},
            {"keys": [("patient_id", ASCENDING)],      "options": {"name": "visits_patient"}},
            {"keys": [("status", ASCENDING)],          "options": {"name": "visits_status"}},
            {"keys": [("department_id", ASCENDING)],   "options": {"name": "visits_department"}},
            {"keys": [("registered_at", DESCENDING)],  "options": {"name": "visits_registered_desc"}},
            {"keys": [("assigned_doctor_id", ASCENDING)], "options": {"name": "visits_doctor", "sparse": True}},
        ],
    },

    "prescriptions": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["patient_id", "doctor_id", "medications", "status", "ordered_at", "created_at"],
                "additionalProperties": True,
                "properties": {
                    "rx_number":   {"bsonType": ["string", "null"]},
                    "patient_id":  {"bsonType": ["objectId", "string"]},
                    "doctor_id":   {"bsonType": ["objectId", "string"]},
                    "visit_id":    {"bsonType": ["objectId", "string", "null"]},
                    "department_id":{"bsonType": ["string", "null"]},
                    "ward_id":     {"bsonType": ["string", "null"]},
                    "order_source":{"bsonType": ["string", "null"], "enum": ORDER_SOURCES + [None]},
                    "priority":    {"bsonType": ["string", "null"], "enum": PRIORITIES + [None]},
                    "medications": {
                        "bsonType": "array",
                        "minItems": 1,
                        "items": {
                            "bsonType": "object",
                            "required": ["name", "dose", "route", "frequency", "duration_days"],
                            "properties": {
                                "name":          {"bsonType": "string"},
                                "dose":          {"bsonType": "string"},
                                "route":         {"bsonType": "string"},
                                "frequency":     {"bsonType": "string"},
                                "duration_days": {"bsonType": "int", "minimum": 1},
                                "dose_per_kg":   {"bsonType": ["double", "int", "null"]},
                                "is_high_alert": {"bsonType": ["bool", "null"]},
                                "is_controlled": {"bsonType": ["bool", "null"]},
                            },
                        },
                    },
                    "status": {
                        "bsonType": "string",
                        "enum": ["draft", "submitted", "flagged", "pending_amendment", "verified", "dispensed", "administered", "archived"],
                    },
                    "ordered_at":      {"bsonType": "date"},
                    "submitted_at":    {"bsonType": ["date", "null"]},
                    "verified_at":     {"bsonType": ["date", "null"]},
                    "dispensed_at":    {"bsonType": ["date", "null"]},
                    "administered_at": {"bsonType": ["date", "null"]},
                    "dispensed_by_id":    {"bsonType": ["string", "null"]},
                    "administered_by_id": {"bsonType": ["string", "null"]},
                    "tat_order_to_submit_min":    {"bsonType": ["double", "int", "null"]},
                    "tat_submit_to_verify_min":   {"bsonType": ["double", "int", "null"]},
                    "tat_flag_hold_min":          {"bsonType": ["double", "int", "null"]},
                    "tat_verify_to_dispense_min": {"bsonType": ["double", "int", "null"]},
                    "tat_dispense_to_admin_min":  {"bsonType": ["double", "int", "null"]},
                    "tat_pharmacy_min":           {"bsonType": ["double", "int", "null"]},
                    "tat_total_min":              {"bsonType": ["double", "int", "null"]},
                    "sla_threshold_min":          {"bsonType": ["double", "int", "null"]},
                    "sla_breached":               {"bsonType": ["bool", "null"]},
                    "sla_breach_duration_min":    {"bsonType": ["double", "int", "null"]},
                    "tat_breached_at":            {"bsonType": ["date", "null"]},
                    "flags":             {"bsonType": "array"},
                    "notes":             {"bsonType": ["string", "null"]},
                    "pharmacist_comment":{"bsonType": ["string", "null"]},
                    "weight_kg":         {"bsonType": ["double", "int", "null"]},
                    "created_at":        {"bsonType": "date"},
                    "updated_at":        {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationLevel": "moderate",
        "validationAction": "error",
        "indexes": [
            {"keys": [("rx_number", ASCENDING)],   "options": {"unique": True, "name": "prescriptions_rx_number_unique", "sparse": True}},
            {"keys": [("patient_id", ASCENDING)],  "options": {"name": "prescriptions_patient_id"}},
            {"keys": [("doctor_id", ASCENDING)],   "options": {"name": "prescriptions_doctor_id"}},
            {"keys": [("visit_id", ASCENDING)],    "options": {"name": "prescriptions_visit", "sparse": True}},
            {"keys": [("status", ASCENDING)],      "options": {"name": "prescriptions_status"}},
            {"keys": [("ordered_at", DESCENDING)], "options": {"name": "prescriptions_ordered_at_desc"}},
            {"keys": [("status", ASCENDING), ("ordered_at", DESCENDING)],                          "options": {"name": "prescriptions_status_ordered"}},
            {"keys": [("status", ASCENDING), ("priority", ASCENDING), ("submitted_at", ASCENDING)],"options": {"name": "prescriptions_sla_scan", "sparse": True}},
            {"keys": [("sla_breached", ASCENDING)], "options": {"name": "prescriptions_sla_breached", "sparse": True}},
            {"keys": [("flags", ASCENDING)],        "options": {"name": "prescriptions_flags", "sparse": True}},
            {"keys": [("department_id", ASCENDING)],"options": {"name": "prescriptions_department", "sparse": True}},
        ],
    },

    "audit_records": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["prescription_id", "flag_code", "created_by", "created_by_role", "type", "issue", "severity", "resolved", "created_at"],
                "additionalProperties": True,
                "properties": {
                    "prescription_id": {"bsonType": ["objectId", "string"]},
                    "visit_id":        {"bsonType": ["objectId", "string", "null"]},
                    "patient_id":      {"bsonType": ["objectId", "string", "null"]},
                    "flag_code":       {"bsonType": "string"},
                    "created_by":      {"bsonType": ["objectId", "string"]},
                    "created_by_role": {"bsonType": "string", "enum": ["system"] + ROLES},
                    "type":            {"bsonType": "string", "enum": AUDIT_TYPES},
                    "issue":           {"bsonType": "string", "minLength": 1},
                    "severity":        {"bsonType": "string", "enum": ["low", "medium", "high", "critical"]},
                    "recommendation":  {"bsonType": ["string", "null"]},
                    "resolved":        {"bsonType": "bool"},
                    "resolved_by":     {"bsonType": ["objectId", "string", "null"]},
                    "resolved_at":     {"bsonType": ["date", "null"]},
                    "resolution_type": {"bsonType": ["string", "null"], "enum": RESOLUTION_TYPES + [None]},
                    "resolution_note": {"bsonType": ["string", "null"]},
                    "created_at":      {"bsonType": "date"},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("prescription_id", ASCENDING)], "options": {"name": "audit_prescription_id"}},
            {"keys": [("flag_code", ASCENDING)],       "options": {"name": "audit_flag_code"}},
            {"keys": [("resolved", ASCENDING)],        "options": {"name": "audit_resolved"}},
            {"keys": [("severity", ASCENDING)],        "options": {"name": "audit_severity"}},
            {"keys": [("created_at", DESCENDING)],     "options": {"name": "audit_created_at_desc"}},
            {"keys": [("prescription_id", ASCENDING), ("resolved", ASCENDING)], "options": {"name": "audit_prescription_unresolved"}},
        ],
    },

    "consultation_notes": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["visit_id", "patient_id", "doctor_id", "created_at"],
                "additionalProperties": True,
                "properties": {
                    "visit_id":   {"bsonType": "string"},
                    "patient_id": {"bsonType": "string"},
                    "doctor_id":  {"bsonType": "string"},
                    "doctor_name":{"bsonType": ["string", "null"]},
                    "consultation_room":    {"bsonType": ["string", "null"]},
                    "assisting_nurse_id":   {"bsonType": ["string", "null"]},
                    "assisting_nurse_name": {"bsonType": ["string", "null"]},
                    "chief_complaint":      {"bsonType": ["string", "null"]},
                    "clinical_findings":    {"bsonType": ["string", "null"]},
                    "diagnosis":            {"bsonType": ["string", "null"]},
                    "recommendations":      {"bsonType": ["string", "null"]},
                    "plan_of_care":         {"bsonType": ["string", "null"]},
                    "follow_up_instructions":{"bsonType": ["string", "null"]},
                    "follow_up_date":       {"bsonType": ["date", "null"]},
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationLevel": "moderate",
        "validationAction": "error",
        "indexes": [
            {"keys": [("visit_id", ASCENDING)],   "options": {"unique": True, "name": "notes_visit_unique"}},
            {"keys": [("patient_id", ASCENDING)], "options": {"name": "notes_patient"}},
        ],
    },

    "consultation_rooms": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["department_id", "room_number", "status", "created_at"],
                "additionalProperties": True,
                "properties": {
                    "department_id":      {"bsonType": "string"},
                    "room_number":        {"bsonType": "string"},
                    "room_name":          {"bsonType": ["string", "null"]},
                    "floor":              {"bsonType": ["string", "null"]},
                    "status":             {"bsonType": "string", "enum": ["available", "occupied", "cleaning", "maintenance"]},
                    "current_doctor_id":  {"bsonType": ["string", "null"]},
                    "current_patient_id": {"bsonType": ["string", "null"]},
                    "notes":              {"bsonType": ["string", "null"]},
                    "created_at":         {"bsonType": "date"},
                    "updated_at":         {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationLevel": "moderate",
        "validationAction": "error",
        "indexes": [
            {"keys": [("department_id", ASCENDING)], "options": {"name": "rooms_department"}},
            {"keys": [("status", ASCENDING)],        "options": {"name": "rooms_status"}},
        ],
    },

    "bills": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["visit_id", "patient_id", "status", "line_items", "subtotal", "total_amount", "created_at"],
                "additionalProperties": True,
                "properties": {
                    "visit_id":   {"bsonType": ["objectId", "string"]},
                    "patient_id": {"bsonType": ["objectId", "string"]},
                    "status":     {"bsonType": "string", "enum": ["open", "finalized", "paid", "partially_paid", "waived"]},
                    "line_items": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "object",
                            "required": ["category", "description", "quantity", "unit_price", "total_price"],
                            "properties": {
                                "category":    {"bsonType": "string"},
                                "description": {"bsonType": "string"},
                                "quantity":    {"bsonType": "number"},
                                "unit_price":  {"bsonType": "number"},
                                "total_price": {"bsonType": "number"},
                            },
                        },
                    },
                    "subtotal":        {"bsonType": "number"},
                    "discount_amount": {"bsonType": "number"},
                    "discount_reason": {"bsonType": ["string", "null"]},
                    "tax_amount":      {"bsonType": "number"},
                    "total_amount":    {"bsonType": "number"},
                    "payments": {
                        "bsonType": "array",
                        "items": {
                            "bsonType": "object",
                            "required": ["amount", "method", "received_at"],
                            "properties": {
                                "amount":           {"bsonType": "number"},
                                "method":           {"bsonType": "string", "enum": ["cash", "card", "insurance", "mobile_money", "nhif", "mpesa"]},
                                "reference_number": {"bsonType": ["string", "null"]},
                                "received_by":      {"bsonType": ["string", "null"]},
                                "received_at":      {"bsonType": "date"},
                            },
                        },
                    },
                    "insurance_details": {"bsonType": ["object", "null"]},
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("visit_id", ASCENDING)],    "options": {"unique": True, "name": "bills_visit_unique"}},
            {"keys": [("patient_id", ASCENDING)],  "options": {"name": "bills_patient"}},
            {"keys": [("status", ASCENDING)],      "options": {"name": "bills_status"}},
            {"keys": [("created_at", DESCENDING)], "options": {"name": "bills_created_desc"}},
        ],
    },

    "counters": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["_id", "seq"],
                "additionalProperties": True,
                "properties": {
                    "_id": {"bsonType": "string"},
                    "seq": {"bsonType": "int"},
                },
            }
        },
        "validationLevel": "moderate",
        "validationAction": "error",
        "indexes": [],
    },

    # Reference data collections

    "sla_config": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["priority", "threshold_minutes"],
                "additionalProperties": True,
                "properties": {
                    "priority":          {"bsonType": "string", "enum": PRIORITIES},
                    "threshold_minutes": {"bsonType": "int"},
                    "description":       {"bsonType": ["string", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("priority", ASCENDING)], "options": {"unique": True, "name": "sla_priority_unique"}},
        ],
    },

    "drug_interactions": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["drug_a", "drug_b", "severity", "interaction"],
                "additionalProperties": True,
                "properties": {
                    "drug_a":          {"bsonType": "string"},
                    "drug_b":          {"bsonType": "string"},
                    "severity":        {"bsonType": "string", "enum": ["low", "medium", "high"]},
                    "interaction":     {"bsonType": "string"},
                    "recommendation":  {"bsonType": ["string", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("drug_a", ASCENDING), ("drug_b", ASCENDING)], "options": {"name": "ddi_pair"}},
        ],
    },

    "controlled_substances": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "schedule", "requires_tracking"],
                "additionalProperties": True,
                "properties": {
                    "name":              {"bsonType": "string"},
                    "schedule":          {"bsonType": "string"},
                    "requires_tracking": {"bsonType": "bool"},
                    "description":       {"bsonType": ["string", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("name", ASCENDING)], "options": {"unique": True, "name": "controlled_name_unique"}},
        ],
    },

    "category_x_drugs": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "risk_description"],
                "additionalProperties": True,
                "properties": {
                    "name":             {"bsonType": "string"},
                    "risk_description": {"bsonType": "string"},
                    "alternative":      {"bsonType": ["string", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("name", ASCENDING)], "options": {"unique": True, "name": "catx_name_unique"}},
        ],
    },

    "high_alert_drugs": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "category", "risk_factors"],
                "additionalProperties": True,
                "properties": {
                    "name":               {"bsonType": "string"},
                    "category":           {"bsonType": "string"},
                    "risk_factors":       {"bsonType": "array"},
                    "special_monitoring": {"bsonType": ["string", "null"]},
                },
            }
        },
        "validationLevel": "strict",
        "validationAction": "error",
        "indexes": [
            {"keys": [("name", ASCENDING)], "options": {"unique": True, "name": "high_alert_name_unique"}},
        ],
    },

    "daily_reports": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["report_date", "generated_at", "summary"],
                "additionalProperties": True,
                "properties": {
                    "report_date":  {"bsonType": "date"},
                    "generated_at": {"bsonType": "date"},
                    "summary":      {"bsonType": "object"},
                },
            }
        },
        "validationLevel": "moderate",
        "validationAction": "warn",
        "indexes": [
            {"keys": [("report_date", DESCENDING)], "options": {"unique": True, "name": "daily_report_date_unique"}},
        ],
    },
}


SEED_DATA = {
    "sla_config": [
        {"priority": "stat",      "threshold_minutes": 15,  "description": "STAT orders must be processed within 15 minutes"},
        {"priority": "urgent",    "threshold_minutes": 30,  "description": "Urgent orders must be processed within 30 minutes"},
        {"priority": "routine",   "threshold_minutes": 60,  "description": "Routine orders must be processed within 60 minutes"},
        {"priority": "discharge", "threshold_minutes": 45,  "description": "Discharge orders must be processed within 45 minutes"},
        {"priority": "nicu",      "threshold_minutes": 20,  "description": "NICU orders must be processed within 20 minutes"},
        {"priority": "chemo",     "threshold_minutes": 120, "description": "Chemotherapy orders must be processed within 120 minutes"},
    ],
    "drug_interactions": [
        {"drug_a": "warfarin",        "drug_b": "aspirin",        "severity": "high",   "interaction": "Increased bleeding risk",              "recommendation": "Monitor INR closely"},
        {"drug_a": "methotrexate",    "drug_b": "nsaids",         "severity": "high",   "interaction": "Increased methotrexate toxicity",      "recommendation": "Avoid combination or reduce dose"},
        {"drug_a": "digoxin",         "drug_b": "furosemide",     "severity": "medium", "interaction": "Hypokalemia increases digoxin toxicity","recommendation": "Monitor potassium levels"},
        {"drug_a": "lithium",         "drug_b": "nsaids",         "severity": "high",   "interaction": "Reduced lithium clearance",             "recommendation": "Monitor lithium levels"},
        {"drug_a": "ace inhibitors",  "drug_b": "potassium",      "severity": "medium", "interaction": "Hyperkalemia risk",                     "recommendation": "Monitor potassium levels"},
        {"drug_a": "ssri",            "drug_b": "tramadol",       "severity": "high",   "interaction": "Serotonin syndrome risk",               "recommendation": "Avoid combination"},
        {"drug_a": "macrolide",       "drug_b": "statins",        "severity": "high",   "interaction": "Rhabdomyolysis risk",                   "recommendation": "Consider statin holiday"},
        {"drug_a": "metronidazole",   "drug_b": "warfarin",       "severity": "high",   "interaction": "Increased anticoagulation",             "recommendation": "Monitor INR closely"},
        {"drug_a": "phenytoin",       "drug_b": "valproate",      "severity": "medium", "interaction": "Altered phenytoin levels",              "recommendation": "Monitor phenytoin levels"},
        {"drug_a": "rifampicin",      "drug_b": "contraceptives", "severity": "medium", "interaction": "Reduced contraceptive efficacy",        "recommendation": "Use additional contraception"},
        {"drug_a": "ciprofloxacin",   "drug_b": "theophylline",   "severity": "medium", "interaction": "Increased theophylline levels",         "recommendation": "Monitor theophylline levels"},
        {"drug_a": "amiodarone",      "drug_b": "warfarin",       "severity": "high",   "interaction": "Increased anticoagulation",             "recommendation": "Reduce warfarin dose by 30-50%"},
        {"drug_a": "carbamazepine",   "drug_b": "contraceptives", "severity": "medium", "interaction": "Reduced contraceptive efficacy",        "recommendation": "Use additional contraception"},
        {"drug_a": "azithromycin",    "drug_b": "simvastatin",    "severity": "high",   "interaction": "Rhabdomyolysis risk",                   "recommendation": "Consider statin holiday"},
        {"drug_a": "clarithromycin",  "drug_b": "warfarin",       "severity": "high",   "interaction": "Increased anticoagulation",             "recommendation": "Monitor INR closely"},
        {"drug_a": "fluconazole",     "drug_b": "warfarin",       "severity": "high",   "interaction": "Increased anticoagulation",             "recommendation": "Monitor INR closely"},
        {"drug_a": "omeprazole",      "drug_b": "clopidogrel",    "severity": "medium", "interaction": "Reduced clopidogrel efficacy",          "recommendation": "Consider alternative PPI"},
        {"drug_a": "verapamil",       "drug_b": "beta blockers",  "severity": "high",   "interaction": "Heart block risk",                     "recommendation": "Avoid combination"},
        {"drug_a": "metformin",       "drug_b": "contrast media", "severity": "high",   "interaction": "Lactic acidosis risk",                 "recommendation": "Hold metformin 48h before/after contrast"},
        {"drug_a": "aminoglycosides", "drug_b": "furosemide",     "severity": "medium", "interaction": "Increased ototoxicity",                "recommendation": "Monitor hearing and renal function"},
        {"drug_a": "allopurinol",     "drug_b": "azathioprine",   "severity": "high",   "interaction": "Bone marrow suppression",              "recommendation": "Reduce azathioprine dose to 25%"},
        {"drug_a": "sildenafil",      "drug_b": "nitrates",       "severity": "high",   "interaction": "Severe hypotension",                   "recommendation": "Absolute contraindication"},
        {"drug_a": "ketoconazole",    "drug_b": "statins",        "severity": "high",   "interaction": "Rhabdomyolysis risk",                  "recommendation": "Avoid combination"},
        {"drug_a": "levodopa",        "drug_b": "iron",           "severity": "medium", "interaction": "Reduced levodopa absorption",          "recommendation": "Separate administration by 2 hours"},
        {"drug_a": "tetracyclines",   "drug_b": "calcium",        "severity": "medium", "interaction": "Reduced antibiotic absorption",        "recommendation": "Separate administration by 2 hours"},
    ],
    "controlled_substances": [
        {"name": "morphine",      "schedule": "II",  "requires_tracking": True, "description": "Opioid analgesic"},
        {"name": "fentanyl",      "schedule": "II",  "requires_tracking": True, "description": "Opioid analgesic"},
        {"name": "oxycodone",     "schedule": "II",  "requires_tracking": True, "description": "Opioid analgesic"},
        {"name": "hydromorphone", "schedule": "II",  "requires_tracking": True, "description": "Opioid analgesic"},
        {"name": "methadone",     "schedule": "II",  "requires_tracking": True, "description": "Opioid analgesic"},
        {"name": "midazolam",     "schedule": "IV",  "requires_tracking": True, "description": "Benzodiazepine sedative"},
        {"name": "lorazepam",     "schedule": "IV",  "requires_tracking": True, "description": "Benzodiazepine anxiolytic"},
        {"name": "diazepam",      "schedule": "IV",  "requires_tracking": True, "description": "Benzodiazepine"},
        {"name": "ketamine",      "schedule": "III", "requires_tracking": True, "description": "Dissociative anesthetic"},
        {"name": "pethidine",     "schedule": "II",  "requires_tracking": True, "description": "Opioid analgesic"},
    ],
    "category_x_drugs": [
        {"name": "isotretinoin", "risk_description": "Severe birth defects",                         "alternative": "Topical retinoids for mild acne"},
        {"name": "warfarin",     "risk_description": "Fetal warfarin syndrome",                       "alternative": "Heparin or LMWH"},
        {"name": "methotrexate", "risk_description": "Neural tube defects, skeletal abnormalities",   "alternative": "Discontinue before conception"},
        {"name": "misoprostol",  "risk_description": "Uterine contractions, birth defects",           "alternative": "Avoid in pregnancy"},
        {"name": "thalidomide",  "risk_description": "Severe limb abnormalities",                     "alternative": "Contraindicated in pregnancy"},
        {"name": "finasteride",  "risk_description": "Abnormalities of male fetus genitalia",         "alternative": "Contraindicated in women of childbearing age"},
        {"name": "statins",      "risk_description": "Skeletal malformations",                        "alternative": "Discontinue during pregnancy"},
        {"name": "acitretin",    "risk_description": "Craniofacial, cardiac, thymic defects",         "alternative": "Contraindicated in pregnancy"},
    ],
    "high_alert_drugs": [
        {"name": "insulin",                  "category": "Endocrine",     "risk_factors": ["Hypoglycemia", "Dosing errors"],                  "special_monitoring": "Blood glucose monitoring"},
        {"name": "heparin",                  "category": "Anticoagulant", "risk_factors": ["Hemorrhage", "Thrombocytopenia"],                 "special_monitoring": "APTT, platelet count"},
        {"name": "warfarin",                 "category": "Anticoagulant", "risk_factors": ["Hemorrhage", "Drug interactions"],               "special_monitoring": "INR monitoring"},
        {"name": "potassium",                "category": "Electrolyte",   "risk_factors": ["Cardiac arrhythmias", "Rapid infusion"],         "special_monitoring": "ECG, serum potassium"},
        {"name": "magnesium sulfate",        "category": "Electrolyte",   "risk_factors": ["Respiratory depression", "Cardiac arrest"],      "special_monitoring": "Respiratory rate, reflexes"},
        {"name": "chemotherapy agents",      "category": "Oncology",      "risk_factors": ["Cytotoxicity", "Dosing errors"],                 "special_monitoring": "Blood counts, organ function"},
        {"name": "opioids",                  "category": "Analgesic",     "risk_factors": ["Respiratory depression", "Sedation"],           "special_monitoring": "Respiratory rate, sedation score"},
        {"name": "neuromuscular blockers",   "category": "Anesthetic",    "risk_factors": ["Paralysis without sedation", "Prolonged paralysis"], "special_monitoring": "Train-of-four monitoring"},
    ],
}


def create_collection(db, name: str, spec: dict) -> None:
    validator        = spec.get("validator")
    validation_level = spec.get("validationLevel", "moderate")
    validation_action= spec.get("validationAction", "error")
    try:
        db.create_collection(name, validator=validator, validationLevel=validation_level, validationAction=validation_action)
        print(f"  [CREATED] {name}")
    except CollectionInvalid:
        print(f"  [EXISTS]  {name} — updating validator")
        try:
            db.command("collMod", name, validator=validator, validationLevel=validation_level, validationAction=validation_action)
        except OperationFailure as exc:
            print(f"  [WARN]    could not update validator for '{name}': {exc}")


def create_indexes(db, name: str, indexes: list) -> None:
    for idx in indexes:
        try:
            db[name].create_index(idx["keys"], **idx.get("options", {}))
            key_str = ", ".join(f"{k}({'ASC' if d == 1 else 'DESC'})" for k, d in idx["keys"])
            print(f"  [INDEX]   {name}: {key_str}")
        except OperationFailure as exc:
            print(f"  [WARN]    index on {name} failed: {exc}")


def seed_reference_data(db) -> None:
    print("\n--- Reference Data ---")
    for collection_name, data in SEED_DATA.items():
        if db[collection_name].count_documents({}) > 0:
            print(f"  [SKIP]  {collection_name} already populated")
            continue
        result = db[collection_name].insert_many(data)
        print(f"  [SEED]  {collection_name}: {len(result.inserted_ids)} documents")


def setup(db) -> None:
    print(f"\nSetting up: {MONGO_DB}\n")
    for name, spec in COLLECTIONS.items():
        create_collection(db, name, spec)
        create_indexes(db, name, spec.get("indexes", []))
    seed_reference_data(db)
    print("\nDone.")


if __name__ == "__main__":
    print(f"Connecting to {MONGO_URI} ...")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except Exception as exc:
        print(f"ERROR: Cannot connect to MongoDB: {exc}", file=sys.stderr)
        sys.exit(1)

    db = client[MONGO_DB]
    try:
        setup(db)
    except Exception as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.close()
