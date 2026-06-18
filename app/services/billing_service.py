from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone
from pymongo.asynchronous.database import AsyncDatabase

from app.models.bill import Bill, BillInDB, LineItem, Payment, BillUpdate
from app.services.visit_service import get_visit
from app.services.patient_service import get_patient_by_id
from app.ws.manager import manager


# Produce the next sequential bill number.
async def generate_bill_number(db: AsyncDatabase) -> str:
    today = datetime.now(timezone.utc)
    prefix = f"BILL-{today.strftime('%Y%m%d')}"
    count = await db.bills.count_documents({"bill_number": {"$regex": f"^{prefix}"}})
    return f"{prefix}-{count + 1:04d}"


# Batch-enrich bill docs with patient_name and visit_number.
async def _enrich_docs(db: AsyncDatabase, docs: list) -> list:
    pid_set = list({str(d.get("patient_id", "")) for d in docs if d.get("patient_id")})
    vid_set = list({str(d.get("visit_id", "")) for d in docs if d.get("visit_id")})

    patient_map: Dict[str, str] = {}
    valid_pids = [ObjectId(p) for p in pid_set if ObjectId.is_valid(p)]
    if valid_pids:
        async for pdoc in db.patients.find({"_id": {"$in": valid_pids}}, {"first_name": 1, "last_name": 1}):
            patient_map[str(pdoc["_id"])] = f"{pdoc.get('first_name','')} {pdoc.get('last_name','')}".strip()

    visit_num_map: Dict[str, str] = {}
    if vid_set:
        async for vdoc in db.visits.find({"_id": {"$in": [ObjectId(v) for v in vid_set if ObjectId.is_valid(v)]}}, {"visit_number": 1}):
            visit_num_map[str(vdoc["_id"])] = vdoc.get("visit_number", "")

    for doc in docs:
        doc["patient_name"] = patient_map.get(str(doc.get("patient_id", "")), "")
        doc["visit_number"] = visit_num_map.get(str(doc.get("visit_id", "")), "")
    return docs


# Create a bill for a visit.
async def create_bill(
    db: AsyncDatabase,
    visit_id: str,
    line_items: List[LineItem],
    created_by: str,
) -> Bill:
    visit = await get_visit(visit_id, db)
    if not visit:
        raise ValueError("Visit not found")

    existing = await db.bills.find_one({"visit_id": visit_id})
    if existing:
        raise ValueError("A bill already exists for this visit")

    patient = await get_patient_by_id(db, visit.patient_id)
    if not patient:
        raise ValueError("Patient not found")

    subtotal = round(sum(item.total_price for item in line_items), 2)
    total_amount = round(subtotal, 2)

    bill_num = await generate_bill_number(db)

    bill = BillInDB(
        visit_id=visit_id,
        patient_id=visit.patient_id,
        department_id=visit.department_id,
        bill_number=bill_num,
        visit_number=visit.visit_number,
        line_items=line_items,
        subtotal=subtotal,
        total_amount=total_amount,
        status="open",
        created_by=created_by,
        created_at=datetime.now(timezone.utc),
    )

    result = await db.bills.insert_one(bill.model_dump(by_alias=True, exclude={"id", "paid_amount", "balance_due"}))
    new_doc = await db.bills.find_one({"_id": result.inserted_id})
    created = Bill.model_validate(new_doc)

    await manager.broadcast("billing", {
        "event_type": "bill_created",
        "entity_id": str(created.id),
        "entity_type": "bill",
        "message": f"New bill created for {patient.first_name} {patient.last_name}",
        "data": {"bill_id": str(created.id), "visit_id": visit_id, "total": total_amount},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "triggered_by_role": "billing",
    })
    return created


# List bills that are still open or partly paid.
async def get_pending_bills(
    db: AsyncDatabase,
    limit: int = 50,
    visit_id: Optional[str] = None,
) -> List[Bill]:
    query: Dict[str, Any] = {}
    if visit_id:
        query["visit_id"] = visit_id
    else:
        query["status"] = {"$in": ["open", "partially_paid"]}

    cursor = db.bills.find(query).sort([("created_at", -1)]).limit(limit)
    docs = []
    async for doc in cursor:
        docs.append(doc)

    docs = await _enrich_docs(db, docs)
    return [Bill.model_validate(doc) for doc in docs]


# Get all bills regardless of status.
async def get_all_bills(db: AsyncDatabase, limit: int = 100) -> List[Bill]:
    docs = []
    async for doc in db.bills.find({}).sort([("created_at", -1)]).limit(limit):
        docs.append(doc)
    docs = await _enrich_docs(db, docs)
    return [Bill.model_validate(doc) for doc in docs]


# Fetch a bill by ID.
async def get_bill(db: AsyncDatabase, bill_id: str) -> Optional[Bill]:
    if not ObjectId.is_valid(bill_id):
        return None
    doc = await db.bills.find_one({"_id": ObjectId(bill_id)})
    if not doc:
        return None
    docs = await _enrich_docs(db, [doc])
    return Bill.model_validate(docs[0])


# Fetch the bill for a given visit.
async def get_bill_by_visit(db: AsyncDatabase, visit_id: str) -> Optional[Bill]:
    doc = await db.bills.find_one({"visit_id": visit_id})
    if not doc:
        return None
    docs = await _enrich_docs(db, [doc])
    return Bill.model_validate(docs[0])


# Update a bill's line items, status, or discount.
async def update_bill(
    db: AsyncDatabase,
    bill_id: str,
    update: BillUpdate,
    updated_by: str,
) -> Bill:
    if not ObjectId.is_valid(bill_id):
        raise ValueError("Invalid bill ID")
    doc = await db.bills.find_one({"_id": ObjectId(bill_id)})
    if not doc:
        raise ValueError("Bill not found")

    set_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if update.status is not None:
        set_fields["status"] = update.status
    if update.line_items is not None:
        items_data = [i.model_dump(exclude_none=True) for i in update.line_items]
        subtotal = round(sum(i.total_price for i in update.line_items), 2)
        set_fields["line_items"] = items_data
        set_fields["subtotal"] = subtotal
        set_fields["total_amount"] = subtotal
    if update.discount_amount is not None:
        set_fields["discount_amount"] = update.discount_amount
    if update.discount_reason is not None:
        set_fields["discount_reason"] = update.discount_reason
    if update.tax_amount is not None:
        set_fields["tax_amount"] = update.tax_amount
        current_subtotal = set_fields.get("subtotal", doc.get("subtotal", 0))
        current_discount = set_fields.get("discount_amount", doc.get("discount_amount", 0))
        set_fields["total_amount"] = round(current_subtotal - current_discount + update.tax_amount, 2)

    await db.bills.update_one({"_id": ObjectId(bill_id)}, {"$set": set_fields})
    updated_doc = await db.bills.find_one({"_id": ObjectId(bill_id)})
    docs = await _enrich_docs(db, [updated_doc])
    return Bill.model_validate(docs[0])


# Record a payment and advance the patient when fully paid.
async def add_payment(
    db: AsyncDatabase,
    bill_id: str,
    payment: Payment,
    updated_by: str,
) -> Bill:
    if not ObjectId.is_valid(bill_id):
        raise ValueError("Invalid bill ID")
    bill_doc = await db.bills.find_one({"_id": ObjectId(bill_id)})
    if not bill_doc:
        raise ValueError("Bill not found")

    bill = Bill.model_validate(bill_doc)

    if payment.amount <= 0:
        raise ValueError("Payment amount must be greater than zero")
    if payment.amount > bill.balance_due + 0.01:
        raise ValueError(f"Payment amount ({payment.amount}) exceeds balance due ({bill.balance_due})")

    if not payment.received_by:
        payment.received_by = updated_by

    bill.payments.append(payment)
    paid_amount = round(sum(p.amount for p in bill.payments), 2)

    if paid_amount >= bill.total_amount - 0.01:
        new_status = "paid"
    elif paid_amount > 0:
        new_status = "partially_paid"
    else:
        new_status = "open"

    payment_data = payment.model_dump(exclude_none=True)
    if isinstance(payment_data.get("received_at"), datetime):
        payment_data["received_at"] = payment_data["received_at"]

    update_data = {
        "$push": {"payments": payment_data},
        "$set": {
            "updated_at": datetime.now(timezone.utc),
            "status": new_status,
        },
    }

    await db.bills.update_one({"_id": ObjectId(bill_id)}, update_data)

    if new_status == "paid" and ObjectId.is_valid(str(bill.visit_id)):
        now = datetime.now(timezone.utc)
        await db.visits.update_one(
            {
                "_id": ObjectId(str(bill.visit_id)),
                "status": {"$nin": ["discharged", "cancelled"]},
            },
            {"$set": {
                "billing_completed_at": now,
                "status": "ready_for_discharge",
                "updated_at": now,
            }},
        )

    updated_doc = await db.bills.find_one({"_id": ObjectId(bill_id)})
    enriched = await _enrich_docs(db, [updated_doc])
    result = Bill.model_validate(enriched[0])

    await manager.broadcast("billing", {
        "event_type": "payment_recorded",
        "entity_id": bill_id,
        "entity_type": "bill",
        "message": f"Payment of {payment.amount:.2f} recorded. Status: {new_status}",
        "data": {
            "bill_id": bill_id,
            "amount": payment.amount,
            "method": payment.method,
            "new_status": new_status,
            "balance_due": result.balance_due,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "triggered_by_role": "billing",
    })
    return result


# Summarise revenue and collection over a date range.
async def get_revenue_summary(
    db: AsyncDatabase,
    start_date: datetime,
    end_date: datetime,
) -> Dict[str, Any]:
    pipeline = [
        {"$match": {"created_at": {"$gte": start_date, "$lte": end_date}}},
        {"$addFields": {"paid_amount": {"$sum": "$payments.amount"}}},
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "total_revenue": {"$sum": "$total_amount"},
                "paid_revenue": {"$sum": "$paid_amount"},
                "bill_count": {"$sum": 1},
                "paid_count": {"$sum": {"$cond": [{"$eq": ["$status", "paid"]}, 1, 0]}},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    cursor = await db.bills.aggregate(pipeline)
    daily = []
    async for doc in cursor:
        daily.append(doc)

    total_revenue = sum(d["total_revenue"] for d in daily)
    total_paid = sum(d["paid_revenue"] for d in daily)

    return {
        "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        "daily": daily,
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "total_paid": round(total_paid, 2),
            "outstanding": round(total_revenue - total_paid, 2),
            "collection_rate": round((total_paid / total_revenue * 100), 2) if total_revenue > 0 else 0,
        },
    }
