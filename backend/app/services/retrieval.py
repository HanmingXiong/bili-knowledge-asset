from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def _tokenize(text_value: str) -> Counter[str]:
    tokens = re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", text_value.lower())
    return Counter(tokens)


def _score(text_value: str, query: str) -> int:
    doc_tokens = _tokenize(text_value)
    query_tokens = _tokenize(query)
    return sum(min(doc_tokens[token], count) for token, count in query_tokens.items())


def _fts_query(query: str) -> str:
    tokens = [token for token in re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", query) if token]
    if not tokens:
        return ""
    return " OR ".join(f'"{token}"' for token in tokens[:10])


def _serialize_snippet_row(row: Any) -> dict[str, Any]:
    metadata_json = row.metadata_json or "{}"
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": row.id,
        "asset_id": row.asset_id,
        "source_type": row.source_type,
        "timestamp": row.timestamp,
        "text": row.text,
        "metadata_json": metadata,
    }


def _fallback_asset_snippets(asset_data_list: list[dict[str, Any]], query: str, limit: int = 8) -> list[dict[str, Any]]:
    snippets: list[tuple[int, dict[str, Any]]] = []
    for asset in asset_data_list:
        asset_id = asset.get("id")
        title = asset.get("title") or asset.get("bvid") or "Untitled asset"
        metadata_text = ". ".join(
            part
            for part in [
                title,
                asset.get("description") or "",
                f"Uploader: {asset.get('uploader')}" if asset.get("uploader") else "",
            ]
            if part
        ).strip()
        if metadata_text:
            snippets.append(
                (
                    _score(metadata_text, query),
                    {
                        "asset_id": asset_id,
                        "source_type": "metadata",
                        "timestamp": None,
                        "text": metadata_text,
                        "metadata_json": {"title": title},
                    },
                )
            )
        for chunk in asset.get("transcript_chunks") or []:
            snippet = {
                "asset_id": asset_id,
                "source_type": "transcript",
                "timestamp": chunk.get("start_time"),
                "text": chunk.get("text", ""),
                "metadata_json": {"title": title},
            }
            snippets.append((_score(snippet["text"], query), snippet))
        for frame in asset.get("keyframes") or []:
            snippet = {
                "asset_id": asset_id,
                "source_type": "visual_description",
                "timestamp": frame.get("timestamp"),
                "text": frame.get("visual_description") or "Frame extracted successfully.",
                "metadata_json": {"title": title},
            }
            snippets.append((_score(snippet["text"], query), snippet))

        knowledge = asset.get("structured_knowledge") or {}
        all_structured = [knowledge.get("summary", "")]
        for key in ("facts", "opinions", "arguments", "concepts", "causal_chains", "visual_evidence"):
            all_structured.extend(knowledge.get(key) or [])
        for item in knowledge.get("timeline") or []:
            if isinstance(item, dict):
                all_structured.append(item.get("event", ""))
        for item in all_structured:
            if item:
                snippets.append(
                    (
                        _score(item, query),
                        {
                            "asset_id": asset_id,
                            "source_type": "structured_knowledge",
                            "timestamp": None,
                            "text": item,
                            "metadata_json": {"title": title},
                        },
                    )
                )

    ranked = sorted(snippets, key=lambda item: item[0], reverse=True)
    filtered = [snippet for score, snippet in ranked if score > 0]
    if not filtered:
        filtered = [snippet for _, snippet in ranked]
    return filtered[:limit]


def retrieve_relevant_snippets(
    db: Session,
    asset_ids: list[int],
    asset_data_list: list[dict[str, Any]],
    query: str,
    limit: int = 8,
) -> list[dict[str, Any]]:
    if not asset_ids:
        return []

    fts_query = _fts_query(query)
    if fts_query:
        placeholders = ", ".join(f":asset_id_{index}" for index, _ in enumerate(asset_ids))
        params = {f"asset_id_{index}": asset_id for index, asset_id in enumerate(asset_ids)}
        params["fts_query"] = fts_query
        params["limit"] = limit
        statement = text(
            f"""
            SELECT s.id, s.asset_id, s.source_type, s.timestamp, s.text, s.metadata_json
            FROM asset_snippets_fts fts
            JOIN asset_snippets s ON s.id = fts.rowid
            WHERE fts.text MATCH :fts_query
              AND s.asset_id IN ({placeholders})
            ORDER BY bm25(asset_snippets_fts), s.timestamp
            LIMIT :limit
            """
        )
        rows = db.execute(statement, params).fetchall()
        if rows:
            return [_serialize_snippet_row(row) for row in rows]

    return _fallback_asset_snippets(asset_data_list, query, limit=limit)
