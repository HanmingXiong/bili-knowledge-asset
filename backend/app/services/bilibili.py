from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests

from app.config import get_settings

settings = get_settings()
COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


def parse_bvid(value: str) -> str:
    match = re.search(r"(BV[0-9A-Za-z]{10})", value)
    if match:
        return match.group(1)
    parsed = urlparse(value)
    if parsed.scheme == "" and value.startswith("BV"):
        return value
    raise ValueError("Could not parse a valid Bilibili BVID from the provided URL")


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(url, params=params, headers=COMMON_HEADERS, timeout=settings.http_timeout_seconds)
    response.raise_for_status()
    return response.json()


def fetch_metadata(bvid: str) -> dict[str, Any]:
    view_payload = _get_json("https://api.bilibili.com/x/web-interface/view", params={"bvid": bvid})
    data = view_payload.get("data") or {}
    if not data:
        raise ValueError("Bilibili metadata API returned no data")

    cid = None
    pages = data.get("pages") or []
    if pages:
        cid = pages[0].get("cid")

    tags: list[str] = []
    aid = data.get("aid")
    if aid:
        try:
            tag_payload = _get_json("https://api.bilibili.com/x/tag/archive/tags", params={"aid": aid})
            tags = [item.get("tag_name", "") for item in (tag_payload.get("data") or []) if item.get("tag_name")]
        except Exception:
            tags = []

    return {
        "bvid": bvid,
        "aid": aid,
        "cid": cid,
        "title": data.get("title"),
        "uploader": (data.get("owner") or {}).get("name"),
        "duration": data.get("duration"),
        "description": data.get("desc"),
        "source_url": f"https://www.bilibili.com/video/{bvid}",
        "tags": tags,
        "raw": data,
    }


def fetch_subtitle_chunks(bvid: str, cid: int | None) -> list[dict[str, Any]]:
    if not cid:
        return []

    payload = _get_json("https://api.bilibili.com/x/player/v2", params={"bvid": bvid, "cid": cid})
    subtitle_data = ((payload.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
    if not subtitle_data:
        return []

    subtitle_url = subtitle_data[0].get("subtitle_url") or subtitle_data[0].get("url")
    if not subtitle_url:
        return []
    if subtitle_url.startswith("//"):
        subtitle_url = f"https:{subtitle_url}"

    response = requests.get(subtitle_url, headers=COMMON_HEADERS, timeout=settings.http_timeout_seconds)
    response.raise_for_status()
    body = response.json().get("body") or []

    chunks: list[dict[str, Any]] = []
    for item in body:
        chunks.append(
            {
                "start_time": float(item.get("from", 0)),
                "end_time": float(item.get("to", 0)),
                "text": (item.get("content") or "").strip(),
            }
        )
    return [chunk for chunk in chunks if chunk["text"]]


def resolve_playable_url(bvid: str, cid: int | None) -> str | None:
    if not cid:
        return None

    payload = _get_json(
        "https://api.bilibili.com/x/player/playurl",
        params={
            "bvid": bvid,
            "cid": cid,
            "qn": 64,
            "fnval": 0,
            "fnver": 0,
            "platform": "html5",
        },
    )
    data = payload.get("data") or {}
    durl = data.get("durl") or []
    if durl:
        return durl[0].get("url")

    dash = data.get("dash") or {}
    videos = dash.get("video") or []
    if videos:
        return videos[0].get("baseUrl") or videos[0].get("base_url")
    return None
