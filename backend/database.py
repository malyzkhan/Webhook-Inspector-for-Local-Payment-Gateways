import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

client: AsyncIOMotorClient | None = None
database: AsyncIOMotorDatabase | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global client, database

    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI must be set before starting the API")

    client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
    database = client[os.getenv("MONGODB_DATABASE", "webhook_saas")]
    try:
        await client.admin.command("ping")
        await database.webhooks.create_index(
            [("created_at", 1)],
            expireAfterSeconds=86_400,
            name="webhook_ttl",
        )
        await database.webhooks.create_index(
            [("endpoint_id", 1), ("created_at", -1)],
            name="endpoint_history",
        )
        yield
    finally:
        client.close()
        client = None
        database = None


def get_webhooks_collection():
    if database is None:
        raise RuntimeError("MongoDB has not been initialized")
    return database.webhooks
