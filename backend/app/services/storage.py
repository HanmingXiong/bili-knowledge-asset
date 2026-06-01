from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings

settings = get_settings()


def ensure_asset_dirs(bvid: str) -> tuple[Path, Path]:
    asset_dir = settings.assets_dir / bvid
    frames_dir = asset_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    return asset_dir, frames_dir


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def asset_bundle_paths(bvid: str) -> dict[str, Path]:
    asset_dir, frames_dir = ensure_asset_dirs(bvid)
    return {
        "asset_dir": asset_dir,
        "frames_dir": frames_dir,
        "metadata": asset_dir / "metadata.json",
        "transcript": asset_dir / "transcript.json",
        "visual_descriptions": asset_dir / "visual_descriptions.json",
        "structured_notes": asset_dir / "structured_notes.json",
        "video": asset_dir / "video.mp4",
        "audio": asset_dir / "audio.wav",
    }


def to_media_path(path: Path) -> str:
    relative = path.relative_to(settings.data_dir).as_posix()
    return f"/media/{relative}"
