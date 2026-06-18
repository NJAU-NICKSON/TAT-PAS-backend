from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


BedType = Literal[
    "general",
    "icu",
    "hdu",
    "nicu",
    "isolation",
    "maternity",
    "birthing",
    "paediatric",
    "day_case",
    "consultation",     
    "procedure_room",   
]

BedStatus = Literal[
    "available",
    "occupied",
    "reserved",
    "cleaning",
    "maintenance"
]


# Shared bed fields.
class BedBase(BaseModel):
    department_id: str
    ward_name: str
    room_number: str
    bed_number: str
    bed_label: str
    bed_type: BedType = "general"
    status: BedStatus = "available"
    notes: Optional[str] = None


# Fields for creating a bed.
class BedCreate(BedBase):
    current_patient_id: Optional[str] = None
    current_admission_id: Optional[str] = None


# Fields for updating a bed.
class BedUpdate(BaseModel):
    status: Optional[BedStatus] = None
    current_patient_id: Optional[str] = None
    current_admission_id: Optional[str] = None
    notes: Optional[str] = None
    last_cleaned_at: Optional[datetime] = None


# Bed as stored in the database.
class BedInDB(BedBase):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    current_patient_id: Optional[str] = None
    current_admission_id: Optional[str] = None
    last_cleaned_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Bed returned by the API.
class BedResponse(BedInDB):
    pass


# Bed plus its current patient.
class BedWithPatient(BedInDB):
    patient_name: Optional[str] = None
    patient_mrn: Optional[str] = None


# Per-department bed availability counts.
class BedAvailabilitySummary(BaseModel):
    department_id: str
    department_name: str
    department_code: str
    total: int
    available: int
    occupied: int
    reserved: int
    cleaning: int
    maintenance: int
