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


# Run every safety rule against a prescription and collect flags.
async def check_all_rules(prescription: dict, patient: dict, active_rxs: List[dict], db: AsyncDatabase) -> List[FlagResult]:
    flags = []
    
    for med in prescription.get("medications", []):
        flags.extend(await check_high_dose(med))
        flags.extend(await check_extended_duration(med))
        flags.extend(await check_duplicate_active_rx(med, active_rxs))
        flags.extend(await check_allergy_match(med, patient))
        flags.extend(await check_drug_drug_interaction(med, prescription, db))
        flags.extend(await check_controlled_substance(med, db))
        
        if patient.get("is_paediatric"):
            flags.extend(await check_paediatric_dose(med, patient))
        
        if patient.get("is_neonate"):
            flags.extend(await check_neonatal(med))
        
        if patient.get("is_pregnant"):
            flags.extend(await check_pregnancy_risk(med, db))
    
    return flags


# Flag a dose above the safe maximum.
async def check_high_dose(med: dict) -> List[FlagResult]:
    dose = med.get("dose", "")
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*mg", dose, re.IGNORECASE)
    
    for match in matches:
        value = float(match)
        if value > 1000:
            return [FlagResult(
                code="high_dose",
                severity=AuditSeverity.high,
                issue=f"High dose detected: {dose} for {med.get('name')}",
                recommendation="Verify dose is correct and appropriate for patient",
                drug_name=med.get("name", ""),
                dose=dose
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
async def check_paediatric_dose(med: dict, patient: dict) -> List[FlagResult]:
    dose_per_kg = med.get("dose_per_kg")
    if dose_per_kg and dose_per_kg > 25:
        return [FlagResult(
            code="paediatric_high_dose",
            severity=AuditSeverity.high,
            issue=f"High paediatric dose: {dose_per_kg} mg/kg for {med.get('name')}",
            recommendation="Verify paediatric dosing calculation",
            drug_name=med.get("name", ""),
            dose=med.get("dose", "")
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
