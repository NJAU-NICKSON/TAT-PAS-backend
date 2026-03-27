from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.asynchronous.database import AsyncDatabase
from app.db.client import get_database
from app.models.user import UserCreate, UserResponse, UserUpdate
from app.security.rbac import Roles, get_current_user, require_roles
from app.services.user_service import (
    create_user,
    get_user_by_id,
    get_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(require_roles(Roles.admin)),
    db: AsyncDatabase = Depends(get_database),
):
    return await get_users(db, skip=skip, limit=limit)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(
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
    return await create_user(db, body)


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
