from enum import Enum
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.asynchronous.database import AsyncDatabase
from bson import ObjectId
from app.security.jwt import decode_token
from app.db.client import get_database

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# user roles
class Roles(str, Enum):
    receptionist = "receptionist"
    nurse = "nurse"
    doctor = "doctor"
    admin = "admin"
    pharmacist = "pharmacist"
    billing = "billing"
    auditor = "auditor"


CLINICAL_ROLES = [
    Roles.doctor,
    Roles.nurse,
    Roles.pharmacist,
]

NURSING_ROLES = [
    Roles.nurse,
]

ADMIN_ROLES = [Roles.admin]


# pull the current user off the request JWT
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncDatabase = Depends(get_database),
):
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id in token",
        )

    user_doc = await db.users.find_one({"_id": obj_id})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    from app.models.user import UserInDB
    user_doc["id"] = str(user_doc["_id"])
    return UserInDB(**user_doc)


# gate a route to the given roles
def require_roles(*roles: Roles):
    async def dependency(
        current_user=Depends(get_current_user),
    ):
        if current_user.role not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


# clinical staff + admin
def require_any_clinical_role():
    return require_roles(*CLINICAL_ROLES, Roles.admin)


# nursing roles + admin
def require_any_nursing_role():
    return require_roles(*NURSING_ROLES, Roles.admin)


# admin only
def require_admin():
    return require_roles(Roles.admin)
