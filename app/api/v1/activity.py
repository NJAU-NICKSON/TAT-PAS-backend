from typing import Optional
from fastapi import APIRouter, Body, Depends, Query, Request
from pymongo.asynchronous.database import AsyncDatabase
from app.db.client import get_database
from app.security.rbac import Roles, get_current_user, require_roles
from app.services.activity_service import list_activity, log_action

router = APIRouter(prefix="/activity", tags=["activity"])


# Record a client-side action like printing a receipt or prescription.
@router.post("/log", status_code=204)
async def log_client_action(
    request: Request,
    action: str = Body(..., embed=True),
    detail: Optional[str] = Body(None, embed=True),
    entity_type: Optional[str] = Body(None, embed=True),
    entity_id: Optional[str] = Body(None, embed=True),
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    await log_action(
        db, action=action, user_id=current_user.id, user_role=current_user.role,
        user_name=getattr(current_user, "full_name", None),
        entity_type=entity_type, entity_id=entity_id, detail=detail,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


# Pending notifications for the current user, derived from live data so missed WebSocket events still surface.
@router.get("/my-notifications")
async def my_notifications(
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    out = []
    role = current_user.role
    uid = current_user.id

    if role == "doctor":
        # Patients assigned to me and still active.
        async for v in db.visits.find(
            {"assigned_doctor_id": uid, "status": {"$in": ["waiting_for_doctor", "in_consultation"]}}
        ).sort("updated_at", -1).limit(20):
            out.append({
                "id": f"assign-{v['_id']}", "type": "patient_assigned",
                "title": "Patient Assigned to You",
                "subtitle": " - ".join(filter(None, [v.get("patient_name"), v.get("consultation_room"), v.get("visit_number")])) or "A patient was assigned to you",
                "timestamp": (v.get("updated_at") or v.get("registered_at")),
            })
        # Prescriptions the auditor returned to me.
        async for p in db.prescriptions.find(
            {"doctor_id": uid, "status": "pending_amendment"}
        ).sort("returned_at", -1).limit(20):
            out.append({
                "id": f"rx-pending_amendment-{p['_id']}", "type": "rx_returned",
                "title": "Returned to Doctor",
                "subtitle": " - ".join(filter(None, [f"Rx {p.get('rx_number')}" if p.get("rx_number") else None, p.get("return_reason"), "Amendment required"])),
                "timestamp": (p.get("returned_at") or p.get("updated_at")),
            })

    if role == "nurse":
        async for v in db.visits.find(
            {"consultation_nurse_id": uid, "status": {"$in": ["waiting_for_doctor", "in_consultation", "triaged"]}}
        ).sort("updated_at", -1).limit(20):
            out.append({
                "id": f"assign-{v['_id']}", "type": "patient_assigned",
                "title": "Patient Assigned to You",
                "subtitle": " - ".join(filter(None, [v.get("patient_name"), v.get("consultation_room"), v.get("visit_number")])) or "A patient was assigned to you",
                "timestamp": (v.get("updated_at") or v.get("registered_at")),
            })

    if role in ("auditor", "admin"):
        async for p in db.prescriptions.find(
            {"status": {"$in": ["submitted", "flagged"]}}
        ).sort("submitted_at", -1).limit(20):
            out.append({
                "id": f"rxnew-{p['_id']}", "type": "rx_created",
                "title": "Prescription to Review",
                "subtitle": " - ".join(filter(None, [f"Rx {p.get('rx_number')}" if p.get("rx_number") else None, p.get("patient_name"), p.get("priority")])),
                "timestamp": (p.get("submitted_at") or p.get("created_at")),
            })

    if role == "pharmacist":
        async for p in db.prescriptions.find(
            {"status": "verified"}
        ).sort("verified_at", -1).limit(20):
            out.append({
                "id": f"rx-verified-{p['_id']}", "type": "rx_verified",
                "title": "Ready to Dispense",
                "subtitle": " - ".join(filter(None, [f"Rx {p.get('rx_number')}" if p.get("rx_number") else None, p.get("patient_name")])),
                "timestamp": (p.get("verified_at") or p.get("updated_at")),
            })

    out = [o for o in out if o.get("timestamp")]
    out.sort(key=lambda o: o["timestamp"], reverse=True)
    for o in out:
        o["timestamp"] = o["timestamp"].isoformat()
    return out[:40]


# List user-action log entries this for  Admin and auditor only.
@router.get("")
async def get_activity(
    action: Optional[str] = Query(None),
    user_role: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(require_roles(Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await list_activity(db, action=action, user_role=user_role, skip=skip, limit=limit)
