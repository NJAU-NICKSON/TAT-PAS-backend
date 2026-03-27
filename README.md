# TAT-PAS Backend

**Turnaround Time – Patient Administration System**
FastAPI · MongoDB (async) · WebSocket · APScheduler

---

## Overview

The backend is a FastAPI application that drives the TAT-PAS hospital management platform. It handles:

- **Authentication & RBAC** – JWT access/refresh tokens, 7 application roles
- **Patient & Visit management** – Registration, triage, consultation, discharge pipeline
- **Prescription pipeline** – Order → Submit → Verify → Dispense → Administer with full TAT tracking
- **Pharmacy audit system** – Automated flagging (dose, allergy, drug interaction, SLA breach), countersign workflow
- **Billing** – Bill creation, line-item management, multi-method payments, receipt generation
- **SLA monitoring** – Background scanner flags prescriptions that breach configurable SLA thresholds
- **Real-time WebSocket** – Role-based rooms broadcast live events to connected clients
- **Analytics** – TAT metrics, bottleneck detection, department performance

---

## Project Structure

```
backend/
├── app/
│   ├── api/v1/          # Route handlers (auth, patients, visits, billing, …)
│   ├── db/              # MongoDB connection + index creation
│   ├── jobs/            # APScheduler + SLA background scanner
│   ├── models/          # Pydantic models (patient, visit, bill, …)
│   ├── security/        # JWT helpers, password hashing, RBAC
│   ├── services/        # Business logic (billing, prescription, audit, …)
│   ├── ws/              # WebSocket manager + router
│   ├── config.py        # Settings (env vars via Pydantic)
│   └── main.py          # App factory, lifespan, middleware, exception handlers
├── setup_db.py          # One-time DB setup (collections, indexes, seed data)
├── requirements.txt
└── .env                 # (not committed) — see Environment Variables below
```

---

## Requirements

- Python 3.11+
- MongoDB 6.0+

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env              # then edit .env with your values

# 4. Initialise the database (run once)
python setup_db.py

# 5. Seed an admin user and demo data
python -m app.script.seed_admin

# 6. Start the development server
uvicorn app.main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB` | `tatpas` | Database name |
| `JWT_SECRET` | — | **Required.** Secret key for JWT signing |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `ALLOWED_ORIGINS` | `["http://localhost:5173"]` | CORS allowed origins (JSON array) |

Create `backend/.env`:

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=tatpas
JWT_SECRET=change-me-in-production
ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

---

## Roles

| Role | Description |
|---|---|
| `admin` | Full system access |
| `receptionist` | Register patients, create visits |
| `nurse` | Triage, ward management, bed assignment |
| `doctor` | Consultations, prescriptions |
| `pharmacist` | Verify and dispense prescriptions |
| `billing` | Create bills, record payments |
| `auditor` | Review prescriptions, manage audit records |

---

## API Modules

| Prefix | Description |
|---|---|
| `/api/v1/auth` | Login, logout, token refresh, password change |
| `/api/v1/users` | User management (admin only) |
| `/api/v1/patients` | Patient CRUD, search |
| `/api/v1/visits` | Visit lifecycle, status transitions |
| `/api/v1/prescriptions` | Prescription pipeline |
| `/api/v1/bills` | Billing, payments, revenue summary |
| `/api/v1/departments` | Department management |
| `/api/v1/beds` | Bed availability and assignment |
| `/api/v1/audits` | Audit records, countersign workflow |
| `/api/v1/analytics` | TAT metrics, SLA compliance |
| `/api/v1/sla` | SLA configuration |
| `/ws` | WebSocket (role-based rooms) |

Full interactive docs at `/docs` (Swagger) or `/redoc`.

---

## Billing

Bills are linked 1:1 to visits. Supported payment methods: `cash`, `card`, `mpesa`, `nhif`, `insurance`, `mobile_money`.

The `Bill` object returned by the API includes computed fields:

| Field | Description |
|---|---|
| `paid_amount` | Sum of all recorded payments |
| `balance_due` | `total_amount - paid_amount` (floor 0) |

Status flow: `open` → `partially_paid` → `paid` (or `finalized` / `waived`).

---

## WebSocket

Connect to `ws://localhost:8000/ws`. Token goes in the **first message** (not the URL).

```json
// Client → Server (first message)
{ "type": "auth", "token": "<access_jwt>" }

// Server → Client (on success)
{ "type": "auth_ok", "room": "billing" }

// Server → Client (event)
{
  "event_type": "payment_recorded",
  "entity_id": "<bill_id>",
  "entity_type": "bill",
  "message": "Payment of 5000.00 recorded. Status: paid",
  "data": { "bill_id": "...", "amount": 5000, "new_status": "paid" },
  "timestamp": "2026-03-22T10:00:00",
  "triggered_by_role": "billing"
}
```

Server sends `{"type":"ping"}` every 25 s; client may reply with `{"type":"pong"}`.

---

## Database Setup (`setup_db.py`)

Creates all MongoDB collections with JSON Schema validators and indexes. Seeds reference data:

- `sla_config` — SLA thresholds per prescription priority
- `drug_interactions` — 25 high-risk drug pairs
- `controlled_substances` — Schedule II–IV drugs
- `high_alert_drugs` — Medications requiring special monitoring
- `category_x_drugs` — Pregnancy category X drugs

Run once on a fresh install (safe to re-run — collections are updated, not dropped):

```bash
python setup_db.py
```

---

## Health Check

```
GET /api/v1/admin/health            # summary (admin role required)
GET /api/v1/admin/health?full=true  # with full route list
```

---

## Production

```bash
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --proxy-headers
```


