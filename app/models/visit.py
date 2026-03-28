from datetime import datetime
from enum import Enum
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field


class VisitType(str, Enum):
    opd = "opd"
    ipd = "ipd"
    emergency = "emergency"
    day_surgery = "day_surgery"
    maternity = "maternity"
    paediatric = "paediatric"
    nicu = "nicu"


class VisitStatus(str, Enum):
    registered = "registered"
    triaged = "triaged"
    waiting_for_doctor = "waiting_for_doctor"
    in_consultation = "in_consultation"
    awaiting_results = "awaiting_results"
    treatment_in_progress = "treatment_in_progress"
    admitted = "admitted"
    in_ward = "in_ward"
    ready_for_discharge = "ready_for_discharge"
    discharged = "discharged"
    cancelled = "cancelled"


class VitalSigns(BaseModel):
    blood_pressure_systolic: Optional[int] = None   # mmHg
    blood_pressure_diastolic: Optional[int] = None  # mmHg
    temperature_celsius: Optional[float] = None
    pulse_rate: Optional[int] = None                # bpm
    oxygen_saturation: Optional[float] = None       # %
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    respiratory_rate: Optional[int] = None          # breaths/min
    triage_notes: Optional[str] = None


class VisitBase(BaseModel):
    patient_id: str
    visit_type: VisitType
    department_id: str
    chief_complaint: Optional[str] = None
    priority: Literal["routine", "urgent", "critical", "immediate"] = "routine"


class VisitCreate(VisitBase):
    pass


class TriageSubmit(BaseModel):
    vitals: VitalSigns
    assigned_doctor_id: Optional[str] = None
    consultation_room: Optional[str] = None


class AdmitPatient(BaseModel):
    bed_id: str
    notes: Optional[str] = None


class VisitUpdate(BaseModel):
    status: Optional[VisitStatus] = None
    assigned_doctor_id: Optional[str] = None
    chief_complaint: Optional[str] = None
    priority: Optional[Literal["routine", "urgent", "critical", "immediate"]] = None
    billing_completed_at: Optional[datetime] = None
    consultation_room: Optional[str] = None
    consultation_nurse_id: Optional[str] = None
    diagnosis: Optional[str] = None
    clinical_findings: Optional[str] = None
    recommendations: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    discharge_notes: Optional[str] = None


class ConsultationNoteCreate(BaseModel):
    """Payload the client sends when creating/updating a consultation note."""
    consultation_room: Optional[str] = None
    assisting_nurse_id: Optional[str] = None
    chief_complaint: Optional[str] = None
    clinical_findings: Optional[str] = None
    diagnosis: Optional[str] = None
    recommendations: Optional[str] = None
    plan_of_care: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    follow_up_date: Optional[str] = None


class ConsultationNote(BaseModel):
    id: Optional[str] = None
    visit_id: Optional[str] = None
    patient_id: Optional[str] = None
    doctor_id: Optional[str] = None
    doctor_name: Optional[str] = None
    consultation_room: Optional[str] = None
    assisting_nurse_id: Optional[str] = None
    assisting_nurse_name: Optional[str] = None
    chief_complaint: Optional[str] = None
    clinical_findings: Optional[str] = None
    diagnosis: Optional[str] = None
    recommendations: Optional[str] = None
    plan_of_care: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    follow_up_date: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class VisitInDB(VisitBase):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    visit_number: str
    status: VisitStatus
    assigned_doctor_id: Optional[str] = None
    assigned_doctor_name: Optional[str] = None
    triage_nurse_id: Optional[str] = None
    triage_nurse_name: Optional[str] = None
    registered_by_id: Optional[str] = None
    registered_by_name: Optional[str] = None
    consultation_room: Optional[str] = None
    consultation_nurse_id: Optional[str] = None
    consultation_nurse_name: Optional[str] = None
    bed_id: Optional[str] = None
    bed_label: Optional[str] = None
    ward_name: Optional[str] = None
    admission_notes: Optional[str] = None
    prescription_ids: List[str] = []
    vitals: Optional[VitalSigns] = None
    # Clinical data from consultation
    diagnosis: Optional[str] = None
    clinical_findings: Optional[str] = None
    recommendations: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    discharge_notes: Optional[str] = None
    registered_at: datetime
    triaged_at: Optional[datetime] = None
    consultation_started_at: Optional[datetime] = None
    consultation_ended_at: Optional[datetime] = None
    admitted_at: Optional[datetime] = None
    billing_completed_at: Optional[datetime] = None
    discharged_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class VisitResponse(VisitInDB):
    patient_name: Optional[str] = None
