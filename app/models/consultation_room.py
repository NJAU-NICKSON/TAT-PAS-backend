from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict


ConsultationRoomStatus = Literal["available", "occupied", "cleaning", "reserved"]


class ConsultationRoomBase(BaseModel):
    department_id: str
    room_number: str
    room_name: str
    floor: Optional[str] = None
    notes: Optional[str] = None


class ConsultationRoomCreate(ConsultationRoomBase):
    status: ConsultationRoomStatus = "available"
    current_doctor_id: Optional[str] = None
    current_patient_id: Optional[str] = None


class ConsultationRoomUpdate(BaseModel):
    status: Optional[ConsultationRoomStatus] = None
    current_doctor_id: Optional[str] = None
    current_patient_id: Optional[str] = None
    notes: Optional[str] = None


class ConsultationRoomInDB(ConsultationRoomBase):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    status: ConsultationRoomStatus = "available"
    current_doctor_id: Optional[str] = None
    current_patient_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class ConsultationRoomResponse(ConsultationRoomInDB):
    pass


class ConsultationRoomWithOccupants(ConsultationRoomInDB):
    current_doctor_name: Optional[str] = None
    current_patient_name: Optional[str] = None
