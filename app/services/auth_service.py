from typing import Optional
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from app.models.user import UserInDB, UserResponse, TokenResponse
from app.security.passwords import verify_password
from app.security.jwt import create_access_token, create_refresh_token


# Raised when valid credentials belong to a deactivated account.
class AccountDeactivatedError(Exception):
    pass


async def authenticate_user(
    username: str, password: str, db: AsyncDatabase
) -> Optional[UserInDB]:
    user_doc = await db.users.find_one({"username": username})
    if not user_doc:
        return None
    if not verify_password(password, user_doc["password_hash"]):
        return None
    # Credentials are correct but the account is disabled: signal distinctly.
    if user_doc.get("is_active", True) is False:
        raise AccountDeactivatedError()
    user_doc["_id"] = str(user_doc["_id"])
    return UserInDB(**user_doc)


# Check a password against a specific user record.
async def verify_password_for_user(
    user_id: str, password: str, db: AsyncDatabase
) -> bool:
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return False

    user_doc = await db.users.find_one({"_id": obj_id})
    if not user_doc:
        return False

    return verify_password(password, user_doc["password_hash"])


# Issue access and refresh tokens for a user.
def create_tokens(user: UserInDB) -> TokenResponse:
    token_data = {"sub": user.id, "role": user.role, "department_id": user.department_id}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    user_response = UserResponse(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        last_login=user.last_login,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user_response,
    )
