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
from app.services.dosing_service import get_dose_limits, update_dose_limit

router = APIRouter(prefix="/sla", tags=["sla"])


# Request body to update an SLA threshold.
class SLAConfigUpdate(BaseModel):
    priority: str
    threshold_min: float = Field(..., gt=0)


# Request body to update a drug's dose limits.
class DoseLimitUpdate(BaseModel):
    drug: str
    adult_max_single_mg: float = Field(..., gt=0)
    max_mg_per_kg_day: float = Field(..., gt=0)
    abs_max_mg_day: float = Field(..., gt=0)


# Return SLA thresholds for all prescription priorities.
@router.get("/config")
async def get_config(
    current_user=Depends(require_roles(Roles.admin, Roles.auditor)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_sla_config(db)


# Update the SLA threshold for a priority. Auditor owns compliance; admin configures.
@router.put("/config")
async def update_config(
    body: SLAConfigUpdate,
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
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


# Return per-drug dose limits used by the prescription audit.
@router.get("/dose-limits")
async def dose_limits(
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_dose_limits(db)


# Update the dose limits for one drug. Auditor (compliance) or admin.
@router.put("/dose-limits")
async def update_dose_limit_endpoint(
    body: DoseLimitUpdate,
    current_user=Depends(require_roles(Roles.auditor, Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    try:
        return await update_dose_limit(
            db,
            drug=body.drug,
            adult_max_single_mg=body.adult_max_single_mg,
            max_mg_per_kg_day=body.max_mg_per_kg_day,
            abs_max_mg_day=body.abs_max_mg_day,
            updated_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DOSE_LIMIT", "message": str(exc), "details": {"drug": body.drug}},
        )


# All active SLA breaches. Updated on each request.
@router.get("/breaches/live")
async def live_breaches(
    current_user=Depends(require_roles(Roles.admin, Roles.auditor, Roles.pharmacist)),
    db: AsyncDatabase = Depends(get_database),
):
    breaches = await get_live_breaches(db)
    count = len(breaches)
    oldest = breaches[0].get("submitted_at") if breaches else None
    return {
        "breach_count": count,
        "oldest_breach_at": oldest,
        "breaches": breaches,
    }
