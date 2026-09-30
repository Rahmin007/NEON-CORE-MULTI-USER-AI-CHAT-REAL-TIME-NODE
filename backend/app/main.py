"""FastAPI application: startup, CORS and routes."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import API_ROUTERS, health_router
from app.core.config import settings
from app.db import mongo
from app.services import store

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo.connect()
    await mongo.init_indexes()
    await store.ensure_admin(settings.ADMIN_USERNAME, settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD)
    yield
    await mongo.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="5.0.0",
    description="Real-time multi-user chat with an AI participant, role-based moderation and an audit log.",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
)

# The frontend sends a Bearer token (not cookies), so credentials are not needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

for router in API_ROUTERS:
    app.include_router(router, prefix="/api/v1")
app.include_router(health_router)


@app.get("/")
async def root():
    return {"service": settings.PROJECT_NAME, "status": "online", "health": "/health"}
