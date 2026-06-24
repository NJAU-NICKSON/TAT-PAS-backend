from datetime import datetime, timezone
from typing import List, Dict, Any
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

# Default tariff in KES, seeded on first use. Keyed by item code.
DEFAULT_CATALOGUE = [
    {"code": "consultation_opd",  "category": "consultation", "name": "OPD Consultation",        "unit_price": 1000, "unit": "per visit"},
    {"code": "consultation_spec", "category": "consultation", "name": "Specialist Consultation", "unit_price": 2000, "unit": "per visit"},
    {"code": "consultation_emerg","category": "consultation", "name": "Emergency Consultation",   "unit_price": 1500, "unit": "per visit"},
    {"code": "bed_general",       "category": "ward",         "name": "General Ward Bed",         "unit_price": 2500, "unit": "per day"},
    {"code": "bed_icu",          "category": "ward",         "name": "ICU Bed",                  "unit_price": 8000, "unit": "per day"},
    {"code": "nursing_care",      "category": "procedure",    "name": "Nursing Care",             "unit_price": 800,  "unit": "per day"},
    {"code": "lab_basic",         "category": "lab",          "name": "Basic Lab Panel",          "unit_price": 1200, "unit": "per test"},
    {"code": "radiology_xray",    "category": "radiology",    "name": "X-Ray",                    "unit_price": 1500, "unit": "per scan"},
    {"code": "medication_default","category": "pharmacy",     "name": "Medication (per item)",    "unit_price": 500,  "unit": "per item"},
]


# Return the price catalogue, seeding defaults on first use.
async def get_catalogue(db: AsyncDatabase) -> List[Dict[str, Any]]:
    if await db.price_catalogue.count_documents({}) == 0:
        now = datetime.now(timezone.utc)
        await db.price_catalogue.insert_many(
            [{**i, "updated_at": now, "updated_by": "system"} for i in DEFAULT_CATALOGUE]
        )
    out = []
    async for d in db.price_catalogue.find({}).sort("category", 1):
        out.append({
            "code": d["code"], "category": d.get("category"), "name": d.get("name"),
            "unit_price": d.get("unit_price"), "unit": d.get("unit"),
        })
    return out


# Update the price for one catalogue item.
async def update_catalogue_item(db: AsyncDatabase, code: str, unit_price: float, updated_by: str) -> Dict[str, Any]:
    if unit_price is None or unit_price < 0:
        raise ValueError("unit_price must be zero or greater")
    now = datetime.now(timezone.utc)
    res = await db.price_catalogue.update_one(
        {"code": code},
        {"$set": {"unit_price": unit_price, "updated_at": now, "updated_by": updated_by}},
    )
    if res.matched_count == 0:
        raise ValueError(f"Unknown catalogue item: {code}")
    doc = await db.price_catalogue.find_one({"code": code})
    return {"code": doc["code"], "category": doc.get("category"), "name": doc.get("name"),
            "unit_price": doc.get("unit_price"), "unit": doc.get("unit")}


# Price lookup map by code.
async def _price_map(db: AsyncDatabase) -> Dict[str, Dict[str, Any]]:
    return {i["code"]: i for i in await get_catalogue(db)}


# Whole days between two datetimes, minimum 1.
def _days_between(start, end) -> int:
    if not start or not end:
        return 1
    days = (end - start).days
    return max(1, days)


# Build line items for a visit from the catalogue: consultation, bed-days, nursing, and dispensed medication.
async def build_bill_items(db: AsyncDatabase, visit: dict) -> List[Dict[str, Any]]:
    prices = await _price_map(db)
    items: List[Dict[str, Any]] = []

    def add(code: str, qty: float, name_override: str = None):
        p = prices.get(code)
        if not p:
            return
        unit = float(p["unit_price"])
        items.append({
            "category": p["category"],
            "description": name_override or p["name"],
            "quantity": qty,
            "unit_price": unit,
            "total_price": round(unit * qty, 2),
        })

    vtype = visit.get("visit_type")
    if vtype == "emergency":
        add("consultation_emerg", 1)
    elif vtype == "ipd":
        add("consultation_spec", 1)
    else:
        add("consultation_opd", 1)

    # Bed-days + nursing for admitted patients.
    if visit.get("admitted_at"):
        end = visit.get("discharged_at") or datetime.now(timezone.utc)
        admitted = visit["admitted_at"]
        if admitted.tzinfo is None:
            admitted = admitted.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        days = _days_between(admitted, end)
        bed_code = "bed_icu" if (visit.get("ward_name") or "").lower().startswith("icu") else "bed_general"
        add(bed_code, days)
        add("nursing_care", days)

    # Dispensed medications on this visit.
    visit_id = str(visit.get("_id") or visit.get("id") or "")
    if visit_id:
        async for rx in db.prescriptions.find({"visit_id": visit_id, "status": {"$in": ["dispensed", "administered"]}}):
            for med in rx.get("medications", []):
                name = med.get("name", "Medication")
                add("medication_default", 1, name_override=f"{name} {med.get('dose','')}".strip())

    return items
