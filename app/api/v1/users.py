from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from app.services.activity_service import log_action
from pymongo.asynchronous.database import AsyncDatabase
from app.db.client import get_database
from app.models.user import UserCreate, UserResponse, UserUpdate
from app.security.rbac import Roles, get_current_user, require_roles
from app.services.user_service import (
    create_user,
    get_user_by_id,
    get_users,
    update_user,
    set_user_active,
)

router = APIRouter(prefix="/users", tags=["users"])


# List users. Admins see everyone; other staff may list clinical staff
@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    role: str | None = Query(None, description="Filter by role, e.g. 'doctor' or 'nurse'"),
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    if current_user.role != Roles.admin.value and role not in ("doctor", "nurse"):
        raise HTTPException(
            status_code=403,
            detail="Only admins may list all users. Specify role=doctor or role=nurse.",
        )
    return await get_users(db, skip=skip, limit=limit, role=role)


# Create a staff account.
@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    request: Request,
    body: UserCreate,
    current_user=Depends(require_roles(Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    existing = await db.users.find_one(
        {"$or": [{"username": body.username}, {"email": body.email}]}
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )
    user = await create_user(db, body)
    await log_action(
        db, action="staff_account_created", user_id=current_user.id, user_role=current_user.role,
        user_name=getattr(current_user, "full_name", None), entity_type="user", entity_id=str(getattr(user, "id", "")),
        detail=f"{body.username} ({body.role})",
        ip_address=request.client.host if request.client else None,
    )
    return user


# Fetch one user by ID.
@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user=Depends(get_current_user),
    db: AsyncDatabase = Depends(get_database),
):
    if current_user.role != Roles.admin.value and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    from app.models.user import UserResponse as UR
    return UR(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        last_login=user.last_login,
    )

# Update a user's details.
@router.patch("/{user_id}", response_model=UserResponse)
async def update_existing_user(
    user_id: str,
    body: UserUpdate,
    current_user=Depends(require_roles(Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    updated = await update_user(db, user_id, body)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return updated


# Deactivate (soft-delete) a user. Blocks login but preserves the record
@router.delete("/{user_id}", response_model=UserResponse)
async def deactivate_user(
    request: Request,
    user_id: str,
    current_user=Depends(require_roles(Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )
    updated = await set_user_active(db, user_id, is_active=False)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    await log_action(
        db, action="staff_account_deactivated", user_id=current_user.id, user_role=current_user.role,
        user_name=getattr(current_user, "full_name", None), entity_type="user", entity_id=user_id,
        detail=f"Deactivated {getattr(updated, 'username', user_id)}",
        ip_address=request.client.host if request.client else None,
    )
    return updated


# Restore a previously deactivated user.
@router.post("/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_user(
    user_id: str,
    current_user=Depends(require_roles(Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    updated = await set_user_active(db, user_id, is_active=True)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return updated
