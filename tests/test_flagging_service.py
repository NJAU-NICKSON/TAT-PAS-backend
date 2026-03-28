"""
Unit tests for flagging_service.py
SO4 / RQ4 — validates automated rule-based prescription checking
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.flagging_service import (
    check_high_dose,
    check_extended_duration,
    check_duplicate_active_rx,
    check_allergy_match,
    check_paediatric_dose,
    check_neonatal,
)


def med(name, dose, days=7, **kw):
    return {"name": name, "dose": dose, "duration_days": days, **kw}


def patient(allergies=None, is_paediatric=False, is_neonate=False, is_pregnant=False):
    return {
        "allergies": allergies or [],
        "is_paediatric": is_paediatric,
        "is_neonate": is_neonate,
        "is_pregnant": is_pregnant,
    }


# TC-01: High dose above threshold is flagged

async def test_high_dose_flagged():
    flags = await check_high_dose(med("Morphine", "1500mg"))
    assert len(flags) == 1
    assert flags[0].code == "high_dose"
    assert flags[0].severity.value == "high"


# TC-02: Normal dose is not flagged

async def test_normal_dose_not_flagged():
    flags = await check_high_dose(med("Paracetamol", "500mg"))
    assert flags == []


# TC-03: Dose exactly at threshold (1000mg) is not flagged

async def test_dose_at_boundary_not_flagged():
    flags = await check_high_dose(med("Ibuprofen", "1000mg"))
    assert flags == []


# TC-04: Non-mg dose string does not raise errors

async def test_non_mg_dose_no_error():
    flags = await check_high_dose(med("Insulin", "20IU"))
    assert flags == []


# TC-05: Duration over 30 days triggers extended duration flag

async def test_extended_duration_flagged():
    flags = await check_extended_duration(med("Metformin", "500mg", days=60))
    assert len(flags) == 1
    assert flags[0].code == "extended_duration"


# TC-06: Duration of exactly 30 days is not flagged

async def test_duration_at_boundary_not_flagged():
    flags = await check_extended_duration(med("Lisinopril", "10mg", days=30))
    assert flags == []


# TC-07: Duplicate drug in active prescriptions is flagged

async def test_duplicate_active_rx_flagged():
    active = [{"medications": [{"name": "Amoxicillin", "dose": "500mg"}]}]
    flags = await check_duplicate_active_rx(med("Amoxicillin", "500mg"), active)
    assert len(flags) == 1
    assert flags[0].code == "duplicate_active_rx"


# TC-08: Different drug in active prescriptions — no flag

async def test_no_duplicate_rx_different_drug():
    active = [{"medications": [{"name": "Metformin", "dose": "500mg"}]}]
    flags = await check_duplicate_active_rx(med("Amoxicillin", "500mg"), active)
    assert flags == []


# TC-09: Drug matches patient allergy — flagged (dict allergy, exact name match)

async def test_allergy_match_dict_flagged():
    p = patient(allergies=[{"substance": "Penicillin", "severity": "severe"}])
    flags = await check_allergy_match(med("Penicillin", "500mg"), p)
    assert len(flags) == 1
    assert flags[0].code == "allergy_match"


# TC-10: Drug does not match patient allergy — no flag

async def test_allergy_no_match():
    p = patient(allergies=[{"substance": "Sulfonamides", "severity": "moderate"}])
    flags = await check_allergy_match(med("Metformin", "500mg"), p)
    assert flags == []


# TC-11: Patient with no allergies — no flag

async def test_no_allergies_no_flag():
    p = patient(allergies=[])
    flags = await check_allergy_match(med("Amoxicillin", "500mg"), p)
    assert flags == []


# TC-12: Paediatric dose above 25 mg/kg is flagged

async def test_paediatric_high_dose_flagged():
    p = patient(is_paediatric=True)
    m = med("Paracetamol", "500mg", dose_per_kg=30.0)
    flags = await check_paediatric_dose(m, p)
    assert len(flags) == 1
    assert flags[0].code == "paediatric_high_dose"


# TC-13: Paediatric dose within safe range — no flag

async def test_paediatric_safe_dose_no_flag():
    p = patient(is_paediatric=True)
    m = med("Paracetamol", "250mg", dose_per_kg=15.0)
    flags = await check_paediatric_dose(m, p)
    assert flags == []


# TC-14: Paediatric med with no dose_per_kg — no flag (no calculation possible)

async def test_paediatric_no_dose_per_kg_no_flag():
    p = patient(is_paediatric=True)
    m = med("Amoxicillin", "250mg")
    flags = await check_paediatric_dose(m, p)
    assert flags == []


# TC-15: Neonatal prescription always flagged

async def test_neonatal_always_flagged():
    flags = await check_neonatal(med("Gentamicin", "5mg"))
    assert len(flags) == 1
    assert flags[0].code == "neonatal_rx"
    assert flags[0].severity.value == "high"
