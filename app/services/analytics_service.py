from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase


def _safe_avg(values: list) -> float:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return 0.0
    return round(sum(filtered) / len(filtered), 2)


def _calc_p95(values: list) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = min(int(len(sorted_vals) * 0.95), len(sorted_vals) - 1)
    return round(sorted_vals[idx], 2)


async def get_tat_metrics(
    db: AsyncDatabase,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    match_stage: dict = {}
    if start_date or end_date:
        date_filter: dict = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        match_stage["ordered_at"] = date_filter

    pipeline = [
        {"$match": match_stage} if match_stage else {"$match": {}},
        {
            "$project": {
                "patient_id": 1,
                "status": 1,
                "ordered_at": 1,
                "verified_at": 1,
                "dispensed_at": 1,
                "administered_at": 1,
                "flags": 1,
                "priority": 1,
                "rx_number": 1,
                "order_to_verify_minutes": {
                    "$cond": {
                        "if": {
                            "$and": [
                                {"$ifNull": ["$ordered_at", False]},
                                {"$ifNull": ["$verified_at", False]},
                            ]
                        },
                        "then": {
                            "$divide": [
                                {"$subtract": ["$verified_at", "$ordered_at"]},
                                60000,
                            ]
                        },
                        "else": None,
                    }
                },
                "verify_to_dispense_minutes": {
                    "$cond": {
                        "if": {
                            "$and": [
                                {"$ifNull": ["$verified_at", False]},
                                {"$ifNull": ["$dispensed_at", False]},
                            ]
                        },
                        "then": {
                            "$divide": [
                                {"$subtract": ["$dispensed_at", "$verified_at"]},
                                60000,
                            ]
                        },
                        "else": None,
                    }
                },
                "dispense_to_administer_minutes": {
                    "$cond": {
                        "if": {
                            "$and": [
                                {"$ifNull": ["$dispensed_at", False]},
                                {"$ifNull": ["$administered_at", False]},
                            ]
                        },
                        "then": {
                            "$divide": [
                                {"$subtract": ["$administered_at", "$dispensed_at"]},
                                60000,
                            ]
                        },
                        "else": None,
                    }
                },
                "total_tat_minutes": {
                    "$cond": {
                        "if": {
                            "$and": [
                                {"$ifNull": ["$ordered_at", False]},
                                {"$ifNull": ["$administered_at", False]},
                            ]
                        },
                        "then": {
                            "$divide": [
                                {"$subtract": ["$administered_at", "$ordered_at"]},
                                60000,
                            ]
                        },
                        "else": None,
                    }
                },
            }
        },
        {
            "$group": {
                "_id": None,
                "total_prescriptions": {"$sum": 1},
                "completed_prescriptions": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", "administered"]}, 1, 0]
                    }
                },
                "avg_total_tat": {"$avg": "$total_tat_minutes"},
                "avg_order_to_verify": {"$avg": "$order_to_verify_minutes"},
                "avg_verify_to_dispense": {"$avg": "$verify_to_dispense_minutes"},
                "avg_dispense_to_administer": {
                    "$avg": "$dispense_to_administer_minutes"
                },
                "flagged_count": {
                    "$sum": {
                        "$cond": [{"$gt": [{"$size": "$flags"}, 0]}, 1, 0]
                    }
                },
                "all_prescriptions": {
                    "$push": {
                        "id": {"$toString": "$_id"},
                        "patient_id": "$patient_id",
                        "rx_number": "$rx_number",
                        "total_tat_minutes": "$total_tat_minutes",
                        "ordered_at": "$ordered_at",
                    }
                },
            }
        },
    ]

    cursor = await db.prescriptions.aggregate(pipeline)
    results = await cursor.to_list(length=1)

    resolved_count = await db.audit_records.count_documents({"resolved": True})
    total_audit = await db.audit_records.count_documents({})

    if not results:
        return _empty_tat_metrics()

    row = results[0]
    all_prescriptions = row.get("all_prescriptions", [])
    slowest = sorted(
        [p for p in all_prescriptions if p.get("total_tat_minutes") is not None],
        key=lambda x: x["total_tat_minutes"],
        reverse=True,
    )[:5]

    for p in slowest:
        if p.get("ordered_at") and isinstance(p["ordered_at"], datetime):
            p["ordered_at"] = p["ordered_at"].isoformat()

    # Enrich slowest prescriptions with patient names
    if slowest:
        patient_ids = list({p["patient_id"] for p in slowest if p.get("patient_id")})
        patients = await db.patients.find(
            {"_id": {"$in": [ObjectId(pid) for pid in patient_ids if len(pid) == 24]}},
            {"_id": 1, "first_name": 1, "last_name": 1}
        ).to_list(length=len(patient_ids))
        patient_map = {str(pt["_id"]): f"{pt.get('first_name', '')} {pt.get('last_name', '')}".strip() for pt in patients}
        for p in slowest:
            if p.get("patient_id"):
                p["patient_name"] = patient_map.get(p["patient_id"])

    resolution_rate = (resolved_count / total_audit * 100) if total_audit > 0 else 0.0

    return {
        "total_prescriptions": row.get("total_prescriptions", 0),
        "completed_prescriptions": row.get("completed_prescriptions", 0),
        "average_total_tat_minutes": round(row.get("avg_total_tat") or 0.0, 2),
        "average_order_to_verify_minutes": round(row.get("avg_order_to_verify") or 0.0, 2),
        "average_verify_to_dispense_minutes": round(row.get("avg_verify_to_dispense") or 0.0, 2),
        "average_dispense_to_administer_minutes": round(row.get("avg_dispense_to_administer") or 0.0, 2),
        "flagged_count": row.get("flagged_count", 0),
        "resolved_flags_count": resolved_count,
        "resolution_rate": round(resolution_rate, 2),
        "slowest_prescriptions": slowest,
    }


def _empty_tat_metrics() -> dict:
    return {
        "total_prescriptions": 0,
        "completed_prescriptions": 0,
        "average_total_tat_minutes": 0.0,
        "average_order_to_verify_minutes": 0.0,
        "average_verify_to_dispense_minutes": 0.0,
        "average_dispense_to_administer_minutes": 0.0,
        "flagged_count": 0,
        "resolved_flags_count": 0,
        "resolution_rate": 0.0,
        "slowest_prescriptions": [],
    }


# Alias used by sla_scanner.generate_daily_report
async def get_tat_summary(
    db: AsyncDatabase,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    return await get_tat_metrics(db, start_date=start_date, end_date=end_date)


async def get_tat_history(
    db: AsyncDatabase,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """Return daily TAT averages for the past N days using stored daily_reports."""
    cursor = db.daily_reports.find({}).sort("date", -1).limit(days)
    docs = await cursor.to_list(length=days)
    result = []
    for doc in docs:
        date_val = doc.get("date")
        date_str = date_val.isoformat() if isinstance(date_val, datetime) else str(date_val)
        summary = doc.get("summary", {})
        result.append({
            "date": date_str,
            "avg_total_tat_minutes": summary.get("average_total_tat_minutes", 0.0),
            "avg_order_to_verify_minutes": summary.get("average_order_to_verify_minutes", 0.0),
            "avg_verify_to_dispense_minutes": summary.get("average_verify_to_dispense_minutes", 0.0),
            "total_prescriptions": summary.get("total_prescriptions", 0),
            "resolution_rate": summary.get("resolution_rate", 0.0),
        })
    return list(reversed(result))


async def get_live_tat(db: AsyncDatabase) -> dict:
    """TAT metrics computed only from prescriptions ordered today."""
    from datetime import timezone, timedelta
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return await get_tat_metrics(db, start_date=start, end_date=now)


async def get_bottleneck_analysis(
    db: AsyncDatabase,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    match_stage: dict = {}
    if start_date or end_date:
        date_filter: dict = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        match_stage["ordered_at"] = date_filter

    pipeline = [
        {"$match": match_stage} if match_stage else {"$match": {}},
        {"$match": {"status": "administered"}},
        {
            "$project": {
                "verify_delay": {
                    "$cond": {
                        "if": {"$and": [{"$ifNull": ["$submitted_at", False]}, {"$ifNull": ["$verified_at", False]}]},
                        "then": {"$divide": [{"$subtract": ["$verified_at", "$submitted_at"]}, 60000]},
                        "else": None,
                    }
                },
                "dispense_delay": {
                    "$cond": {
                        "if": {"$and": [{"$ifNull": ["$verified_at", False]}, {"$ifNull": ["$dispensed_at", False]}]},
                        "then": {"$divide": [{"$subtract": ["$dispensed_at", "$verified_at"]}, 60000]},
                        "else": None,
                    }
                },
                "admin_delay": {
                    "$cond": {
                        "if": {"$and": [{"$ifNull": ["$dispensed_at", False]}, {"$ifNull": ["$administered_at", False]}]},
                        "then": {"$divide": [{"$subtract": ["$administered_at", "$dispensed_at"]}, 60000]},
                        "else": None,
                    }
                },
                "pharmacy_total": {
                    "$cond": {
                        "if": {"$and": [{"$ifNull": ["$submitted_at", False]}, {"$ifNull": ["$dispensed_at", False]}]},
                        "then": {"$divide": [{"$subtract": ["$dispensed_at", "$submitted_at"]}, 60000]},
                        "else": None,
                    }
                },
            }
        },
        {
            "$group": {
                "_id": None,
                "verify_values": {"$push": "$verify_delay"},
                "dispense_values": {"$push": "$dispense_delay"},
                "admin_values": {"$push": "$admin_delay"},
                "pharmacy_values": {"$push": "$pharmacy_total"},
            }
        },
    ]

    cursor = await db.prescriptions.aggregate(pipeline)
    result = await cursor.to_list(length=1)
    if not result:
        return {
            "verification_queue": {"avg": 0.0, "p95": 0.0, "count": 0},
            "dispensing_queue": {"avg": 0.0, "p95": 0.0, "count": 0},
            "administration_queue": {"avg": 0.0, "p95": 0.0, "count": 0},
            "total_pharmacy_tat": {"avg": 0.0, "p95": 0.0, "count": 0},
        }

    row = result[0]

    def _stats(values: list) -> dict:
        clean = [v for v in values if v is not None]
        return {
            "avg": _safe_avg(clean),
            "p95": _calc_p95(clean),
            "count": len(clean),
        }

    return {
        "verification_queue": _stats(row.get("verify_values", [])),
        "dispensing_queue": _stats(row.get("dispense_values", [])),
        "administration_queue": _stats(row.get("admin_values", [])),
        "total_pharmacy_tat": _stats(row.get("pharmacy_values", [])),
    }


async def get_performance_stats(
    db: AsyncDatabase,
    role: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    match_stage: dict = {}
    if start_date or end_date:
        date_filter: dict = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        match_stage["ordered_at"] = date_filter

    if role == "doctor":
        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {
                "$group": {
                    "_id": "$doctor_id",
                    "prescriptions": {"$sum": 1},
                    "avg_order_to_submit": {"$avg": "$tat_order_to_submit_min"},
                    "flagged_count": {
                        "$sum": {"$cond": [{"$gt": [{"$size": "$flags"}, 0]}, 1, 0]}
                    },
                }
            },
            {
                "$addFields": {
                    "doctor_obj_id": {
                        "$cond": {
                            "if": {"$eq": [{"$type": "$_id"}, "string"]},
                            "then": {"$toObjectId": "$_id"},
                            "else": "$_id",
                        }
                    }
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "doctor_obj_id",
                    "foreignField": "_id",
                    "as": "doctor_info",
                }
            },
            {
                "$project": {
                    "doctor_id": {"$toString": "$_id"},
                    "doctor_name": {
                        "$cond": {
                            "if": {"$gt": [{"$size": "$doctor_info"}, 0]},
                            "then": {"$arrayElemAt": ["$doctor_info.full_name", 0]},
                            "else": "Unknown",
                        }
                    },
                    "prescriptions": 1,
                    "avg_order_to_submit": {"$round": ["$avg_order_to_submit", 2]},
                    "flag_rate": {
                        "$cond": {
                            "if": {"$gt": ["$prescriptions", 0]},
                            "then": {
                                "$round": [
                                    {"$multiply": [{"$divide": ["$flagged_count", "$prescriptions"]}, 100]},
                                    2,
                                ]
                            },
                            "else": 0.0,
                        }
                    },
                }
            },
            {"$sort": {"prescriptions": -1}},
        ]
    else:
        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {"$match": {"dispensed_by_id": {"$ne": None}}},
            {
                "$group": {
                    "_id": "$dispensed_by_id",
                    "dispensed": {"$sum": 1},
                    "avg_verify_to_dispense": {"$avg": "$tat_verify_to_dispense_min"},
                }
            },
            {
                "$addFields": {
                    "pharm_obj_id": {
                        "$cond": {
                            "if": {"$eq": [{"$type": "$_id"}, "string"]},
                            "then": {"$toObjectId": "$_id"},
                            "else": "$_id",
                        }
                    }
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "pharm_obj_id",
                    "foreignField": "_id",
                    "as": "pharmacist_info",
                }
            },
            {
                "$project": {
                    "pharmacist_id": {"$toString": "$_id"},
                    "pharmacist_name": {
                        "$cond": {
                            "if": {"$gt": [{"$size": "$pharmacist_info"}, 0]},
                            "then": {
                                "$ifNull": [
                                    {"$arrayElemAt": ["$pharmacist_info.full_name", 0]},
                                    {"$arrayElemAt": ["$pharmacist_info.username", 0]},
                                ]
                            },
                            "else": "Unknown",
                        }
                    },
                    "dispensed": 1,
                    "avg_verify_to_dispense": {"$round": ["$avg_verify_to_dispense", 2]},
                }
            },
            {"$sort": {"dispensed": -1}},
        ]

    cursor = await db.prescriptions.aggregate(pipeline)
    results = await cursor.to_list(length=None)
    return results
