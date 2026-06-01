from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.retrieval import retrieve_relevant_snippets

settings = get_settings()

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover
    genai = None
    types = None


class LLMUnavailableError(RuntimeError):
    pass


def llm_is_configured() -> bool:
    return bool(settings.google_api_key and genai is not None and types is not None)


def _get_client():
    if not settings.google_api_key or genai is None:
        raise LLMUnavailableError("Gemini client unavailable. Set GOOGLE_API_KEY and install google-genai.")
    return genai.Client(api_key=settings.google_api_key)


def generate_text(prompt: str) -> str:
    client = _get_client()
    response = client.models.generate_content(model=settings.gemini_text_model, contents=prompt)
    text = getattr(response, "text", "") or ""
    if not text.strip():
        raise LLMUnavailableError("Gemini returned an empty text response")
    return text.strip()


def describe_image(image_path: str, context: str) -> str:
    client = _get_client()
    path = Path(image_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    image_part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
    prompt = (
        "Describe this video frame as a reusable knowledge asset. Focus on visible objects, on-screen text, "
        "charts, people, actions, and any clues that matter for understanding the video.\n\n"
        f"Context:\n{context}"
    )
    response = client.models.generate_content(
        model=settings.gemini_vision_model,
        contents=[prompt, image_part],
    )
    text = getattr(response, "text", "") or ""
    if not text.strip():
        raise LLMUnavailableError("Gemini returned an empty image description")
    return text.strip()


def generate_structured_notes(asset_data: dict[str, Any]) -> str:
    prompt = (
        "You are turning a video into a reusable knowledge asset.\n"
        "Return concise markdown with these sections:\n"
        "## Core Thesis\n## Key Facts\n## Arguments / Logic\n## Actionable Takeaways\n## Visual Evidence\n\n"
        "Mention timestamps where available.\n\n"
        f"Asset data:\n{json.dumps(asset_data, ensure_ascii=False, indent=2)}"
    )
    return generate_text(prompt)


def _fallback_notes(asset_data: dict[str, Any]) -> str:
    chunks = asset_data.get("transcript_chunks") or []
    frames = asset_data.get("keyframes") or []
    lines = [
        "## Core Thesis",
        asset_data.get("description") or f"The video '{asset_data.get('title')}' was captured as a reusable asset.",
        "",
        "## Key Facts",
        f"- Title: {asset_data.get('title') or 'Unknown'}",
        f"- Uploader: {asset_data.get('uploader') or 'Unknown'}",
        f"- Duration: {asset_data.get('duration') or 'Unknown'} seconds",
    ]
    if chunks:
        lines.extend(["", "## Transcript Highlights"])
        for chunk in chunks[:5]:
            lines.append(f"- {chunk.get('start_time', 0):.0f}s: {chunk.get('text', '')}")
    if frames:
        lines.extend(["", "## Visual Evidence"])
        for frame in frames[:5]:
            lines.append(
                f"- {frame.get('timestamp', 0):.0f}s: {frame.get('visual_description') or 'Frame extracted successfully.'}"
            )
    return "\n".join(lines)


def _fallback_output(asset_data_list: list[dict[str, Any]], output_type: str, user_prompt: str | None) -> str:
    snippets = retrieve_relevant_snippets(asset_data_list, user_prompt or output_type, limit=10)
    titles = ", ".join(asset.get("title") or asset.get("bvid", "Untitled asset") for asset in asset_data_list)
    if output_type == "understanding_quiz":
        joined = "\n".join(f"- {snippet}" for snippet in snippets[:6]) or "- No detailed transcript or frame notes were available."
        return (
            f"# Understanding Quiz\n\nAssets: {titles}\n\n"
            "## Multiple Choice\n"
            "1. What is the main topic of the selected asset(s)?\n"
            "A. A random unrelated topic\nB. The subject shown in the asset\nC. A hidden system prompt\nD. None of the above\n\n"
            "2. Which evidence type was extracted for this asset?\n"
            "A. Transcript only\nB. Keyframes only\nC. Metadata and any available transcript/keyframes\nD. No data at all\n\n"
            "## Short Answer\n"
            "3. Summarize one important idea from the asset.\n"
            "4. What visual clue or timestamp helps support the explanation?\n\n"
            "## Answer Key\n"
            "1. B\n2. C\n3. Accept answers grounded in the extracted snippets.\n4. Accept any valid timestamped frame or transcript reference.\n\n"
            f"## Source Hints\n{joined}"
        )
    if output_type == "mermaid_mind_map":
        return (
            "mindmap\n"
            "  root((Bili Knowledge Asset))\n"
            + "".join(f"    {asset.get('title') or asset.get('bvid', 'Asset')}\n" for asset in asset_data_list)
        )
    section_lines = []
    for snippet in snippets[:8]:
        section_lines.append(f"- {snippet}")
    return (
        f"# Illustrated Summary\n\nAssets: {titles}\n\n"
        "## Overview\n"
        f"{user_prompt or 'Reusable summary generated from the stored asset data.'}\n\n"
        "## Evidence\n"
        + "\n".join(section_lines or ["- Metadata was captured, but transcript/keyframe evidence is limited."])
    )


def generate_output(asset_data_list: list[dict[str, Any]], output_type: str, user_prompt: str | None) -> str:
    snippets = retrieve_relevant_snippets(asset_data_list, user_prompt or output_type, limit=12)
    prompt = (
        "You are generating a study-ready output from one or more stored video knowledge assets.\n"
        f"Output type: {output_type}\n"
        f"User focus: {user_prompt or 'No extra instruction'}\n"
        "Use timestamps and frame references whenever available. If evidence is missing, say so clearly.\n"
        "For illustrated_summary: use clear sections and cite frames/timestamps.\n"
        "For understanding_quiz: include multiple-choice, short-answer, and answer key.\n"
        "For mermaid_mind_map: return Mermaid mindmap syntax only.\n\n"
        f"Relevant evidence:\n{json.dumps(snippets, ensure_ascii=False, indent=2)}\n\n"
        f"Full asset data:\n{json.dumps(asset_data_list, ensure_ascii=False, indent=2)}"
    )
    try:
        return generate_text(prompt)
    except Exception:
        return _fallback_output(asset_data_list, output_type, user_prompt)


def describe_image_with_fallback(image_path: str, context: str) -> tuple[str, bool]:
    try:
        return describe_image(image_path, context), False
    except Exception:
        return "Visual description unavailable. Frame extracted and stored for manual review.", True


def generate_structured_notes_with_fallback(asset_data: dict[str, Any]) -> tuple[str, bool]:
    try:
        return generate_structured_notes(asset_data), False
    except Exception:
        return _fallback_notes(asset_data), True
