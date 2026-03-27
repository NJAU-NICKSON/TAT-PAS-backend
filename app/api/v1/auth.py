from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.asynchronous.database import AsyncDatabase
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.db.client import get_database
from app.models.user import LoginRequest, TokenResponse, UserInDB
from app.security.jwt import decode_token, create_access_token, create_refresh_token
from app.security.rbac import get_current_user
from app.services.auth_service import authenticate_user, create_tokens
from app.services.audit_service import create_security_audit

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    db: AsyncDatabase = Depends(get_database),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        # Log security event
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
    return create_tokens(user)


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


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user=Depends(get_current_user),
):
    """
    Invalidate the current session.
    Clients must clear their local token storage on receipt of this response.
    Note: tokens remain cryptographically valid until expiry — for full revocation
    implement a server-side token blacklist.
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)