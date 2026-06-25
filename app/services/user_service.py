from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from app.models.user import UserCreate, UserInDB, UserResponse, UserUpdate
from app.security.passwords import hash_password


def _doc_to_user_response(doc: dict) -> UserResponse:
    return UserResponse(
        id=str(doc["_id"]),
        username=doc["username"],
        full_name=doc["full_name"],
        email=doc["email"],
        role=doc["role"],
        is_active=doc.get("is_active", True),
        created_at=doc["created_at"],
        last_login=doc.get("last_login"),
    )


def _doc_to_user_in_db(doc: dict) -> UserInDB:
    doc["id"] = str(doc["_id"])
    return UserInDB(**doc)


async def get_users(
    db: AsyncDatabase, skip: int = 0, limit: int = 20, role: Optional[str] = None
) -> list[UserResponse]:
    query: dict = {}
    if role:
        query["role"] = role
    cursor = db.users.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_doc_to_user_response(doc) for doc in docs]


async def get_user_by_id(
    db: AsyncDatabase, user_id: str
) -> Optional[UserInDB]:
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return None
    doc = await db.users.find_one({"_id": obj_id})
    if not doc:
        return None
    return _doc_to_user_in_db(doc)


async def get_user_by_username(
    db: AsyncDatabase, username: str
) -> Optional[UserInDB]:
    doc = await db.users.find_one({"username": username})
    if not doc:
        return None
    return _doc_to_user_in_db(doc)


async def create_user(
    db: AsyncDatabase, user_create: UserCreate
) -> UserResponse:
    now = datetime.now(timezone.utc)
    doc = {
        "username": user_create.username,
        "full_name": user_create.full_name,
        "email": user_create.email,
        "role": user_create.role,
        "password_hash": hash_password(user_create.password),
        "is_active": True,
        "created_at": now,
        "last_login": None,
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_user_response(doc)


async def update_user(
    db: AsyncDatabase, user_id: str, update: UserUpdate
) -> Optional[UserResponse]:
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return None

    update_fields: dict = {}
    if update.full_name is not None:
        update_fields["full_name"] = update.full_name
    if update.email is not None:
        update_fields["email"] = update.email
    if update.role is not None:
        update_fields["role"] = update.role
    if update.password is not None:
        update_fields["password_hash"] = hash_password(update.password)

    if not update_fields:
        doc = await db.users.find_one({"_id": obj_id})
        if not doc:
            return None
        return _doc_to_user_response(doc)

    result = await db.users.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_fields},
        return_document=True,
    )
    if not result:
        return None
    return _doc_to_user_response(result)


# soft delete: just flips is_active
async def set_user_active(
    db: AsyncDatabase, user_id: str, is_active: bool
) -> Optional[UserResponse]:
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        return None
    result = await db.users.find_one_and_update(
        {"_id": obj_id},
        {"$set": {"is_active": is_active}},
        return_document=True,
    )
    if not result:
        return None
    return _doc_to_user_response(result)
