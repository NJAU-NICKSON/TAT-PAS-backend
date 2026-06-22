from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.asynchronous.database import AsyncDatabase
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.db.client import get_database
from app.models.user import ChangePasswordRequest, TokenResponse, UserInDB, UserUpdate
from app.security.jwt import decode_token
from app.security.rbac import get_current_user
from app.services.auth_service import authenticate_user, create_tokens, verify_password_for_user, AccountDeactivatedError
from app.services.user_service import update_user
from app.services.audit_service import create_security_audit
from app.services.activity_service import log_action

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])


# Authenticate and issue access + refresh tokens.
@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    db: AsyncDatabase = Depends(get_database),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    try:
        user = await authenticate_user(form_data.username, form_data.password, db)
    except AccountDeactivatedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account access is restricted. Please contact management for assistance.",
        )
    if not user:
        await create_security_audit(
            db=db,
            user_id="system",
            user_role="system",
            event_type="login_failure",
            details={"username": form_data.username, "reason": "invalid credentials"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    now = datetime.now(timezone.utc)
    await db.users.update_one(
        {"username": form_data.username},
        {"$set": {"last_login": now}},
    )
    user.last_login = now
    await log_action(
        db, action="login", user_id=user.id, user_role=user.role, user_name=user.full_name,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return create_tokens(user)


# Exchange a refresh token for a new access token.
@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh_token(
    request: Request,
    db: AsyncDatabase = Depends(get_database),
):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not a refresh token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id",
        )

    user_doc = await db.users.find_one({"_id": obj_id})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    user_doc["id"] = str(user_doc["_id"])
    user = UserInDB(**user_doc)
    return create_tokens(user)


# Invalidate the current session.
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    await log_action(
        db, action="logout", user_id=current_user.id, user_role=current_user.role,
        user_name=current_user.full_name,
        ip_address=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Change the logged-in user's password.
@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    if not await verify_password_for_user(current_user.id, body.current_password, db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    updated_user = await update_user(
        db,
        current_user.id,
        UserUpdate(password=body.new_password),
    )
    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
