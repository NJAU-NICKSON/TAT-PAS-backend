from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Import Roles enum from your RBAC module
from app.security.rbac import Roles


class UserBase(BaseModel):
    username: str
    full_name: str
    email: str
    role: str
    department_id: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Ensure the role is one of the predefined roles."""
        valid_roles = [r.value for r in Roles]
        if v not in valid_roles:
            raise ValueError(f"Invalid role '{v}'. Must be one of {valid_roles}")
        return v


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    department_id: Optional[str] = None
    password: Optional[str] = None

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
    created_at: datetime
    last_login: Optional[datetime] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse