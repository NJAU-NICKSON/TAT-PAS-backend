from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from pydantic_core import core_schema
from datetime import datetime, timezone
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.any_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")


class LineItem(BaseModel):
    category: Literal[
        "consultation", "lab", "radiology", "pharmacy",
        "ward", "procedure", "other"
    ] = "other"
    description: str
    quantity: float = 1
    unit_price: float
    total_price: float
    reference_id: Optional[str] = None


class Payment(BaseModel):
    amount: float
    method: Literal["cash", "card", "insurance", "mobile_money", "nhif", "mpesa"]
    reference_number: Optional[str] = None
    received_by: Optional[str] = None  # set server-side if not provided
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None


class BillBase(BaseModel):
    visit_id: str
    patient_id: str
    patient_name: Optional[str] = None
    bill_number: Optional[str] = None
    visit_number: Optional[str] = None
    department_id: Optional[str] = None
    status: Literal["open", "finalized", "paid", "partially_paid", "waived"] = "open"
    line_items: List[LineItem] = []
    subtotal: float = 0
    discount_amount: float = 0
    discount_reason: Optional[str] = None
    tax_amount: float = 0
    total_amount: float = 0
    payments: List[Payment] = []
    insurance_details: Optional[dict] = None


class BillCreate(BaseModel):
    """Payload sent by the frontend to create a new bill."""
    visit_id: str
    line_items: List[LineItem] = []


class BillUpdate(BaseModel):
    status: Optional[Literal["open", "finalized", "paid", "partially_paid", "waived"]] = None
    line_items: Optional[List[LineItem]] = None
    discount_amount: Optional[float] = None
    discount_reason: Optional[str] = None
    tax_amount: Optional[float] = None


class BillInDB(BillBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None

    # Computed fields (not stored — derived on read)
    paid_amount: float = 0
    balance_due: float = 0

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    @model_validator(mode="after")
    def compute_payment_totals(self) -> "BillInDB":
        self.paid_amount = round(sum(p.amount for p in self.payments), 2)
        self.balance_due = round(max(self.total_amount - self.paid_amount, 0), 2)
        return self


Bill = BillInDB


class BillResponse(BillInDB):
    id: str
