from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


class Settings:
    def __init__(self) -> None:
        repo_root = REPO_ROOT
        self.repo_root = repo_root
        self.data_dir = Path(os.getenv("APP_DATA_DIR", repo_root / "data"))
        self.assets_dir = self.data_dir / "assets"
        self.db_path = Path(os.getenv("APP_DB_PATH", self.data_dir / "app.db"))
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self.gemini_text_model = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash").strip()
        self.gemini_vision_model = os.getenv("GEMINI_VISION_MODEL", self.gemini_text_model).strip()
        self.ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg").strip()
        self.frame_interval_seconds = int(os.getenv("FRAME_INTERVAL_SECONDS", "60"))
        self.max_keyframes = int(os.getenv("MAX_KEYFRAMES", "12"))
        self.http_timeout_seconds = int(os.getenv("HTTP_TIMEOUT_SECONDS", "25"))
        self.frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
