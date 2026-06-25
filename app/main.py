from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1 import auth, users, patients, prescriptions, audits, analytics, departments, beds, visits, billing, sla, consultation_rooms, activity
from app.config import get_settings
from app.db.client import connect_db, close_db, get_database
from app.db.indexes import create_indexes
from app.jobs.scheduler import start_scheduler, stop_scheduler, scheduler
from app.security.rbac import Roles, require_roles
from app.ws import router as ws_router

logger = logging.getLogger(__name__)
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

SERVER_STARTED_AT = datetime.now(timezone.utc)


# wires up DB + scheduler for the app lifetime
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    db = await get_database()
    try:
        await db.command("ping")
        logger.info("MongoDB connected successfully")
    except Exception as e:
        logger.error("MongoDB connection error: %s", e)

    try:
        await create_indexes(db)
    except Exception as e:
        logger.error("Index creation skipped (DB unreachable at startup): %s", e)
    try:
        await start_scheduler()
    except Exception as e:
        logger.error("Scheduler start error: %s", e)

    yield

    try:
        await stop_scheduler()
    except Exception as e:
        logger.error("Scheduler stop error: %s", e)
    await close_db()


app = FastAPI(
    title="TAT-PAS API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(prescriptions.router, prefix="/api/v1")
app.include_router(audits.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(departments.router, prefix="/api/v1")
app.include_router(beds.router, prefix="/api/v1")
app.include_router(visits.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(sla.router, prefix="/api/v1")
app.include_router(consultation_rooms.router, prefix="/api/v1")
app.include_router(activity.router, prefix="/api/v1")
app.include_router(ws_router.router, prefix="")

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests", "code": "RATE_LIMIT_EXCEEDED"}
    )

# flatten pydantic errors into field/message pairs
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    formatted_errors = []
    for error in errors:
        formatted_errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": formatted_errors, "code": "VALIDATION_ERROR"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# last resort so we never leak a stack trace
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred", "code": "INTERNAL_ERROR"},
    )

@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/docs")


# Render hits this to keep the dyno alive; no auth, no DB
@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "tat-pas-backend"}


# admin-only, checks DB + scheduler + route coverage
@app.get("/api/v1/admin/health", tags=["admin"])
async def health_check(
    full: bool = False,
    current_user=Depends(require_roles(Roles.admin)),
):
    db_status = "ok"
    db_latency_ms = None
    collection_counts: dict = {}
    db = None
    try:
        db = await get_database()
        _ping_start = datetime.now(timezone.utc)
        await db.command("ping")
        db_latency_ms = round((datetime.now(timezone.utc) - _ping_start).total_seconds() * 1000, 1)
    except Exception:
        db_status = "error"

    if db is not None and db_status == "ok":
        for coll in ("users", "patients", "visits", "prescriptions",
                     "audit_records", "beds", "consultation_rooms", "departments", "bills"):
            try:
                collection_counts[coll] = await db[coll].count_documents({})
            except Exception:
                collection_counts[coll] = None

    scheduler_status = "ok" if scheduler.running else "stopped"

    expected_modules = {
        "auth": "/api/v1/auth",
        "users": "/api/v1/users",
        "patients": "/api/v1/patients",
        "prescriptions": "/api/v1/prescriptions",
        "audits": "/api/v1/audits",
        "analytics": "/api/v1/analytics",
        "departments": "/api/v1/departments",
        "beds": "/api/v1/beds",
        "visits": "/api/v1/visits",
        "billing": "/api/v1/bills",
        "sla": "/api/v1/sla",
        "consultation_rooms": "/api/v1/consultation-rooms",
        "activity": "/api/v1/activity",
        "websocket": "/ws",
    }

    module_counts = {name: 0 for name in expected_modules}
    unexpected_routes = []
    all_routes = []

    # prefer the OpenAPI paths, fall back to app.routes
    route_paths: list[str] = []
    try:
        schema = app.openapi()
        route_paths.extend(schema.get("paths", {}).keys())
    except Exception:
        pass
    for route in app.routes:
        p = getattr(route, "path", None)
        if p and p not in route_paths:
            route_paths.append(p)

    for path in route_paths:
        if path in ("/", "/docs", "/redoc", "/api/v1/admin/health"):
            continue

        matched = False
        for module_name, prefix in expected_modules.items():
            if path.startswith(prefix):
                module_counts[module_name] += 1
                matched = True
                break

        if not matched:
            unexpected_routes.append(path)

        if full:
            all_routes.append({"path": path})

    # ws isn't in the schema, count it off its own router
    module_counts["websocket"] = len(getattr(ws_router.router, "routes", []) or [])

    # status comes from DB + scheduler; route counts are just info
    overall_status = "ok"
    if db_status != "ok":
        overall_status = "degraded"
    elif scheduler_status != "ok":
        overall_status = "degraded"

    now = datetime.now(timezone.utc)
    uptime_seconds = round((now - SERVER_STARTED_AT).total_seconds())

    response = {
        "status": overall_status,
        "timestamp": now.replace(tzinfo=None).isoformat(),
        "version": app.version,
        "uptime_seconds": uptime_seconds,
        "started_at": SERVER_STARTED_AT.replace(tzinfo=None).isoformat(),
        "database": db_status,
        "database_latency_ms": db_latency_ms,
        "database_name": settings.MONGO_DB,
        "collection_counts": collection_counts,
        "scheduler": scheduler_status,
        "modules": module_counts,
        "unexpected_routes_count": len(unexpected_routes),
    }

    if full:
        response["unexpected_routes"] = unexpected_routes
        response["all_routes"] = all_routes
        response["total_routes"] = len(all_routes)
    else:
        response["note"] = "Add ?full=true to see all routes and unexpected paths."

    return response
