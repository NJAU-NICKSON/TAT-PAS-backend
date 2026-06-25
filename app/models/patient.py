from datetime import datetime, date
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from dateutil.relativedelta import relativedelta


# Patient phone and address.
class ContactInfo(BaseModel):
    phone: Optional[str] = None
    alt_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


# Patient's emergency contact.
class EmergencyContact(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    phone: Optional[str] = None


# Patient's next of kin.
class NextOfKin(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


# A recorded allergy.
class Allergy(BaseModel):
    substance: str
    reaction_type: Optional[str] = None
    severity: Literal["mild", "moderate", "severe"] = "moderate"


# Patient insurance details.
class Insurance(BaseModel):
    provider: Optional[str] = None
    policy_number: Optional[str] = None
    scheme_type: Optional[str] = None
    is_active: bool = True
    expiry_date: Optional[datetime] = None


# Kenyan National ID: digits only, 7-8 characters.
def _is_valid_national_id(value: str) -> bool:
    v = value.strip()
    return v.isdigit() and 7 <= len(v) <= 8


# True when the patient is 18 or older. Unknown DOB is treated as adult
def _is_adult(dob: Optional[datetime]) -> bool:
    age = compute_age(dob)
    return age is None or age >= 18


# Reject a date of birth in the future.
def _validate_dob_not_future(v: Optional[datetime]) -> Optional[datetime]:
    if v is None:
        return v
    today = date.today()
    dob_date = v.date() if isinstance(v, datetime) else v
    if dob_date > today:
        raise ValueError("Date of birth cannot be in the future")
    return v


# Shared patient fields.
class PatientBase(BaseModel):
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    dob: Optional[datetime] = None

    @field_validator("dob")
    @classmethod
    def _dob_not_future(cls, v: Optional[datetime]) -> Optional[datetime]:
        return _validate_dob_not_future(v)
    gender: Optional[Literal["male", "female", "other"]] = None
    blood_group: Optional[Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"]] = None
    weight_kg: Optional[float] = None
    national_id: Optional[str] = None
    guardian_national_id: Optional[str] = None
    guardian_name: Optional[str] = None
    contact: Optional[ContactInfo] = None
    emergency_contact: Optional[EmergencyContact] = None
    allergies: Optional[List[Allergy]] = None
    chronic_conditions: Optional[List[str]] = None
    current_medications: Optional[List[str]] = None
    insurance: Optional[Insurance] = None
    next_of_kin: Optional[NextOfKin] = None


# Fields for registering a patient.
class PatientCreate(PatientBase):
    mrn: Optional[str] = None

    # Require National IDs to be 7-8 digits.
    @field_validator("national_id", "guardian_national_id")
    @classmethod
    def validate_id_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        if not _is_valid_national_id(v):
            raise ValueError("National ID must be 7-8 digits")
        return v.strip()

    # Adults (18+) need their own National ID; minors need a guardian's.
    @model_validator(mode="after")
    def validate_id_by_age(self) -> "PatientCreate":
        if _is_adult(self.dob):
            if not self.national_id:
                raise ValueError("National ID is required for patients aged 18 and above")
        else:
            if not self.guardian_national_id:
                raise ValueError("Guardian National ID is required for patients under 18")
        return self


# Fields for updating a patient.
class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    dob: Optional[datetime] = None

    @field_validator("dob")
    @classmethod
    def _dob_not_future(cls, v: Optional[datetime]) -> Optional[datetime]:
        return _validate_dob_not_future(v)
    gender: Optional[Literal["male", "female", "other"]] = None
    blood_group: Optional[Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"]] = None
    weight_kg: Optional[float] = None
    national_id: Optional[str] = None
    guardian_national_id: Optional[str] = None
    guardian_name: Optional[str] = None
    contact: Optional[ContactInfo] = None
    emergency_contact: Optional[EmergencyContact] = None
    allergies: Optional[List[Allergy]] = None
    chronic_conditions: Optional[List[str]] = None
    current_medications: Optional[List[str]] = None
    insurance: Optional[Insurance] = None
    next_of_kin: Optional[NextOfKin] = None
    is_pregnant: Optional[bool] = None


# Patient as stored in the database.
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


# Patient age in whole years.
def compute_age(dob: Optional[datetime]) -> Optional[int]:
    if dob:
        today = date.today()
        dob_date = dob.date() if isinstance(dob, datetime) else dob
        return relativedelta(today, dob_date).years
    return None


# Patient age in days (for neonates).
def compute_age_days(dob: Optional[datetime]) -> Optional[int]:
    if dob:
        today = date.today()
        dob_date = dob.date() if isinstance(dob, datetime) else dob
        return (today - dob_date).days
    return None


# Patient returned by the API.
class PatientResponse(PatientInDB):
    age: Optional[int] = None
    age_days: Optional[int] = None

    # Build the patient and derive age-based flags.
    def __init__(self, **data):
        super().__init__(**data)
        if self.dob:
            object.__setattr__(self, 'age', compute_age(self.dob))
            object.__setattr__(self, 'age_days', compute_age_days(self.dob))


# Condensed patient row for lists.
class PatientSummary(BaseModel):
    id: str
    mrn: str
    first_name: str
    last_name: str
    dob: Optional[datetime] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    national_id: Optional[str] = None
    guardian_national_id: Optional[str] = None
    guardian_name: Optional[str] = None
    contact: Optional[ContactInfo] = None
    is_pregnant: bool = False
    is_paediatric: bool = False
    is_neonate: bool = False
    allergies_count: int = 0
    has_allergies: bool = False
    created_at: Optional[datetime] = None


# A patient search hit.
class PatientSearchResult(BaseModel):
    patients: List[PatientSummary]
    total: int
    page: int
    page_size: int
