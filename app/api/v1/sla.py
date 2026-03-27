from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.asynchronous.database import AsyncDatabase
from pydantic import BaseModel, Field
from app.db.client import get_database
from app.security.rbac import Roles, require_roles
from app.services.sla_service import (
    get_sla_config,
    update_sla_config,
    get_live_breaches,
    get_breach_count,
)

router = APIRouter(prefix="/sla", tags=["sla"])


class SLAConfigUpdate(BaseModel):
    priority: str
    threshold_min: float = Field(..., gt=0)


@router.get("/config")
async def get_config(
    current_user=Depends(require_roles(Roles.admin, Roles.auditor)),
    db: AsyncDatabase = Depends(get_database),
):
    """Return SLA thresholds for all prescription priorities."""
    return await get_sla_config(db)


@router.put("/config")
async def update_config(
    body: SLAConfigUpdate,
    current_user=Depends(require_roles(Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    """Update the SLA threshold for a specific priority. Admin only."""
    try:
        result = await update_sla_config(
            db,
            priority=body.priority,
            threshold_min=body.threshold_min,
            updated_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_SLA_CONFIG",
                "message": str(exc),
                "details": {"priority": body.priority},
            },
        )
    return result


@router.get("/breaches/live")
async def live_breaches(
    current_user=Depends(require_roles(Roles.admin, Roles.auditor, Roles.pharmacist)),
    db: AsyncDatabase = Depends(get_database),
):
    """All active SLA breaches. Updated on each request."""
    breaches = await get_live_breaches(db)
    count = len(breaches)
    oldest = breaches[0].get("submitted_at") if breaches else None
    return {
        "breach_count": count,
        "oldest_breach_at": oldest,
        "breaches": breaches,
    }
