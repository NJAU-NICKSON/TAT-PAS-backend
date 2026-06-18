from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


# Kinds of audit records (automated, manual, etc.).
class AuditType(str, Enum):
    automated = "automated"
    manual = "manual"
    sla_breach = "sla_breach"
    sla_warning = "sla_warning"
    status_change = "status_change"
    countersign = "countersign"
    resolution = "resolution"


# Severity levels for a flag.
class AuditSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# Allowed ways to resolve a flag.
class ResolutionType(str, Enum):
    accepted_risk = "accepted_risk"
    dose_adjusted = "dose_adjusted"
    drug_changed = "drug_changed"
    prescription_cancelled = "prescription_cancelled"
    false_positive = "false_positive"


# Kinds of security events.
class SecurityEventType(str, Enum):
    login_failure = "login_failure"
    role_change = "role_change"
    password_reset = "password_reset"
    sla_breach = "sla_breach"
    permission_change = "permission_change"


# Shared audit-record fields.
class AuditRecordBase(BaseModel):
    prescription_id: str
    visit_id: Optional[str] = None
    department_id: Optional[str] = None
    patient_id: Optional[str] = None
    flag_code: str = "generic"
    drug_name: Optional[str] = None
    dose: Optional[str] = None
    patient_age: Optional[int] = None
    patient_allergies_snapshot: List[str] = Field(default_factory=list)
    tat_pharmacy_min_at_flag: Optional[float] = None
    sla_threshold_min: Optional[float] = None
    created_by: str
    created_by_role: str
    type: AuditType
    issue: str
    severity: AuditSeverity
    recommendation: Optional[str] = None
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_type: Optional[ResolutionType] = None
    resolution_note: Optional[str] = None
    countersigned: bool = False
    countersigned_by: Optional[str] = None
    countersigned_at: Optional[datetime] = None
    countersign_note: Optional[str] = None
    original_flag_id: Optional[str] = None
    esig_required: Optional[bool] = None
    esig_confirmed_by: Optional[str] = None
    esig_confirmed_at: Optional[datetime] = None
    before_snapshot: Optional[Dict[str, Any]] = None
    after_snapshot: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_security_event: bool = False
    security_event_type: Optional[SecurityEventType] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    created_at: datetime
    rx_number: Optional[str] = None
    patient_name: Optional[str] = None


# Audit record as stored in the database.
class AuditRecordInDB(AuditRecordBase):
    id: str


# Audit record returned by the API.
class AuditRecordResponse(AuditRecordBase):
    id: str


# Request body to countersign a flag.
class CountersignRequest(BaseModel):
    flag_id: str = Field(..., description="ID of the original flag record to countersign")
    note: str = Field(..., min_length=10, description="Attestation note from countersigning auditor")
