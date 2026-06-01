from __future__ import annotations

import re
from collections import Counter
from typing import Any


def _tokenize(text: str) -> Counter[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return Counter(tokens)


def _score(text: str, query: str) -> int:
    doc_tokens = _tokenize(text)
    query_tokens = _tokenize(query)
    return sum(min(doc_tokens[token], count) for token, count in query_tokens.items())


def retrieve_relevant_snippets(asset_data_list: list[dict[str, Any]], query: str, limit: int = 8) -> list[str]:
    snippets: list[tuple[int, str]] = []
    for asset in asset_data_list:
        title = asset.get("title") or asset.get("bvid") or "Untitled asset"
        for chunk in asset.get("transcript_chunks") or []:
            snippet = f"[{title}] Transcript {chunk.get('start_time', 0):.0f}-{chunk.get('end_time', 0):.0f}s: {chunk.get('text', '')}"
            snippets.append((_score(snippet, query), snippet))
        for frame in asset.get("keyframes") or []:
            desc = frame.get("visual_description") or "No visual description available"
            snippet = f"[{title}] Frame {frame.get('timestamp', 0):.0f}s: {desc}"
            snippets.append((_score(snippet, query), snippet))
        notes = asset.get("structured_notes") or ""
        if notes:
            snippets.append((_score(notes, query), f"[{title}] Notes: {notes}"))

    ranked = sorted(snippets, key=lambda item: item[0], reverse=True)
    filtered = [snippet for score, snippet in ranked if score > 0]
    if not filtered:
        filtered = [snippet for _, snippet in ranked]
    return filtered[:limit]
