from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security.rbac import Roles
from app.security.passwords import validate_password_length


class UserBase(BaseModel):
    username: str
    full_name: str
    email: str
    role: str
    department_id: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = [r.value for r in Roles]
        if v not in valid_roles:
            raise ValueError(f"Invalid role '{v}'. Must be one of {valid_roles}")
        return v


class UserCreate(UserBase):
    password: str

    # 8+ chars, at least one digit
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        validate_password_length(v)
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    department_id: Optional[str] = None
    password: Optional[str] = None

    # 8+ chars, at least one digit
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters")
            if not any(c.isdigit() for c in v):
                raise ValueError("Password must contain at least one number")
            validate_password_length(v)
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_roles = [r.value for r in Roles]
            if v not in valid_roles:
                raise ValueError(f"Invalid role '{v}'. Must be one of {valid_roles}")
        return v


class UserInDB(UserBase):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id", default="")
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    last_login: Optional[datetime] = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_object_id(cls, v: Any) -> str:
        return str(v)


class UserResponse(UserBase):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    # 8+ chars, at least one digit
    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        validate_password_length(v)
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
