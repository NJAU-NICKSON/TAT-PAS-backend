from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

# Where a prescription was ordered from.
class OrderSource(str, Enum):
    opd = "opd"
    ipd = "ipd"
    emergency = "emergency"
    theatre = "theatre"
    maternity = "maternity"
    paediatric = "paediatric"
    nicu = "nicu"
    discharge = "discharge"

# Prescription priority levels.
class Priority(str, Enum):
    stat = "stat"
    urgent = "urgent"
    routine = "routine"
    discharge = "discharge"
    nicu = "nicu"
    chemo = "chemo"

# A single medication line.
class MedicationItem(BaseModel):
    name: str
    dose: str
    route: str
    frequency: str
    duration_days: int
    dose_per_kg: Optional[float] = None
    is_high_alert: bool = False
    is_controlled: bool = False

# Prescription workflow states.
class PrescriptionStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    pending_amendment = "pending_amendment"
    flagged = "flagged"
    verified = "verified"
    dispensed = "dispensed"
    administered = "administered"
    archived = "archived"

# Shared prescription fields.
class PrescriptionBase(BaseModel):
    patient_id: str
    medications: List[MedicationItem]
    notes: Optional[str] = None

# Fields for creating a prescription.
class PrescriptionCreate(PrescriptionBase):
    visit_id: Optional[str] = None
    department_id: Optional[str] = None
    priority: Priority = Priority.routine
    order_source: OrderSource = OrderSource.opd

# Fields for updating a prescription.
class PrescriptionUpdate(BaseModel):
    status: Optional[PrescriptionStatus] = None
    notes: Optional[str] = None
    pharmacist_comment: Optional[str] = None
    return_reason: Optional[str] = None
    administered_dose: Optional[str] = None
    administered_route: Optional[str] = None
    administered_time_actual: Optional[str] = None
    administration_notes: Optional[str] = None
    receipt_number: Optional[str] = None

# Prescription as stored, with TAT fields.
class PrescriptionInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    rx_number: Optional[str] = None
    patient_id: str
    doctor_id: str
    visit_id: Optional[str] = None
    department_id: Optional[str] = None
    ward_id: Optional[str] = None
    order_source: OrderSource = OrderSource.opd
    priority: Priority = Priority.routine
    dispensed_by_id: Optional[str] = None
    dispensed_by_name: Optional[str] = None
    administered_by_id: Optional[str] = None
    administered_by_name: Optional[str] = None
    administered_dose: Optional[str] = None
    administered_route: Optional[str] = None
    administration_notes: Optional[str] = None
    receipt_number: Optional[str] = None
    auditor_id: Optional[str] = None
    auditor_name: Optional[str] = None
    auditor_approved_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    return_reason: Optional[str] = None
    medications: List[MedicationItem]
    status: PrescriptionStatus
    
    ordered_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    dispensed_at: Optional[datetime] = None
    administered_at: Optional[datetime] = None
    
    tat_order_to_submit_min: Optional[float] = None
    tat_submit_to_verify_min: Optional[float] = None
    tat_flag_hold_min: Optional[float] = None
    tat_verify_to_dispense_min: Optional[float] = None
    tat_dispense_to_admin_min: Optional[float] = None
    tat_total_min: Optional[float] = None
    tat_pharmacy_min: Optional[float] = None
    
    sla_threshold_min: Optional[float] = None
    sla_breached: bool = False
    sla_breach_duration_min: Optional[float] = None
    tat_breached_at: Optional[datetime] = None
    
    flags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    pharmacist_comment: Optional[str] = None
    weight_kg: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None

PrescriptionResponse = PrescriptionInDB