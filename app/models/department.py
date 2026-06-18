from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# A sub-area within a department.
class SubArea(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None


# Shared department fields.
class DepartmentBase(BaseModel):
    name: str
    code: str
    type: str = Field(..., description="clinical | diagnostic | support | administrative")
    floor: str
    wing: Optional[str] = None
    description: Optional[str] = None
    accepts_emergency: bool = False
    is_active: bool = True
    sub_areas: Optional[List[SubArea]] = None
    bed_count: Optional[int] = None


# Fields for creating a department.
class DepartmentCreate(DepartmentBase):
    head_user_id: Optional[str] = None


# Fields for updating a department.
class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    floor: Optional[str] = None
    wing: Optional[str] = None
    head_user_id: Optional[str] = None
    accepts_emergency: Optional[bool] = None
    is_active: Optional[bool] = None
    sub_areas: Optional[List[SubArea]] = None
    bed_count: Optional[int] = None


# Department as stored in the database.
class DepartmentInDB(DepartmentBase):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    head_user_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Department returned by the API.
class DepartmentResponse(DepartmentInDB):
    pass


# Department plus its bed availability.
class DepartmentWithBedSummary(DepartmentInDB):
    total_beds: int = 0
    available_beds: int = 0
    occupied_beds: int = 0
    reserved_beds: int = 0
    cleaning_beds: int = 0
    maintenance_beds: int = 0
