from __future__ import annotations

import shutil
import sqlite3

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.routers import assets, generation
from app.services.llm import llm_is_configured
from app.schemas import HealthResponse

settings = get_settings()
app = FastAPI(title="Bili Knowledge Asset API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    init_db()


app.mount("/media", StaticFiles(directory=settings.data_dir), name="media")
app.include_router(assets.router, prefix="/api/assets", tags=["assets"])
app.include_router(generation.router, prefix="/api", tags=["generation"])


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    database_ok = False
    try:
        with sqlite3.connect(settings.db_path) as connection:
            connection.execute("SELECT 1")
        database_ok = True
    except Exception:
        database_ok = False

    assets_directory_ok = settings.assets_dir.exists() and settings.assets_dir.is_dir()
    ffmpeg_ok = shutil.which(settings.ffmpeg_bin) is not None

    return HealthResponse(
        status="ok",
        database=database_ok,
        assets_directory=assets_directory_ok,
        ffmpeg=ffmpeg_ok,
        gemini_configured=llm_is_configured(),
    )
