from datetime import datetime, timezone
from typing import List, Dict, Any
from pymongo.asynchronous.database import AsyncDatabase

# Default per-drug dose limits, grounded in BNF for Children / MSF / Drugs.com.
# Used to seed the dose_limits collection and as a fallback if it is empty.
DEFAULT_DOSE_LIMITS: Dict[str, Dict[str, float]] = {
    "paracetamol":  {"adult_max_single_mg": 1000, "max_mg_per_kg_day": 75,  "abs_max_mg_day": 4000},
    "ibuprofen":    {"adult_max_single_mg": 400,  "max_mg_per_kg_day": 40,  "abs_max_mg_day": 1200},
    "amoxicillin":  {"adult_max_single_mg": 500,  "max_mg_per_kg_day": 90,  "abs_max_mg_day": 3000},
    "diclofenac":   {"adult_max_single_mg": 50,   "max_mg_per_kg_day": 3,   "abs_max_mg_day": 150},
    "prednisolone": {"adult_max_single_mg": 60,   "max_mg_per_kg_day": 2,   "abs_max_mg_day": 60},
    "azithromycin": {"adult_max_single_mg": 500,  "max_mg_per_kg_day": 12,  "abs_max_mg_day": 500},
    "furosemide":   {"adult_max_single_mg": 80,   "max_mg_per_kg_day": 6,   "abs_max_mg_day": 600},
}


# Return all dose limits, seeding defaults on first use.
async def get_dose_limits(db: AsyncDatabase) -> List[Dict[str, Any]]:
    count = await db.dose_limits.count_documents({})
    if count == 0:
        now = datetime.now(timezone.utc)
        docs = [{"drug": d, **v, "updated_at": now, "updated_by": "system"}
                for d, v in DEFAULT_DOSE_LIMITS.items()]
        if docs:
            await db.dose_limits.insert_many(docs)

    out = []
    async for doc in db.dose_limits.find({}).sort("drug", 1):
        out.append({
            "drug": doc["drug"],
            "adult_max_single_mg": doc.get("adult_max_single_mg"),
            "max_mg_per_kg_day": doc.get("max_mg_per_kg_day"),
            "abs_max_mg_day": doc.get("abs_max_mg_day"),
        })
    return out


# Update (or add) the dose limits for one drug.
async def update_dose_limit(
    db: AsyncDatabase,
    drug: str,
    adult_max_single_mg: float,
    max_mg_per_kg_day: float,
    abs_max_mg_day: float,
    updated_by: str,
) -> Dict[str, Any]:
    drug = drug.strip().lower()
    if not drug:
        raise ValueError("drug name is required")
    for label, val in (("adult_max_single_mg", adult_max_single_mg),
                       ("max_mg_per_kg_day", max_mg_per_kg_day),
                       ("abs_max_mg_day", abs_max_mg_day)):
        if val is None or val <= 0:
            raise ValueError(f"{label} must be greater than 0")

    now = datetime.now(timezone.utc)
    await db.dose_limits.update_one(
        {"drug": drug},
        {"$set": {
            "drug": drug,
            "adult_max_single_mg": adult_max_single_mg,
            "max_mg_per_kg_day": max_mg_per_kg_day,
            "abs_max_mg_day": abs_max_mg_day,
            "updated_at": now,
            "updated_by": updated_by,
        }},
        upsert=True,
    )
    return {
        "drug": drug,
        "adult_max_single_mg": adult_max_single_mg,
        "max_mg_per_kg_day": max_mg_per_kg_day,
        "abs_max_mg_day": abs_max_mg_day,
    }


# Return the dose-limit map keyed by drug, for the flagging engine.
async def get_dose_limit_map(db: AsyncDatabase) -> Dict[str, Dict[str, float]]:
    limits = await get_dose_limits(db)
    return {
        l["drug"]: {
            "adult_max_single_mg": l["adult_max_single_mg"],
            "max_mg_per_kg_day": l["max_mg_per_kg_day"],
            "abs_max_mg_day": l["abs_max_mg_day"],
        }
        for l in limits
    }
