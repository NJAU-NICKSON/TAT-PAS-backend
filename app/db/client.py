import certifi
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from app.config import get_settings

_client: AsyncMongoClient | None = None


# Build a client that validates Atlas TLS with certifi's CA bundle to avoid SSL handshake failures.
def _build_client(uri: str) -> AsyncMongoClient:
    kwargs = {"serverSelectionTimeoutMS": 30000}
    if "mongodb+srv://" in uri or "mongodb.net" in uri:
        kwargs["tlsCAFile"] = certifi.where()
    return AsyncMongoClient(uri, **kwargs)


# Open the MongoDB connection on startup.
async def connect_db() -> None:
    global _client
    settings = get_settings()
    _client = _build_client(settings.MONGO_URI)


# Close the MongoDB connection on shutdown.
async def close_db() -> None:
    global _client
    if _client is not None:
        await _client.close()   
        _client = None

# Return the active database handle for request handlers.
async def get_database() -> AsyncDatabase:
    global _client
    settings = get_settings()
    if _client is None:
        _client = _build_client(settings.MONGO_URI)
    return _client[settings.MONGO_DB]