import re
from dataclasses import dataclass
from typing import List, Optional
from pymongo.asynchronous.database import AsyncDatabase
from app.models.audit import AuditSeverity


# Result of a single safety-rule check.
@dataclass
class FlagResult:
    code: str
    severity: AuditSeverity
    issue: str
    recommendation: str
    drug_name: str
    dose: str


# Maximum-dose reference per drug, grounded in published dosing guidance
# (BNF for Children, MSF Essential Drugs, Drugs.com). Per-drug:
#   adult_max_single_mg : usual adult max for one dose
#   max_mg_per_kg_day    : paediatric weight-based ceiling (mg/kg/day)
#   abs_max_mg_day       : absolute daily ceiling regardless of weight
# Keyed by lowercase drug name. Drugs not listed fall back to a generic rule.
_DOSE_LIMITS = {
    "paracetamol":  {"adult_max_single_mg": 1000, "max_mg_per_kg_day": 75,  "abs_max_mg_day": 4000},
    "acetaminophen":{"adult_max_single_mg": 1000, "max_mg_per_kg_day": 75,  "abs_max_mg_day": 4000},
    "ibuprofen":    {"adult_max_single_mg": 400,  "max_mg_per_kg_day": 40,  "abs_max_mg_day": 1200},
    "amoxicillin":  {"adult_max_single_mg": 500,  "max_mg_per_kg_day": 90,  "abs_max_mg_day": 3000},
    "diclofenac":   {"adult_max_single_mg": 50,   "max_mg_per_kg_day": 3,   "abs_max_mg_day": 150},
    "prednisolone": {"adult_max_single_mg": 60,   "max_mg_per_kg_day": 2,   "abs_max_mg_day": 60},
    "azithromycin": {"adult_max_single_mg": 500,  "max_mg_per_kg_day": 12,  "abs_max_mg_day": 500},
    "furosemide":   {"adult_max_single_mg": 80,   "max_mg_per_kg_day": 6,   "abs_max_mg_day": 600},
}

# Doses per day implied by a frequency code, for mg/kg/day calculations.
_FREQ_PER_DAY = {
    "od": 1, "daily": 1, "qd": 1,
    "bd": 2, "bid": 2,
    "tds": 3, "tid": 3,
    "qds": 4, "qid": 4,
    "prn": 1,
}


# Parse the milligrams in a dose string ("500mg", "1g" -> 1000).
def _parse_mg(dose: str) -> Optional[float]:
    if not dose:
        return None
    g = re.search(r"(\d+(?:\.\d+)?)\s*g(?![a-z/])", dose, re.IGNORECASE)
    if g:
        return float(g.group(1)) * 1000
    mg = re.search(r"(\d+(?:\.\d+)?)\s*mg", dose, re.IGNORECASE)
    if mg:
        return float(mg.group(1))
    return None


# Total milligrams a med delivers per day, from its dose and frequency.
def _mg_per_day(med: dict) -> Optional[float]:
    per_dose = _parse_mg(med.get("dose", ""))
    if per_dose is None:
        return None
    freq = str(med.get("frequency", "")).strip().lower()
    return per_dose * _FREQ_PER_DAY.get(freq, 1)


# Run every safety rule against a prescription and collect flags.
async def check_all_rules(prescription: dict, patient: dict, active_rxs: List[dict], db: AsyncDatabase) -> List[FlagResult]:
    flags = []

    # Load configurable dose limits (falls back to the built-in table).
    try:
        from app.services.dosing_service import get_dose_limit_map
        limits_map = await get_dose_limit_map(db)
    except Exception:
        limits_map = _DOSE_LIMITS

    for med in prescription.get("medications", []):
        flags.extend(await check_high_dose(med, patient, limits_map))
        flags.extend(await check_extended_duration(med))
        flags.extend(await check_duplicate_active_rx(med, active_rxs))
        flags.extend(await check_allergy_match(med, patient))
        flags.extend(await check_drug_drug_interaction(med, prescription, db))
        flags.extend(await check_controlled_substance(med, db))

        if patient.get("is_paediatric"):
            flags.extend(await check_paediatric_dose(med, patient, limits_map))

        if patient.get("is_neonate"):
            flags.extend(await check_neonatal(med))

        if patient.get("is_pregnant"):
            flags.extend(await check_pregnancy_risk(med, db))

    return flags


# Flag a dose above the safe maximum, weight-adjusted where possible.
async def check_high_dose(med: dict, patient: Optional[dict] = None, limits_map: Optional[dict] = None) -> List[FlagResult]:
    dose = med.get("dose", "")
    name = med.get("name", "")
    limits = (limits_map or _DOSE_LIMITS).get(name.strip().lower())
    daily_mg = _mg_per_day(med)
    weight = (patient or {}).get("weight_kg")

    # Weight-based check for known drugs when we have a weight: compares the
    # ordered mg/kg/day against the drug's paediatric ceiling.
    if limits and daily_mg and weight:
        mg_per_kg_day = daily_mg / weight
        if mg_per_kg_day > limits["max_mg_per_kg_day"]:
            return [FlagResult(
                code="high_dose",
                severity=AuditSeverity.high,
                issue=f"Dose exceeds weight-based limit: {mg_per_kg_day:.1f} mg/kg/day for {name} (max {limits['max_mg_per_kg_day']} mg/kg/day)",
                recommendation="Recalculate the dose for the patient's weight before dispensing.",
                drug_name=name,
                dose=dose,
            )]

    # Absolute daily ceiling for known drugs (catches adult overdoses too).
    if limits and daily_mg and daily_mg > limits["abs_max_mg_day"]:
        return [FlagResult(
            code="high_dose",
            severity=AuditSeverity.high,
            issue=f"Dose exceeds maximum daily limit: {daily_mg:.0f} mg/day for {name} (max {limits['abs_max_mg_day']} mg/day)",
            recommendation="Verify the dose; it is above the recommended daily maximum.",
            drug_name=name,
            dose=dose,
        )]

    # Generic fallback for drugs without a reference entry.
    if not limits:
        per_dose = _parse_mg(dose)
        if per_dose and per_dose > 1000:
            return [FlagResult(
                code="high_dose",
                severity=AuditSeverity.medium,
                issue=f"High dose detected: {dose} for {name}",
                recommendation="Verify dose is correct and appropriate for the patient.",
                drug_name=name,
                dose=dose,
            )]
    return []


# Flag a course that runs longer than recommended.
async def check_extended_duration(med: dict) -> List[FlagResult]:
    duration = med.get("duration_days", 0)
    if duration > 30:
        return [FlagResult(
            code="extended_duration",
            severity=AuditSeverity.medium,
            issue=f"Extended duration: {duration} days for {med.get('name')}",
            recommendation="Confirm long-term therapy is intended",
            drug_name=med.get("name", ""),
            dose=med.get("dose", "")
        )]
    return []


# Flag a drug the patient is already on.
async def check_duplicate_active_rx(med: dict, active_rxs: List[dict]) -> List[FlagResult]:
    drug_name = med.get("name", "").lower()
    
    for rx in active_rxs:
        for rx_med in rx.get("medications", []):
            if rx_med.get("name", "").lower() == drug_name:
                return [FlagResult(
                    code="duplicate_active_rx",
                    severity=AuditSeverity.high,
                    issue=f"Duplicate active prescription for {med.get('name')}",
                    recommendation="Check if duplicate prescription is intended",
                    drug_name=med.get("name", ""),
                    dose=med.get("dose", "")
                )]
    return []


# Flag a drug the patient is allergic to.
async def check_allergy_match(med: dict, patient: dict) -> List[FlagResult]:
    drug_name = med.get("name", "").lower()
    allergies = patient.get("allergies") or []

    for allergy in allergies:
        if isinstance(allergy, dict):
            substance = allergy.get("substance", "").lower()
        else:
            substance = str(allergy).lower()
        
        if substance in drug_name or drug_name in substance:
            return [FlagResult(
                code="allergy_match",
                severity=AuditSeverity.high,
                issue=f"Allergy match: {med.get('name')} matches patient allergy {substance}",
                recommendation="Do not dispense. Patient allergy on record.",
                drug_name=med.get("name", ""),
                dose=med.get("dose", "")
            )]
    return []


# Flag interactions with the patient's other drugs.
async def check_drug_drug_interaction(med: dict, prescription: dict, db: AsyncDatabase) -> List[FlagResult]:
    drug_name = med.get("name", "").lower()
    other_meds = [m.get("name", "").lower() for m in prescription.get("medications", []) if m.get("name", "").lower() != drug_name]
    
    for other in other_meds:
        interaction = await db.drug_interactions.find_one({
            "$or": [
                {"drug1": drug_name, "drug2": other},
                {"drug1": other, "drug2": drug_name}
            ]
        })
        
        if interaction:
            return [FlagResult(
                code="drug_drug_interaction",
                severity=AuditSeverity[interaction.get("severity", "medium")],
                issue=f"Drug interaction: {med.get('name')} with {other}",
                recommendation=interaction.get("recommendation", "Review interaction"),
                drug_name=med.get("name", ""),
                dose=med.get("dose", "")
            )]
    return []


# Flag controlled or scheduled drugs.
async def check_controlled_substance(med: dict, db: AsyncDatabase) -> List[FlagResult]:
    drug_name = med.get("name", "").lower()
    controlled = await db.controlled_substances.find_one({"name": {"$regex": f"^{re.escape(drug_name)}$", "$options": "i"}})
    
    if controlled:
        return [FlagResult(
            code="controlled_substance",
            severity=AuditSeverity.high,
            issue=f"Controlled substance: {med.get('name')}",
            recommendation="Verify prescription authorization and documentation",
            drug_name=med.get("name", ""),
            dose=med.get("dose", "")
        )]
    return []


# Flag doses unsafe for a child's weight.
async def check_paediatric_dose(med: dict, patient: dict, limits_map: Optional[dict] = None) -> List[FlagResult]:
    name = med.get("name", "")
    weight = patient.get("weight_kg")
    if not weight:
        return []

    daily_mg = _mg_per_day(med)
    limits = (limits_map or _DOSE_LIMITS).get(name.strip().lower())

    # Known drug: compare against its paediatric mg/kg/day ceiling.
    if limits and daily_mg:
        mg_per_kg_day = daily_mg / weight
        if mg_per_kg_day > limits["max_mg_per_kg_day"]:
            return [FlagResult(
                code="paediatric_high_dose",
                severity=AuditSeverity.high,
                issue=f"High paediatric dose: {mg_per_kg_day:.1f} mg/kg/day for {name} (max {limits['max_mg_per_kg_day']} mg/kg/day)",
                recommendation="Verify the paediatric dosing calculation for the child's weight.",
                drug_name=name,
                dose=med.get("dose", ""),
            )]

    # Unknown drug: generic 25 mg/kg/day caution threshold for a child.
    if not limits and daily_mg and (daily_mg / weight) > 25:
        return [FlagResult(
            code="paediatric_high_dose",
            severity=AuditSeverity.medium,
            issue=f"High paediatric dose: {daily_mg / weight:.1f} mg/kg/day for {name}",
            recommendation="Confirm the dose is appropriate for the child's weight.",
            drug_name=name,
            dose=med.get("dose", ""),
        )]
    return []


# Flag drugs unsafe for neonates.
async def check_neonatal(med: dict) -> List[FlagResult]:
    return [FlagResult(
        code="neonatal_rx",
        severity=AuditSeverity.high,
        issue=f"Neonatal prescription: {med.get('name')} requires specialized review",
        recommendation="Pharmacist must verify neonatal dosing and appropriateness",
        drug_name=med.get("name", ""),
        dose=med.get("dose", "")
    )]


# Flag drugs risky in pregnancy.
async def check_pregnancy_risk(med: dict, db: AsyncDatabase) -> List[FlagResult]:
    drug_name = med.get("name", "").lower()
    category_x = await db.category_x_drugs.find_one({"name": {"$regex": f"^{re.escape(drug_name)}$", "$options": "i"}})
    
    if category_x:
        return [FlagResult(
            code="pregnancy_risk",
            severity=AuditSeverity.high,
            issue=f"Pregnancy risk: {med.get('name')} is contraindicated in pregnancy",
            recommendation="Do not dispense. Contraindicated in pregnancy.",
            drug_name=med.get("name", ""),
            dose=med.get("dose", "")
        )]
    return []
