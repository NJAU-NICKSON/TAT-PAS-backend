# TAT-PAS Backend

FastAPI application that powers the TAT-PAS hospital system.

Handles authentication, patient and visit management, prescription pipeline, pharmacy audit, billing, SLA monitoring, real-time WebSocket events, and analytics.

## Requirements

- Python 3.11+
- MongoDB 6.0+

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in values (see below)
python setup_db.py              # run once — creates collections and seeds reference data
uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000
Swagger docs: http://localhost:8000/docs

## Environment variables

Create `backend/.env`:

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=tatpas
JWT_SECRET=change-me-in-production
ALLOWED_ORIGINS=["http://localhost:5173"]
```

| Variable | Default | Notes |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB` | `tatpas` | Database name |
| `JWT_SECRET` | — | Required. Use a long random string in production |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |
| `ALLOWED_ORIGINS` | `["http://localhost:5173"]` | CORS origins (JSON array) |

## Project structure

```
app/
├── api/v1/         Route handlers — one file per resource
├── db/             MongoDB client and index creation
├── jobs/           APScheduler + SLA background scanner
├── models/         Pydantic models (request / response / DB)
├── security/       JWT helpers, password hashing, RBAC guards
├── services/       Business logic — one file per domain
├── ws/             WebSocket connection manager and router
├── config.py       Settings loaded from .env via Pydantic
└── main.py         App factory, CORS, lifespan, middleware
```

## API routes

| Prefix | What it covers |
|---|---|
| `/api/v1/auth` | Login, logout, token refresh, password change |
| `/api/v1/users` | User management (admin only) |
| `/api/v1/patients` | Patient CRUD and search |
| `/api/v1/visits` | Visit lifecycle and status transitions |
| `/api/v1/prescriptions` | Prescription pipeline |
| `/api/v1/bills` | Billing, payments, revenue summary |
| `/api/v1/departments` | Department management |
| `/api/v1/beds` | Bed availability and assignment |
| `/api/v1/audits` | Audit records and countersign workflow |
| `/api/v1/analytics` | TAT metrics, SLA compliance, bottlenecks |
| `/api/v1/sla` | SLA configuration per prescription priority |
| `/ws` | WebSocket — role-based rooms |

## Roles

| Role | Access |
|---|---|
| `admin` | Full system access |
| `receptionist` | Register patients, create visits |
| `nurse` | Triage, ward management, bed assignment |
| `doctor` | Consultations, write prescriptions |
| `pharmacist` | Verify and dispense prescriptions |
| `billing` | Create bills, record payments |
| `auditor` | Review prescriptions, manage audit records |

## Prescription audit flags

When a prescription is submitted the system checks it automatically. Any of the following raise a flag:

| Flag | Severity | Reason |
|---|---|---|
| `allergy_match` | CRITICAL | Drug matches a recorded patient allergy |
| `high_dose` | HIGH | Dose exceeds the safety threshold |
| `drug_interaction` | HIGH | Interaction with another active prescription |
| `sla_breach` | HIGH | Pharmacy TAT exceeded the SLA target |
| `controlled_sub` | MEDIUM | Controlled or scheduled substance |
| `extended_duration` | MEDIUM | Prescription runs longer than 30 days |
| `duplicate_rx` | MEDIUM | Similar active prescription already exists |
| `manual_flag` | INFO | Flagged manually by an auditor |

A flagged prescription must be reviewed and countersigned by an auditor before the pharmacist can dispense.

## WebSocket

Connect to `ws://localhost:8000/ws`. Send the JWT in the first message — not in the URL.

```json
// Authenticate
{ "type": "auth", "token": "<access_token>" }

// Server confirms and assigns room
{ "type": "auth_ok", "room": "billing" }

// Incoming event
{
  "event_type": "payment_recorded",
  "entity_id": "<bill_id>",
  "message": "Payment of 5000.00 recorded. Status: paid",
  "data": { "bill_id": "...", "amount": 5000, "new_status": "paid" },
  "timestamp": "2026-03-22T10:00:00"
}
```

The server sends `{"type":"ping"}` every 25 seconds. The server keeps separate rooms per role: `pharmacy`, `auditor`, `billing`, `receptionist`, `doctor:<id>`, `ward:<department_id>`.

## Database setup

`setup_db.py` creates MongoDB collections with schema validators and indexes, then seeds required reference data:

- SLA thresholds (STAT / Urgent / Routine)
- 25 high-risk drug interaction pairs
- Controlled substances list
- High-alert drugs
- Pregnancy category X drugs

Safe to re-run — it updates existing documents rather than dropping collections.

## SLA thresholds (pharmacy TAT)

| Priority | Target |
|---|---|
| STAT | 15 minutes |
| Urgent | 30 minutes |
| Routine | 60 minutes |

## Running tests

```bash
pytest tests/
```

## Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers
```
