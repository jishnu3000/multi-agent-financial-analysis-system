"""
MongoDB client and collection references.

Import ``users_collection`` and ``history_collection`` anywhere
database access is needed.
"""

from pymongo import MongoClient
from core.config import settings

mongo_client: MongoClient = MongoClient(settings.MONGODB_URL)

_db = mongo_client.stock_analysis_db
users_collection = _db["users"]
history_collection = _db["history"]
