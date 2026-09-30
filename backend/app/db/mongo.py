"""MongoDB connection (PyMongo's official async driver) and index setup."""
from __future__ import annotations

import logging
from typing import Any

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Any = None
_db: Any = None


def connect() -> None:
    """Create the client once at startup.

    A `mongomock://` URI is only for automated tests and demos without a MongoDB
    server (it needs the dev dependency `mongomock-motor`)."""
    global _client, _db
    if settings.MONGODB_URI.startswith("mongomock://"):
        from mongomock_motor import AsyncMongoMockClient

        _client = AsyncMongoMockClient(tz_aware=True)
    else:
        _client = AsyncMongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=10_000, tz_aware=True)
    _db = _client[settings.MONGODB_DB_NAME]


def set_database(database: Any) -> None:
    """Used by tests to plug in an in-memory database."""
    global _db
    _db = database


async def close() -> None:
    if _client is not None and hasattr(_client, "close"):
        result = _client.close()
        if hasattr(result, "__await__"):
            await result


def get_db() -> Any:
    if _db is None:
        raise RuntimeError("Database is not connected")
    return _db


async def ping() -> bool:
    try:
        await get_db().command("ping")
        return True
    except Exception:  # noqa: BLE001 - a health check must never raise
        return False


async def init_indexes() -> None:
    db = get_db()
    await db.users.create_index([("username_lower", ASCENDING)], unique=True)
    await db.users.create_index([("email", ASCENDING)], unique=True)
    await db.messages.create_index([("created_at", DESCENDING)])
    await db.warnings.create_index([("user_id", ASCENDING), ("acknowledged_at", ASCENDING)])
    await db.activity_logs.create_index([("action", ASCENDING), ("created_at", DESCENDING)])
    if settings.LOG_RETENTION_DAYS > 0:
        # TTL index: MongoDB deletes old activity-log entries automatically.
        await db.activity_logs.create_index(
            [("created_at", ASCENDING)],
            expireAfterSeconds=settings.LOG_RETENTION_DAYS * 86400,
            name="created_at_ttl",
        )
    else:
        await db.activity_logs.create_index([("created_at", DESCENDING)])
    logger.info("MongoDB indexes ready")
