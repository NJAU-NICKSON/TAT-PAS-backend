import csv
import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pymongo.asynchronous.database import AsyncDatabase
from app.db.client import get_database
from app.security.rbac import Roles, require_roles
from app.services.analytics_service import (
    get_tat_metrics,
    get_tat_history,
    get_live_tat,
    get_bottleneck_analysis,
    get_performance_stats,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# TAT metrics for prescriptions ordered today.
@router.get("/tat/live")
async def tat_live(
    current_user=Depends(require_roles(Roles.admin, Roles.auditor)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_live_tat(db)


# Daily TAT averages from stored daily reports for the past N days.
@router.get("/tat/history")
async def tat_history(
    days: int = Query(30, ge=1, le=365),
    current_user=Depends(require_roles(Roles.admin, Roles.auditor)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_tat_history(db, days=days)


# Turnaround-time metrics over a date range.
@router.get("/tat")
async def tat_metrics(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    format: Optional[str] = Query(None, description="Set to 'csv' for CSV export"),
    current_user=Depends(require_roles(Roles.admin, Roles.auditor)),
    db: AsyncDatabase = Depends(get_database),
):
    metrics = await get_tat_metrics(db, start_date=date_from, end_date=date_to)

    if format and format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        for key, value in metrics.items():
            if key != "slowest_prescriptions":
                writer.writerow([key, value])

        if metrics.get("slowest_prescriptions"):
            writer.writerow([])
            writer.writerow(["Slowest Prescriptions"])
            writer.writerow(["id", "patient_id", "total_tat_minutes", "ordered_at"])
            for p in metrics["slowest_prescriptions"]:
                writer.writerow([
                    p.get("id", ""),
                    p.get("patient_id", ""),
                    p.get("total_tat_minutes", ""),
                    p.get("ordered_at", ""),
                ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=tat_metrics.csv"},
        )

    return metrics

# CSV export - delegates to /tat?format=csv.
@router.get("/export")
async def export_analytics(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user=Depends(require_roles(Roles.admin, Roles.auditor)),
    db: AsyncDatabase = Depends(get_database),
):
    return await tat_metrics(
        date_from=date_from,
        date_to=date_to,
        format="csv",
        current_user=current_user,
        db=db,
    )

# The slowest stage in the prescription pipeline.
@router.get("/bottlenecks")
async def bottleneck_analysis(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user=Depends(require_roles(Roles.admin, Roles.auditor)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_bottleneck_analysis(db, start_date=date_from, end_date=date_to)

# Per-staff performance figures.
@router.get("/performance")
async def performance_stats(
    role: str = Query(..., description="doctor or pharmacist"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    current_user=Depends(require_roles(Roles.admin, Roles.auditor)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_performance_stats(db, role, start_date=date_from, end_date=date_to)
 