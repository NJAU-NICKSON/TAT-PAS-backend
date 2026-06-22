from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from typing import List, Optional
from datetime import datetime

from app.models.bill import Bill, BillCreate, BillUpdate, LineItem, Payment
from app.models.user import UserInDB
from app.services.activity_service import log_action
from app.services.billing_service import (
    create_bill,
    get_pending_bills,
    get_all_bills,
    get_bill,
    get_bill_by_visit,
    add_payment,
    update_bill,
    get_revenue_summary,
)
from app.db.client import get_database
from app.security.rbac import Roles, get_current_user, require_roles
from app.services.pricing_service import get_catalogue, update_catalogue_item, build_bill_items
from pydantic import BaseModel, Field
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

router = APIRouter(prefix="/bills", tags=["billing"])


# Body to update a catalogue item's price.
class CatalogueUpdate(BaseModel):
    code: str
    unit_price: float = Field(..., ge=0)


# Return the editable price catalogue.
@router.get("/catalogue")
async def list_catalogue(
    current_user: UserInDB = Depends(require_roles(Roles.billing, Roles.admin, Roles.receptionist)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_catalogue(db)


# Update a catalogue item's price. Billing or admin.
@router.put("/catalogue")
async def edit_catalogue(
    body: CatalogueUpdate,
    current_user: UserInDB = Depends(require_roles(Roles.billing, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    try:
        return await update_catalogue_item(db, body.code, body.unit_price, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Auto-build a bill for a visit from the catalogue, or preview the line items.
@router.post("/auto/{visit_id}", response_model=Bill)
async def auto_generate_bill(
    request: Request,
    visit_id: str,
    current_user: UserInDB = Depends(require_roles(Roles.receptionist, Roles.billing)),
    db: AsyncDatabase = Depends(get_database),
):
    if not ObjectId.is_valid(visit_id):
        raise HTTPException(status_code=400, detail="Invalid visit id")
    visit = await db.visits.find_one({"_id": ObjectId(visit_id)})
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    items_raw = await build_bill_items(db, visit)
    if not items_raw:
        raise HTTPException(status_code=400, detail="Nothing to bill for this visit yet.")
    items = [LineItem(**i) for i in items_raw]
    try:
        bill = await create_bill(db, visit_id, items, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_action(
        db, action="bill_auto_generated", user_id=current_user.id, user_role=current_user.role,
        user_name=current_user.full_name, entity_type="bill", entity_id=str(bill.id),
        detail=f"{bill.bill_number} auto total {bill.total_amount}",
        ip_address=request.client.host if request.client else None,
    )
    return bill


# Create a new bill for a visit.
@router.post("/", response_model=Bill, status_code=status.HTTP_201_CREATED)
async def create_bill_endpoint(
    request: Request,
    data: BillCreate,
    current_user: UserInDB = Depends(require_roles(Roles.receptionist, Roles.billing)),
    db: AsyncDatabase = Depends(get_database),
):
    try:
        bill = await create_bill(db, data.visit_id, data.line_items, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_action(
        db, action="bill_generated", user_id=current_user.id, user_role=current_user.role,
        user_name=current_user.full_name, entity_type="bill", entity_id=str(bill.id),
        detail=f"{bill.bill_number} total {bill.total_amount}",
        ip_address=request.client.host if request.client else None,
    )
    return bill


# Get bills. By default returns open/partially_paid. Use all_statuses=true for all.
@router.get("/", response_model=List[Bill])
async def list_bills(
    limit: int = Query(100, ge=1, le=500),
    visit_id: Optional[str] = Query(None, description="Filter by visit ID"),
    all_statuses: bool = Query(False, description="Include all statuses (not just open/partially_paid)"),
    current_user: UserInDB = Depends(require_roles(Roles.billing, Roles.admin, Roles.auditor, Roles.receptionist)),
    db: AsyncDatabase = Depends(get_database),
):
    if all_statuses or visit_id:
        return await get_all_bills(db, limit) if not visit_id else await get_pending_bills(db, limit, visit_id)
    return await get_pending_bills(db, limit)


# Get revenue summary between two dates (ISO format: YYYY-MM-DD).
@router.get("/revenue-summary/")
async def revenue_summary(
    start_date: str,
    end_date: str,
    current_user: UserInDB = Depends(require_roles(Roles.billing, Roles.admin, Roles.auditor, Roles.receptionist)),
    db: AsyncDatabase = Depends(get_database),
):
    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    return await get_revenue_summary(db, start, end)


# Get the bill associated with a specific visit.
@router.get("/visit/{visit_id}", response_model=Optional[Bill])
async def get_bill_for_visit(
    visit_id: str,
    current_user: UserInDB = Depends(require_roles(Roles.billing, Roles.admin, Roles.auditor, Roles.doctor, Roles.nurse, Roles.receptionist)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_bill_by_visit(db, visit_id)


# Get a specific bill by ID.
@router.get("/{bill_id}", response_model=Bill)
async def get_bill_detail(
    bill_id: str,
    current_user: UserInDB = Depends(require_roles(Roles.billing, Roles.admin, Roles.auditor, Roles.doctor, Roles.nurse, Roles.receptionist)),
    db: AsyncDatabase = Depends(get_database),
):
    bill = await get_bill(db, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


# Update line items, status, or discount on a bill.
@router.patch("/{bill_id}", response_model=Bill)
async def update_bill_endpoint(
    bill_id: str,
    update: BillUpdate,
    current_user: UserInDB = Depends(require_roles(Roles.receptionist, Roles.billing)),
    db: AsyncDatabase = Depends(get_database),
):
    try:
        return await update_bill(db, bill_id, update, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Record a payment against a bill.
@router.post("/{bill_id}/payments", response_model=Bill)
async def record_payment(
    request: Request,
    bill_id: str,
    payment: Payment,
    current_user: UserInDB = Depends(require_roles(Roles.receptionist, Roles.billing)),
    db: AsyncDatabase = Depends(get_database),
):
    try:
        bill = await add_payment(db, bill_id, payment, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_action(
        db, action="payment_recorded", user_id=current_user.id, user_role=current_user.role,
        user_name=current_user.full_name, entity_type="bill", entity_id=bill_id,
        detail=f"{payment.method} {payment.amount}",
        ip_address=request.client.host if request.client else None,
    )
    return bill
