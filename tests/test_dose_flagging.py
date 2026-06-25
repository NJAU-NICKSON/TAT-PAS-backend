"""SO2 / RQ3: automatic age-banded prescription dose checks flag unsafe orders."""

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from app.services import flagging_service as f

# Age-banded limits for the tests (matches the production shape).
LIMITS = {
    "paracetamol": {"adult_max_single_mg": 1000, "bands": [
        {"min_age_years": 0,  "max_age_years": 1,   "max_mg_per_kg_day": 60, "abs_max_mg_day": 500},
        {"min_age_years": 1,  "max_age_years": 12,  "max_mg_per_kg_day": 75, "abs_max_mg_day": 2000},
        {"min_age_years": 12, "max_age_years": 120, "max_mg_per_kg_day": 75, "abs_max_mg_day": 4000},
    ]},
    "aspirin": {"adult_max_single_mg": 600, "bands": [
        {"min_age_years": 16, "max_age_years": 120, "max_mg_per_kg_day": 0, "abs_max_mg_day": 4000},
    ]},
}


def _dob(years):
    return datetime.now(timezone.utc) - relativedelta(years=years)


# Dose string parsing: grams convert to milligrams.
def test_parse_mg_grams_and_mg():
    assert f._parse_mg("1g") == 1000
    assert f._parse_mg("500mg") == 500
    assert f._parse_mg("") is None


# Frequency multiplies the per-dose amount into a daily total.
def test_mg_per_day_uses_frequency():
    assert f._mg_per_day({"dose": "400mg", "frequency": "TDS"}) == 1200
    assert f._mg_per_day({"dose": "1g", "frequency": "QDS"}) == 4000


# A 5-year-old's overdose is caught against the 1-12 age band, not the adult band.
async def test_child_overdose_uses_child_band():
    child = {"dob": _dob(5), "weight_kg": 18}
    med = {"name": "Paracetamol", "dose": "500mg", "frequency": "QDS"}  # 2000/day = 111 mg/kg/day
    flags = await f.check_dose_for_age(med, child, LIMITS)
    assert flags
    assert flags[0].code == "high_dose"
    assert "1-12" in flags[0].issue or "mg/kg/day" in flags[0].issue


# A safe child dose is not flagged.
async def test_child_safe_dose_not_flagged():
    child = {"dob": _dob(5), "weight_kg": 18}
    med = {"name": "Paracetamol", "dose": "250mg", "frequency": "TDS"}  # 750/day = 41 mg/kg/day
    assert await f.check_dose_for_age(med, child, LIMITS) == []


# The same dose is fine for an adult (adult band has a higher ceiling).
async def test_adult_dose_allowed():
    adult = {"dob": _dob(40), "weight_kg": 70}
    med = {"name": "Paracetamol", "dose": "1g", "frequency": "QDS"}  
    assert await f.check_dose_for_age(med, adult, LIMITS) == []


# A drug with no band for the patient's age is flagged as age-restricted.
async def test_no_band_for_age_flagged():
    child = {"dob": _dob(8), "weight_kg": 25}
    med = {"name": "Aspirin", "dose": "300mg", "frequency": "OD"}  # aspirin only 16+
    flags = await f.check_dose_for_age(med, child, LIMITS)
    assert flags
    assert flags[0].code == "age_restriction"


# Allergy match is flagged.
async def test_allergy_match_flagged():
    patient = {"allergies": [{"substance": "Penicillin", "severity": "severe"}]}
    med = {"name": "Penicillin V", "dose": "250mg"}
    flags = await f.check_allergy_match(med, patient)
    assert flags and flags[0].code == "allergy_match"


# Extended course (over 30 days) is flagged.
async def test_extended_duration_flagged():
    flags = await f.check_extended_duration({"name": "Drug", "dose": "1mg", "duration_days": 60})
    assert flags and flags[0].code == "extended_duration"
