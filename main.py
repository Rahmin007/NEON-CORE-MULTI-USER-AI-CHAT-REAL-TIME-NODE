from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.v1 import activity_logs, admin, auth, chat, users
from app.core.config import settings
from app.db.mongo import init_mongo_indexes
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_mongo_indexes()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="4.0.0",
    description="Real-time multi-user chat with AI participant, authentication, RBAC and moderation.",
    lifespan=lifespan,
)

origins = [x.strip() for x in settings.ALLOW_ORIGINS.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(activity_logs.router, prefix="/api/v1")


@app.get("/")
def root():
    return FileResponse(Path(__file__).resolve().parent / "static" / "index.html")


@app.get("/api-info")
def api_info():
    return {"status": "online", "service": settings.PROJECT_NAME, "version": "3.1.0"}


@app.get("/health")
def health():
    return {"status": "healthy", "database": "initialized"}
