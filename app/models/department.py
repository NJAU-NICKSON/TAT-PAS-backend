from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class SubArea(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None


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


class DepartmentCreate(DepartmentBase):
    head_user_id: Optional[str] = None


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


class DepartmentInDB(DepartmentBase):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    head_user_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class DepartmentResponse(DepartmentInDB):
    pass


class DepartmentWithBedSummary(DepartmentInDB):
    total_beds: int = 0
    available_beds: int = 0
    occupied_beds: int = 0
    reserved_beds: int = 0
    cleaning_beds: int = 0
    maintenance_beds: int = 0
