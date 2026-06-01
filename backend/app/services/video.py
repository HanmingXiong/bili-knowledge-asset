from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import requests
from yt_dlp import YoutubeDL

from app.config import get_settings
from app.services.bilibili import COMMON_HEADERS, resolve_playable_url

settings = get_settings()


def _is_valid_video(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False

    ffprobe_bin = shutil.which("ffprobe")
    if ffprobe_bin is None:
        return True

    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode == 0 and bool(result.stdout.strip())


def download_video(source_url: str, bvid: str, cid: int | None, asset_dir: Path) -> Path | None:
    mp4_path = asset_dir / "video.mp4"
    try:
        direct_url = resolve_playable_url(bvid, cid)
        if direct_url:
            with requests.get(
                direct_url,
                headers=COMMON_HEADERS,
                timeout=settings.http_timeout_seconds,
                stream=True,
            ) as response:
                response.raise_for_status()
                with mp4_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            if _is_valid_video(mp4_path):
                return mp4_path
            mp4_path.unlink(missing_ok=True)
    except Exception:
        mp4_path.unlink(missing_ok=True)

    try:
        ydl = YoutubeDL(
            {
                "outtmpl": str(asset_dir / "video.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
            }
        )
        ydl.download([source_url])
        for candidate in sorted(asset_dir.glob("video.*")):
            if candidate.name.startswith("video.") and candidate.is_file() and _is_valid_video(candidate):
                return candidate
    except Exception:
        return None
    return None


def extract_keyframes(video_path: Path, frames_dir: Path, duration: int | None) -> list[dict[str, float | str]]:
    if shutil.which(settings.ffmpeg_bin) is None:
        return []

    total_duration = max(duration or 0, 1)
    timestamps = list(range(0, total_duration, settings.frame_interval_seconds))[: settings.max_keyframes]
    if 0 not in timestamps:
        timestamps.insert(0, 0)
    timestamps = timestamps[: settings.max_keyframes]

    keyframes: list[dict[str, float | str]] = []
    for index, timestamp in enumerate(timestamps, start=1):
        output_path = frames_dir / f"frame_{index:03d}.jpg"
        command = [
            settings.ffmpeg_bin,
            "-y",
            "-ss",
            str(timestamp),
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]
        try:
            subprocess.run(command, capture_output=True, check=True)
        except Exception:
            continue
        if output_path.exists():
            keyframes.append({"timestamp": float(timestamp), "file_path": str(output_path)})
    return keyframes
