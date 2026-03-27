from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from app.config import get_settings

_client: AsyncMongoClient | None = None


async def connect_db() -> None:
    global _client
    settings = get_settings()
    _client = AsyncMongoClient(settings.MONGO_URI)


async def close_db() -> None:
    global _client
    if _client is not None:
        await _client.close()   # FIXED: added await
        _client = None

async def get_database() -> AsyncDatabase:
    global _client
    settings = get_settings()
    if _client is None:
        _client = AsyncMongoClient(settings.MONGO_URI)
    return _client[settings.MONGO_DB]