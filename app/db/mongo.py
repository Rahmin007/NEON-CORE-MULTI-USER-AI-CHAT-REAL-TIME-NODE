from pymongo import DESCENDING, MongoClient
from pymongo.collection import Collection

from app.core.config import settings

_client = MongoClient(settings.MONGODB_URI)
_db = _client[settings.MONGODB_DB_NAME]
activity_logs: Collection = _db["activity_logs"]


def init_mongo_indexes() -> None:
    activity_logs.create_index([("created_at", DESCENDING)])
