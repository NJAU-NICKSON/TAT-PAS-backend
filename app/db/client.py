import certifi
from datetime import timezone
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from app.config import get_settings

_client: AsyncMongoClient | None = None


# certifi CA bundle, otherwise Atlas TLS handshakes fail
def _build_client(uri: str) -> AsyncMongoClient:
    # tz_aware keeps datetimes UTC instead of being read back as local
    kwargs = {"serverSelectionTimeoutMS": 30000, "tz_aware": True, "tzinfo": timezone.utc}
    if "mongodb+srv://" in uri or "mongodb.net" in uri:
        kwargs["tlsCAFile"] = certifi.where()
    return AsyncMongoClient(uri, **kwargs)


async def connect_db() -> None:
    global _client
    settings = get_settings()
    _client = _build_client(settings.MONGO_URI)


async def close_db() -> None:
    global _client
    if _client is not None:
        await _client.close()   
        _client = None

async def get_database() -> AsyncDatabase:
    global _client
    settings = get_settings()
    if _client is None:
        _client = _build_client(settings.MONGO_URI)
    return _client[settings.MONGO_DB]