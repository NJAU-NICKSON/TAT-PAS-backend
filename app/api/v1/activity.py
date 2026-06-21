from typing import Optional
from fastapi import APIRouter, Body, Depends, Query, Request
from pymongo.asynchronous.database import AsyncDatabase
from app.db.client import get_database
from app.security.rbac import Roles, get_current_user, require_roles
from app.services.activity_service import list_activity, log_action

router = APIRouter(prefix="/activity", tags=["activity"])


# Record a client-side action (e.g. printing a receipt or prescription).
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


# List user-action log entries. Admin and auditor only.
@router.get("")
async def get_activity(
    action: Optional[str] = Query(None),
    user_role: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(require_roles(Roles.admin, Roles.auditor)),
    db: AsyncDatabase = Depends(get_database),
):
    return await list_activity(db, action=action, user_role=user_role, skip=skip, limit=limit)
