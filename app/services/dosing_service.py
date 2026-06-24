from datetime import datetime, timezone
from typing import List, Dict, Any
from pymongo.asynchronous.database import AsyncDatabase

# Age-banded dose limits per drug, giving max mg/kg/day and absolute mg/day ceiling per age range.
DEFAULT_DOSE_LIMITS: List[Dict[str, Any]] = [
    {"drug": "paracetamol", "adult_max_single_mg": 1000, "bands": [
        {"min_age_years": 0,  "max_age_years": 1,   "max_mg_per_kg_day": 60, "abs_max_mg_day": 500},
        {"min_age_years": 1,  "max_age_years": 12,  "max_mg_per_kg_day": 75, "abs_max_mg_day": 2000},
        {"min_age_years": 12, "max_age_years": 120, "max_mg_per_kg_day": 75, "abs_max_mg_day": 4000},
    ]},
    {"drug": "ibuprofen", "adult_max_single_mg": 400, "bands": [
        {"min_age_years": 0.25, "max_age_years": 12,  "max_mg_per_kg_day": 30, "abs_max_mg_day": 800},
        {"min_age_years": 12,   "max_age_years": 120, "max_mg_per_kg_day": 40, "abs_max_mg_day": 1200},
    ]},
    {"drug": "amoxicillin", "adult_max_single_mg": 500, "bands": [
        {"min_age_years": 0,  "max_age_years": 12,  "max_mg_per_kg_day": 90, "abs_max_mg_day": 1500},
        {"min_age_years": 12, "max_age_years": 120, "max_mg_per_kg_day": 45, "abs_max_mg_day": 3000},
    ]},
    {"drug": "diclofenac", "adult_max_single_mg": 50, "bands": [
        {"min_age_years": 14, "max_age_years": 120, "max_mg_per_kg_day": 3, "abs_max_mg_day": 150},
    ]},
    {"drug": "prednisolone", "adult_max_single_mg": 60, "bands": [
        {"min_age_years": 0,  "max_age_years": 12,  "max_mg_per_kg_day": 2, "abs_max_mg_day": 40},
        {"min_age_years": 12, "max_age_years": 120, "max_mg_per_kg_day": 1, "abs_max_mg_day": 60},
    ]},
    {"drug": "azithromycin", "adult_max_single_mg": 500, "bands": [
        {"min_age_years": 0,  "max_age_years": 12,  "max_mg_per_kg_day": 12, "abs_max_mg_day": 250},
        {"min_age_years": 12, "max_age_years": 120, "max_mg_per_kg_day": 10, "abs_max_mg_day": 500},
    ]},
    {"drug": "furosemide", "adult_max_single_mg": 80, "bands": [
        {"min_age_years": 0,  "max_age_years": 12,  "max_mg_per_kg_day": 6, "abs_max_mg_day": 80},
        {"min_age_years": 12, "max_age_years": 120, "max_mg_per_kg_day": 6, "abs_max_mg_day": 600},
    ]},
    {"drug": "aspirin", "adult_max_single_mg": 600, "bands": [
        {"min_age_years": 16, "max_age_years": 120, "max_mg_per_kg_day": 0, "abs_max_mg_day": 4000},
    ]},
]


def _sort_bands(bands: List[dict]) -> List[dict]:
    return sorted(bands, key=lambda b: b.get("min_age_years", 0))


# Return all dose limits, seeding defaults on first use.
async def get_dose_limits(db: AsyncDatabase) -> List[Dict[str, Any]]:
    if await db.dose_limits.count_documents({}) == 0:
        now = datetime.now(timezone.utc)
        await db.dose_limits.insert_many(
            [{**d, "bands": _sort_bands(d["bands"]), "updated_at": now, "updated_by": "system"} for d in DEFAULT_DOSE_LIMITS]
        )

    out = []
    async for doc in db.dose_limits.find({}).sort("drug", 1):
        out.append({
            "drug": doc["drug"],
            "adult_max_single_mg": doc.get("adult_max_single_mg"),
            "bands": _sort_bands(doc.get("bands", [])),
        })
    return out


# Update (or add) a drug's age-banded dose limits.
async def update_dose_limit(
    db: AsyncDatabase,
    drug: str,
    adult_max_single_mg: float,
    bands: List[Dict[str, Any]],
    updated_by: str,
) -> Dict[str, Any]:
    drug = drug.strip().lower()
    if not drug:
        raise ValueError("drug name is required")
    if adult_max_single_mg is None or adult_max_single_mg <= 0:
        raise ValueError("adult_max_single_mg must be greater than 0")
    if not bands:
        raise ValueError("at least one age band is required")

    clean: List[dict] = []
    for b in bands:
        mn = b.get("min_age_years")
        mx = b.get("max_age_years")
        kg = b.get("max_mg_per_kg_day")
        ab = b.get("abs_max_mg_day")
        if mn is None or mx is None or mx <= mn or mn < 0:
            raise ValueError("each band needs a valid age range (max age greater than min age)")
        if ab is None or ab <= 0:
            raise ValueError("each band needs an absolute max greater than 0")
        if kg is None or kg < 0:
            raise ValueError("max mg/kg/day must be zero or greater")
        clean.append({
            "min_age_years": mn, "max_age_years": mx,
            "max_mg_per_kg_day": kg, "abs_max_mg_day": ab,
        })

    now = datetime.now(timezone.utc)
    await db.dose_limits.update_one(
        {"drug": drug},
        {"$set": {
            "drug": drug,
            "adult_max_single_mg": adult_max_single_mg,
            "bands": _sort_bands(clean),
            "updated_at": now,
            "updated_by": updated_by,
        }},
        upsert=True,
    )
    return {"drug": drug, "adult_max_single_mg": adult_max_single_mg, "bands": _sort_bands(clean)}


# Return the dose-limit map keyed by drug, for the flagging engine.
async def get_dose_limit_map(db: AsyncDatabase) -> Dict[str, Dict[str, Any]]:
    limits = await get_dose_limits(db)
    return {l["drug"]: {"adult_max_single_mg": l["adult_max_single_mg"], "bands": l["bands"]} for l in limits}


# Pick the band whose age range contains the given age, or None.
def band_for_age(bands: List[dict], age_years: float):
    for b in _sort_bands(bands or []):
        if b["min_age_years"] <= age_years < b["max_age_years"]:
            return b
    return None
