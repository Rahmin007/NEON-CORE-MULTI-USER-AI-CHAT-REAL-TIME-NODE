"""All MongoDB reads and writes live here, so routes never touch collections directly.

Collections:
  users          {username, username_lower, email, hashed_password, role, is_active, muted_until, created_at}
  messages       {user_id, username, sender_role, message, created_at}
  activity_logs  {user_id, username, action, details, ip_address, created_at}
  warnings       {user_id, from_username, reason, created_at, acknowledged_at}
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from app.core.security import hash_password
from app.db.mongo import get_db
from app.schemas.models import Role

logger = logging.getLogger(__name__)


class AlreadyExists(Exception):
    """Username or email is already registered."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def to_object_id(value: str | None) -> ObjectId | None:
    try:
        return ObjectId(value) if value else None
    except (InvalidId, TypeError):
        return None


# ---------------------------------------------------------------- users
def user_out(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "username": doc["username"],
        "email": doc["email"],
        "role": doc["role"],
        "is_active": doc.get("is_active", True),
        "muted_until": as_utc(doc.get("muted_until")),
        "created_at": as_utc(doc["created_at"]),
    }


async def get_user(user_id: str | None) -> dict | None:
    oid = to_object_id(user_id)
    return await get_db().users.find_one({"_id": oid}) if oid else None


async def get_user_by_username(username: str) -> dict | None:
    return await get_db().users.find_one({"username_lower": username.strip().lower()})


async def create_user(username: str, email: str, password: str, role: str = Role.USER.value) -> dict:
    doc = {
        "username": username.strip(),
        "username_lower": username.strip().lower(),
        "email": email.strip().lower(),
        "hashed_password": hash_password(password),
        "role": role,
        "is_active": True,
        "muted_until": None,
        "created_at": utcnow(),
    }
    users = get_db().users
    # Check first for a friendly error; the unique indexes still guard against races.
    if await users.find_one({"$or": [{"username_lower": doc["username_lower"]}, {"email": doc["email"]}]}):
        raise AlreadyExists
    try:
        result = await users.insert_one(doc)
    except DuplicateKeyError as exc:
        raise AlreadyExists from exc
    doc["_id"] = result.inserted_id
    return doc


async def list_users(search: str = "") -> list[dict]:
    query: dict[str, Any] = {}
    if search:
        query = {"$or": [{"username_lower": {"$regex": _escape(search.lower())}}, {"email": {"$regex": _escape(search.lower())}}]}
    return await get_db().users.find(query).sort("created_at", 1).to_list(length=1000)


async def update_user(user_id: str, changes: dict) -> dict | None:
    oid = to_object_id(user_id)
    if not oid:
        return None
    await get_db().users.update_one({"_id": oid}, {"$set": changes})
    return await get_db().users.find_one({"_id": oid})


async def count_users(query: dict | None = None) -> int:
    return await get_db().users.count_documents(query or {})


async def ensure_admin(username: str, email: str, password: str) -> None:
    """Create the first admin from environment variables, if it doesn't exist yet."""
    if not (username and email and password):
        return
    if await get_user_by_username(username):
        return
    try:
        await create_user(username, email, password, Role.ADMIN.value)
        logger.info("Created admin account '%s'", username)
    except AlreadyExists:
        logger.warning("Admin bootstrap skipped: email '%s' is already used by another account", email)


def _escape(text: str) -> str:
    import re

    return re.escape(text)


# ---------------------------------------------------------------- messages
def message_out(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]) if doc.get("user_id") else None,
        "username": doc.get("username") or "UNKNOWN",
        "sender_role": doc["sender_role"],
        "message": doc["message"],
        "created_at": as_utc(doc["created_at"]),
    }


async def create_message(user: dict | None, sender_role: str, text: str) -> dict:
    doc = {
        "user_id": user["_id"] if user else None,
        # Username is stored on the message so history loads without a join.
        "username": "AI CORE" if sender_role == Role.AI.value else user["username"],
        "sender_role": sender_role,
        "message": text,
        "created_at": utcnow(),
    }
    result = await get_db().messages.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def message_history(limit: int = 50, before: str | None = None) -> list[dict]:
    """Newest `limit` messages (optionally older than message id `before`), returned oldest first."""
    query: dict[str, Any] = {}
    before_oid = to_object_id(before)
    if before_oid:
        anchor = await get_db().messages.find_one({"_id": before_oid})
        if anchor:
            query = {"created_at": {"$lt": anchor["created_at"]}}
    rows = await get_db().messages.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
    return list(reversed(rows))


async def delete_message(message_id: str) -> bool:
    oid = to_object_id(message_id)
    if not oid:
        return False
    result = await get_db().messages.delete_one({"_id": oid})
    return result.deleted_count == 1


async def count_messages() -> int:
    return await get_db().messages.count_documents({})


# ---------------------------------------------------------------- activity log
async def log_activity(
    user: dict | None,
    action: str,
    details: dict | str | None = None,
    ip_address: str | None = None,
    username: str | None = None,
) -> None:
    """Write an audit event. Never raises: logging must not break the request."""
    try:
        await get_db().activity_logs.insert_one(
            {
                "user_id": str(user["_id"]) if user else None,
                "username": user["username"] if user else username,
                "action": action,
                "details": details,
                "ip_address": ip_address,
                "created_at": utcnow(),
            }
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to write activity log for action=%s", action)


def activity_out(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]) if doc.get("user_id") is not None else None,
        "username": doc.get("username"),
        "action": doc["action"],
        "details": doc.get("details"),
        "ip_address": doc.get("ip_address"),
        "created_at": as_utc(doc["created_at"]),
    }


async def list_activity(limit: int = 100, action: str | None = None, before: str | None = None) -> list[dict]:
    query: dict[str, Any] = {}
    if action:
        query["action"] = action
    before_oid = to_object_id(before)
    if before_oid:
        anchor = await get_db().activity_logs.find_one({"_id": before_oid})
        if anchor:
            query["created_at"] = {"$lt": anchor["created_at"]}
    return await get_db().activity_logs.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)


# ---------------------------------------------------------------- warnings
def warning_out(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "from_username": doc["from_username"],
        "reason": doc["reason"],
        "created_at": as_utc(doc["created_at"]).isoformat(),
    }


async def create_warning(target: dict, actor: dict, reason: str) -> dict:
    doc = {
        "user_id": target["_id"],
        "from_username": actor["username"],
        "reason": reason,
        "created_at": utcnow(),
        "acknowledged_at": None,
    }
    result = await get_db().warnings.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def unacknowledged_warnings(user_id: str) -> list[dict]:
    oid = to_object_id(user_id)
    if not oid:
        return []
    query = {"user_id": oid, "acknowledged_at": None}
    return await get_db().warnings.find(query).sort("created_at", 1).to_list(length=20)


async def acknowledge_warning(user_id: str, warning_id: str) -> bool:
    oid, wid = to_object_id(user_id), to_object_id(warning_id)
    if not (oid and wid):
        return False
    result = await get_db().warnings.update_one(
        {"_id": wid, "user_id": oid, "acknowledged_at": None}, {"$set": {"acknowledged_at": utcnow()}}
    )
    return result.modified_count == 1
