import os
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "leave_management")


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    database: Optional[AsyncIOMotorDatabase] = None


mongodb = MongoDB()


async def connect_to_mongo() -> None:
    mongodb.client = AsyncIOMotorClient(MONGODB_URI)
    mongodb.database = mongodb.client[MONGODB_DB_NAME]

    await mongodb.database.users.create_index("email", unique=True)
    await mongodb.database.users.create_index("employee_id", unique=True)
    await mongodb.database.leave_quotas.create_index(
        [("user_id", 1), ("year", 1), ("leave_type", 1)],
        unique=True,
    )
    await mongodb.database.leave_requests.create_index("user_id")
    await mongodb.database.leave_requests.create_index("manager_id")
    await mongodb.database.leave_requests.create_index("status")
    await mongodb.database.audit_trails.create_index("entity_id")


async def close_mongo_connection() -> None:
    if mongodb.client:
        mongodb.client.close()


def get_database() -> AsyncIOMotorDatabase:
    if mongodb.database is None:
        raise RuntimeError("MongoDB connection has not been initialized")
    return mongodb.database
