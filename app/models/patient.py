from datetime import datetime, date
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, field_validator
from dateutil.relativedelta import relativedelta


class ContactInfo(BaseModel):
    phone: Optional[str] = None
    alt_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class EmergencyContact(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    phone: Optional[str] = None


class NextOfKin(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class Allergy(BaseModel):
    substance: str
    reaction_type: Optional[str] = None
    severity: Literal["mild", "moderate", "severe"] = "moderate"


class Insurance(BaseModel):
    provider: Optional[str] = None
    policy_number: Optional[str] = None
    scheme_type: Optional[str] = None
    is_active: bool = True
    expiry_date: Optional[datetime] = None


class PatientBase(BaseModel):
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    dob: Optional[datetime] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    blood_group: Optional[Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"]] = None
    weight_kg: Optional[float] = None
    contact: Optional[ContactInfo] = None
    emergency_contact: Optional[EmergencyContact] = None
    allergies: Optional[List[Allergy]] = None
    chronic_conditions: Optional[List[str]] = None
    current_medications: Optional[List[str]] = None
    insurance: Optional[Insurance] = None
    next_of_kin: Optional[NextOfKin] = None


class PatientCreate(PatientBase):
    mrn: Optional[str] = None


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    dob: Optional[datetime] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    blood_group: Optional[Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"]] = None
    weight_kg: Optional[float] = None
    contact: Optional[ContactInfo] = None
    emergency_contact: Optional[EmergencyContact] = None
    allergies: Optional[List[Allergy]] = None
    chronic_conditions: Optional[List[str]] = None
    current_medications: Optional[List[str]] = None
    insurance: Optional[Insurance] = None
    next_of_kin: Optional[NextOfKin] = None
    is_pregnant: Optional[bool] = None


class PatientInDB(PatientBase):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    mrn: str
    is_pregnant: bool = False
    is_paediatric: bool = False
    is_neonate: bool = False
    registered_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


def compute_age(dob: Optional[datetime]) -> Optional[int]:
    if dob:
        today = date.today()
        dob_date = dob.date() if isinstance(dob, datetime) else dob
        return relativedelta(today, dob_date).years
    return None


def compute_age_days(dob: Optional[datetime]) -> Optional[int]:
    if dob:
        today = date.today()
        dob_date = dob.date() if isinstance(dob, datetime) else dob
        return (today - dob_date).days
    return None


class PatientResponse(PatientInDB):
    age: Optional[int] = None
    age_days: Optional[int] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.dob:
            object.__setattr__(self, 'age', compute_age(self.dob))
            object.__setattr__(self, 'age_days', compute_age_days(self.dob))


class PatientSummary(BaseModel):
    id: str
    mrn: str
    first_name: str
    last_name: str
    dob: Optional[datetime] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    is_pregnant: bool = False
    is_paediatric: bool = False
    is_neonate: bool = False
    allergies_count: int = 0
    has_allergies: bool = False


class PatientSearchResult(BaseModel):
    patients: List[PatientSummary]
    total: int
    page: int
    page_size: int
