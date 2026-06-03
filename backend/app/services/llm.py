from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from app.config import get_settings

settings = get_settings()

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover
    genai = None
    types = None


class LLMUnavailableError(RuntimeError):
    pass


def _normalize_plain_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line or re.fullmatch(r"[-*_]{3,}", line):
            continue
        line = re.sub(r"^#{1,6}\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        line = re.sub(r"^[-*•]\s+", "", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        cleaned_lines.append(line)
    return re.sub(r"\s+", " ", " ".join(cleaned_lines)).strip()


def _truncate_text(text: str, max_chars: int, max_sentences: int) -> str:
    normalized = _normalize_plain_text(text)
    if not normalized:
        return ""
    sentence_parts = re.split(r"(?<=[.!?。！？])\s+", normalized)
    concise = " ".join(part.strip() for part in sentence_parts[:max_sentences] if part.strip()).strip() or normalized
    if len(concise) <= max_chars:
        return concise
    shortened = concise[: max_chars - 3].rstrip(" ,;:")
    cut_at = max(shortened.rfind(". "), shortened.rfind("! "), shortened.rfind("? "), shortened.rfind(" "))
    if cut_at >= max_chars // 2:
        shortened = shortened[:cut_at].rstrip(" ,;:")
    return f"{shortened}..."


def _sanitize_string_list(items: list[Any], *, max_chars: int, max_items: int) -> list[str]:
    sanitized: list[str] = []
    for item in items[:max_items]:
        if not isinstance(item, str):
            continue
        cleaned = _truncate_text(item, max_chars=max_chars, max_sentences=1)
        if cleaned:
            sanitized.append(cleaned)
    return sanitized


def _sanitize_structured_notes(payload: dict[str, Any]) -> dict[str, Any]:
    timeline_items: list[dict[str, Any]] = []
    for item in payload.get("timeline") or []:
        if not isinstance(item, dict):
            continue
        event = _truncate_text(str(item.get("event", "")), max_chars=140, max_sentences=1)
        if event:
            timeline_items.append({"timestamp": item.get("timestamp"), "event": event})

    return {
        "summary": _truncate_text(str(payload.get("summary", "")), max_chars=260, max_sentences=2),
        "facts": _sanitize_string_list(payload.get("facts") or [], max_chars=140, max_items=8),
        "opinions": _sanitize_string_list(payload.get("opinions") or [], max_chars=140, max_items=6),
        "arguments": _sanitize_string_list(payload.get("arguments") or [], max_chars=160, max_items=8),
        "timeline": timeline_items[:8],
        "concepts": _sanitize_string_list(payload.get("concepts") or [], max_chars=80, max_items=10),
        "causal_chains": _sanitize_string_list(payload.get("causal_chains") or [], max_chars=160, max_items=6),
        "visual_evidence": _sanitize_string_list(payload.get("visual_evidence") or [], max_chars=160, max_items=8),
    }


def _extract_json_payload(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise LLMUnavailableError("Gemini returned empty JSON content")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", stripped, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(1))


def _sanitize_transcript_chunks(payload: Any, duration: int | None) -> list[dict[str, Any]]:
    raw_chunks = payload.get("chunks") if isinstance(payload, dict) else payload
    if not isinstance(raw_chunks, list):
        return []

    sanitized: list[dict[str, Any]] = []
    chunk_count = max(len(raw_chunks), 1)
    inferred_chunk_size = max((duration or 120) / chunk_count, 8)

    for index, item in enumerate(raw_chunks):
        if not isinstance(item, dict):
            continue
        text = _truncate_text(str(item.get("text", "")), max_chars=320, max_sentences=4)
        if not text:
            continue
        start_time = item.get("start_time")
        end_time = item.get("end_time")

        try:
            start_value = float(start_time) if start_time is not None else float(index * inferred_chunk_size)
        except (TypeError, ValueError):
            start_value = float(index * inferred_chunk_size)
        try:
            end_value = float(end_time) if end_time is not None else start_value + inferred_chunk_size
        except (TypeError, ValueError):
            end_value = start_value + inferred_chunk_size

        if duration is not None:
            start_value = max(0.0, min(start_value, float(duration)))
            end_value = max(start_value + 1.0, min(end_value, float(duration)))
        elif end_value <= start_value:
            end_value = start_value + inferred_chunk_size

        sanitized.append(
            {
                "start_time": round(start_value, 2),
                "end_time": round(end_value, 2),
                "text": text,
            }
        )

    return sanitized


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
        "Describe this video frame as a reusable knowledge asset. Return 1-2 short plain sentences only, "
        "under 45 words total, with no bullets, headings, markdown, or filler. Focus on the main visible "
        "subjects, actions, and any on-screen text or context clues that matter.\n\n"
        f"Context:\n{context}"
    )
    response = client.models.generate_content(
        model=settings.gemini_vision_model,
        contents=[prompt, image_part],
    )
    text = getattr(response, "text", "") or ""
    if not text.strip():
        raise LLMUnavailableError("Gemini returned an empty image description")
    return _truncate_text(text, max_chars=220, max_sentences=2)


def generate_structured_notes(asset_data: dict[str, Any]) -> dict[str, Any]:
    prompt = (
        "You are turning a video into a reusable structured knowledge asset.\n"
        "Return valid JSON only using this schema:\n"
        "{"
        '"summary": string, '
        '"facts": string[], '
        '"opinions": string[], '
        '"arguments": string[], '
        '"timeline": [{"timestamp": number|null, "event": string}], '
        '"concepts": string[], '
        '"causal_chains": string[], '
        '"visual_evidence": string[]'
        "}\n"
        "Keep every string plain text and concise. No markdown, bullets, headings, or code fences inside values. "
        "Prefer one sentence per list item. Use timestamps when available.\n\n"
        f"Asset data:\n{json.dumps(asset_data, ensure_ascii=False, indent=2)}"
    )
    return _sanitize_structured_notes(json.loads(generate_text(prompt)))


def transcribe_audio(audio_path: str, duration: int | None = None) -> list[dict[str, Any]]:
    client = _get_client()
    path = Path(audio_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "audio/wav"
    audio_part = types.Part.from_bytes(data=path.read_bytes(), mime_type=mime_type)
    prompt = (
        "Transcribe the spoken content from this audio and return valid JSON only.\n"
        'Schema: {"chunks":[{"start_time": number, "end_time": number, "text": string}]}\n'
        "Use concise chunk text, keep chunk durations around 10 to 30 seconds when possible, "
        "and include approximate timestamps even if they are estimated. If there is no meaningful speech, return "
        '{"chunks":[]}. Do not include markdown fences or commentary.'
    )
    response = client.models.generate_content(
        model=settings.gemini_text_model,
        contents=[prompt, audio_part],
    )
    text = getattr(response, "text", "") or ""
    if not text.strip():
        raise LLMUnavailableError("Gemini returned an empty audio transcription")
    return _sanitize_transcript_chunks(_extract_json_payload(text), duration)


def _fallback_notes(asset_data: dict[str, Any]) -> dict[str, Any]:
    chunks = asset_data.get("transcript_chunks") or []
    frames = asset_data.get("keyframes") or []
    facts = [
        f"Title: {asset_data.get('title') or 'Unknown'}",
        f"Uploader: {asset_data.get('uploader') or 'Unknown'}",
        f"Duration: {asset_data.get('duration') or 'Unknown'} seconds",
    ]
    arguments = [chunk.get("text", "") for chunk in chunks[:5] if chunk.get("text")]
    timeline = [{"timestamp": chunk.get("start_time"), "event": chunk.get("text", "")} for chunk in chunks[:5] if chunk.get("text")]
    visual_evidence = [
        f"{frame.get('timestamp', 0):.0f}s: {_truncate_text(frame.get('visual_description') or 'Frame extracted successfully.', max_chars=120, max_sentences=1)}"
        for frame in frames[:5]
    ]
    return _sanitize_structured_notes(
        {
        "summary": asset_data.get("description") or f"The video '{asset_data.get('title')}' was stored as a reusable asset.",
        "facts": facts,
        "opinions": [],
        "arguments": arguments,
        "timeline": timeline,
        "concepts": asset_data.get("tags") or [],
        "causal_chains": [],
        "visual_evidence": visual_evidence,
        }
    )


def _fallback_output(
    asset_data_list: list[dict[str, Any]],
    output_type: str,
    user_prompt: str | None,
    evidence_snippets: list[dict[str, Any]],
) -> str:
    snippets = [
        (
            f"{snippet.get('source_type', 'snippet')} "
            f"{f'@ {snippet.get('timestamp', 0):.0f}s' if snippet.get('timestamp') is not None else ''}: "
            f"{snippet.get('text', '')}"
        ).strip()
        for snippet in evidence_snippets[:10]
    ]
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


def generate_output(
    asset_data_list: list[dict[str, Any]],
    output_type: str,
    user_prompt: str | None,
    evidence_snippets: list[dict[str, Any]],
) -> str:
    prompt = (
        "You are generating a study-ready output from one or more stored video knowledge assets.\n"
        f"Output type: {output_type}\n"
        f"User focus: {user_prompt or 'No extra instruction'}\n"
        "Use timestamps and frame references whenever available. If evidence is missing, say so clearly.\n"
        "For illustrated_summary: use clear sections and cite frames/timestamps.\n"
        "For understanding_quiz: include multiple-choice, short-answer, and answer key.\n"
        "For mermaid_mind_map: return Mermaid mindmap syntax only.\n\n"
        f"Relevant evidence:\n{json.dumps(evidence_snippets, ensure_ascii=False, indent=2)}\n\n"
        f"Full asset data:\n{json.dumps(asset_data_list, ensure_ascii=False, indent=2)}"
    )
    try:
        return generate_text(prompt)
    except Exception:
        return _fallback_output(asset_data_list, output_type, user_prompt, evidence_snippets)


def answer_asset_question(asset_data: dict[str, Any], question: str, evidence_snippets: list[dict[str, Any]]) -> str:
    prompt = (
        "Answer the user's question about a single stored video knowledge asset.\n"
        "Use only the provided evidence. If the evidence is incomplete, say that directly.\n"
        "Return a concise answer in plain text.\n\n"
        f"Question:\n{question}\n\n"
        f"Evidence:\n{json.dumps(evidence_snippets, ensure_ascii=False, indent=2)}\n\n"
        f"Asset data:\n{json.dumps(asset_data, ensure_ascii=False, indent=2)}"
    )
    try:
        return _truncate_text(generate_text(prompt), max_chars=600, max_sentences=5)
    except Exception:
        if not evidence_snippets:
            return "I could not find enough asset evidence to answer that question confidently."
        joined = " ".join(snippet.get("text", "") for snippet in evidence_snippets[:4]).strip()
        return joined or "I could not find enough asset evidence to answer that question confidently."


def answer_multi_asset_question(asset_data_list: list[dict[str, Any]], question: str, evidence_snippets: list[dict[str, Any]]) -> str:
    prompt = (
        "Answer the user's question across multiple stored video knowledge assets.\n"
        "Synthesize the provided evidence, call out disagreements or missing evidence, and stay concise.\n"
        "Return plain text only.\n\n"
        f"Question:\n{question}\n\n"
        f"Evidence:\n{json.dumps(evidence_snippets, ensure_ascii=False, indent=2)}\n\n"
        f"Asset data:\n{json.dumps(asset_data_list, ensure_ascii=False, indent=2)}"
    )
    try:
        return _truncate_text(generate_text(prompt), max_chars=700, max_sentences=6)
    except Exception:
        if not evidence_snippets:
            return "I could not find enough asset evidence across the selected assets to answer that question confidently."
        joined = " ".join(snippet.get("text", "") for snippet in evidence_snippets[:6]).strip()
        return joined or "I could not find enough asset evidence across the selected assets to answer that question confidently."


def describe_image_with_fallback(image_path: str, context: str) -> tuple[str, bool]:
    try:
        return describe_image(image_path, context), False
    except Exception:
        return "Frame extracted; Gemini description unavailable.", True


def generate_structured_notes_with_fallback(asset_data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    try:
        return generate_structured_notes(asset_data), False
    except Exception:
        return _sanitize_structured_notes(_fallback_notes(asset_data)), True


def transcribe_audio_with_fallback(audio_path: str, duration: int | None = None) -> tuple[list[dict[str, Any]], bool]:
    try:
        return transcribe_audio(audio_path, duration=duration), False
    except Exception:
        return [], True
