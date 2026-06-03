from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Asset, AssetSnippet, GeneratedOutput, Keyframe, TranscriptChunk
from app.schemas import (
    AssetDetailResponse,
    AssetQueryResponse,
    AssetRetryResponse,
    AssetSnippetResponse,
    AssetSummaryResponse,
    GeneratedOutputResponse,
    KeyframeResponse,
    StructuredKnowledge,
)
from app.services.bilibili import fetch_metadata, fetch_subtitle_chunks, parse_bvid
from app.services.llm import (
    answer_multi_asset_question,
    answer_asset_question,
    describe_image_with_fallback,
    generate_output,
    generate_structured_notes_with_fallback,
    llm_is_configured,
    transcribe_audio_with_fallback,
)
from app.services.retrieval import retrieve_relevant_snippets
from app.services.storage import asset_bundle_paths, load_json, save_json, to_media_path
from app.services.video import download_video, extract_audio_track, extract_keyframes

TERMINAL_STATUSES = {"ready", "partial_ready", "failed"}
RETRY_STAGES = {"transcript", "keyframes", "vision", "notes", "all"}


def _set_status(asset: Asset, status: str, db: Session, error_message: str | None = None) -> None:
    asset.status = status
    asset.updated_at = datetime.utcnow()
    if error_message is not None:
        asset.error_message = error_message
    db.add(asset)
    db.commit()
    db.refresh(asset)


def list_assets(db: Session) -> list[Asset]:
    return db.query(Asset).order_by(desc(Asset.created_at)).all()


def get_asset_by_id(asset_id: int, db: Session) -> Asset | None:
    return db.query(Asset).filter(Asset.id == asset_id).first()


def _metadata_payload(asset: Asset) -> dict[str, Any]:
    return load_json(asset_bundle_paths(asset.bvid)["metadata"], {})


def _asset_tags(asset: Asset) -> list[str]:
    return _metadata_payload(asset).get("tags") or []


def _asset_visual_descriptions(asset: Asset) -> list[dict[str, Any]]:
    return load_json(asset_bundle_paths(asset.bvid)["visual_descriptions"], [])


def _transcript_payload(asset: Asset) -> dict[str, Any]:
    payload = load_json(asset_bundle_paths(asset.bvid)["transcript"], {})
    if isinstance(payload, list):
        return {"source": "subtitles", "chunks": payload}
    if isinstance(payload, dict):
        chunks = payload.get("chunks")
        if isinstance(chunks, list):
            return payload
    return {}


def _transcript_source(asset: Asset) -> str | None:
    payload = _transcript_payload(asset)
    source = payload.get("source")
    return source if isinstance(source, str) and source else None


def _asset_structured_knowledge(asset: Asset) -> dict[str, Any]:
    payload = load_json(asset_bundle_paths(asset.bvid)["structured_notes"], {})
    if not payload:
        return StructuredKnowledge().model_dump()
    try:
        return StructuredKnowledge.model_validate(payload).model_dump()
    except Exception:
        return StructuredKnowledge().model_dump()


def _generated_outputs_for_asset(asset_id: int, db: Session) -> list[GeneratedOutput]:
    outputs = db.query(GeneratedOutput).order_by(desc(GeneratedOutput.created_at)).all()
    matched: list[GeneratedOutput] = []
    for output in outputs:
        try:
            asset_ids = json.loads(output.asset_ids)
        except json.JSONDecodeError:
            continue
        if asset_id in asset_ids:
            matched.append(output)
    return matched


def serialize_generated_output(output: GeneratedOutput) -> GeneratedOutputResponse:
    return GeneratedOutputResponse(
        id=output.id,
        asset_ids=json.loads(output.asset_ids),
        output_type=output.output_type,
        user_prompt=output.user_prompt,
        content=output.content,
        created_at=output.created_at,
    )


def serialize_asset_summary(asset: Asset) -> AssetSummaryResponse:
    return AssetSummaryResponse.model_validate(asset)


def _serialize_snippet(snippet: AssetSnippet) -> AssetSnippetResponse:
    try:
        metadata_json = json.loads(snippet.metadata_json or "{}")
    except json.JSONDecodeError:
        metadata_json = {}
    return AssetSnippetResponse(
        id=snippet.id,
        source_type=snippet.source_type,
        timestamp=snippet.timestamp,
        text=snippet.text,
        metadata_json=metadata_json,
    )


def serialize_asset_detail(asset: Asset, db: Session) -> AssetDetailResponse:
    keyframes = [
        KeyframeResponse(
            id=frame.id,
            timestamp=frame.timestamp,
            file_path=frame.file_path,
            file_url=to_media_path(Path(frame.file_path)),
            visual_description=frame.visual_description,
        )
        for frame in sorted(asset.keyframes, key=lambda row: row.timestamp)
    ]
    transcript_source = _transcript_source(asset)
    transcript_status = transcript_source or ("available" if asset.transcript_chunks else "transcript unavailable")
    snippets = [_serialize_snippet(snippet) for snippet in sorted(asset.snippets, key=lambda row: (row.timestamp or -1, row.id))]
    return AssetDetailResponse(
        **serialize_asset_summary(asset).model_dump(),
        description=asset.description,
        tags=_asset_tags(asset),
        transcript_status=transcript_status,
        transcript_source=transcript_source,
        transcript_chunks=asset.transcript_chunks,
        keyframes=keyframes,
        generated_outputs=[serialize_generated_output(output) for output in _generated_outputs_for_asset(asset.id, db)],
        structured_knowledge=StructuredKnowledge.model_validate(_asset_structured_knowledge(asset)),
        snippets=snippets,
        visual_descriptions=_asset_visual_descriptions(asset),
    )


def _build_asset_payload(asset: Asset) -> dict[str, Any]:
    metadata = _metadata_payload(asset)
    return {
        "id": asset.id,
        "bvid": asset.bvid,
        "aid": asset.aid,
        "cid": asset.cid,
        "title": asset.title,
        "uploader": asset.uploader,
        "description": asset.description,
        "duration": asset.duration,
        "source_url": asset.source_url,
        "status": asset.status,
        "tags": metadata.get("tags") or [],
        "transcript_chunks": [
            {"start_time": chunk.start_time, "end_time": chunk.end_time, "text": chunk.text}
            for chunk in sorted(asset.transcript_chunks, key=lambda row: row.start_time)
        ],
        "keyframes": [
            {
                "timestamp": frame.timestamp,
                "file_path": frame.file_path,
                "visual_description": frame.visual_description,
            }
            for frame in sorted(asset.keyframes, key=lambda row: row.timestamp)
        ],
        "structured_knowledge": _asset_structured_knowledge(asset),
    }


def _clear_transcript(asset: Asset, db: Session) -> None:
    for chunk in list(asset.transcript_chunks):
        db.delete(chunk)
    db.commit()
    db.refresh(asset)
    transcript_path = asset_bundle_paths(asset.bvid)["transcript"]
    if transcript_path.exists():
        transcript_path.unlink()


def _store_transcript_chunks(asset: Asset, db: Session, transcript_chunks: list[dict[str, Any]], source: str) -> None:
    save_json(asset_bundle_paths(asset.bvid)["transcript"], {"source": source, "chunks": transcript_chunks})
    for chunk in transcript_chunks:
        db.add(
            TranscriptChunk(
                asset_id=asset.id,
                start_time=chunk["start_time"],
                end_time=chunk["end_time"],
                text=chunk["text"],
            )
        )
    db.commit()
    db.refresh(asset)


def _extract_transcript_with_gemini_asr(asset: Asset, db: Session) -> str | None:
    bundle_paths = asset_bundle_paths(asset.bvid)
    video_path = download_video(asset.source_url, asset.bvid, asset.cid, bundle_paths["asset_dir"])
    if video_path is None:
        return "Transcript unavailable."

    audio_path = extract_audio_track(video_path, bundle_paths["audio"])
    if audio_path is None:
        return "Transcript unavailable."

    transcript_chunks, used_fallback = transcribe_audio_with_fallback(str(audio_path), duration=asset.duration)
    if used_fallback or not transcript_chunks:
        save_json(bundle_paths["transcript"], {"source": None, "chunks": [], "status": "transcript unavailable"})
        return "Transcript unavailable."

    _store_transcript_chunks(asset, db, transcript_chunks, "gemini_asr")
    return None


def _clear_keyframes(asset: Asset, db: Session) -> None:
    for frame in list(asset.keyframes):
        db.delete(frame)
    db.commit()
    db.refresh(asset)

    bundle_paths = asset_bundle_paths(asset.bvid)
    frames_dir = bundle_paths["frames_dir"]
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    for path in (bundle_paths["visual_descriptions"],):
        if path.exists():
            path.unlink()


def _clear_structured_knowledge(asset: Asset) -> None:
    structured_path = asset_bundle_paths(asset.bvid)["structured_notes"]
    if structured_path.exists():
        structured_path.unlink()


def _delete_asset_snippets(asset: Asset, db: Session) -> None:
    for snippet in list(asset.snippets):
        db.delete(snippet)
    db.commit()
    db.refresh(asset)


def _reset_asset_materialized_data(asset: Asset, db: Session) -> None:
    bundle_paths = asset_bundle_paths(asset.bvid)
    _clear_transcript(asset, db)
    _clear_keyframes(asset, db)
    _clear_structured_knowledge(asset)
    _delete_asset_snippets(asset, db)

    for path in (bundle_paths["metadata"], bundle_paths["audio"]):
        if path.exists():
            path.unlink()

    for candidate in bundle_paths["asset_dir"].glob("video.*"):
        if candidate.is_file():
            candidate.unlink()


def _extract_transcript(asset: Asset, db: Session) -> str | None:
    _clear_transcript(asset, db)
    try:
        transcript_chunks = fetch_subtitle_chunks(asset.bvid, asset.cid)
        if not transcript_chunks:
            return _extract_transcript_with_gemini_asr(asset, db)
        _store_transcript_chunks(asset, db, transcript_chunks, "subtitles")
        return None
    except Exception:
        return _extract_transcript_with_gemini_asr(asset, db)


def _extract_keyframes(asset: Asset, db: Session) -> str | None:
    _clear_keyframes(asset, db)
    bundle_paths = asset_bundle_paths(asset.bvid)
    video_path = download_video(asset.source_url, asset.bvid, asset.cid, bundle_paths["asset_dir"])
    if video_path is None:
        save_json(bundle_paths["visual_descriptions"], [])
        return "Video download failed; metadata-only asset created."

    keyframes = extract_keyframes(video_path, bundle_paths["frames_dir"], asset.duration)
    for keyframe in keyframes:
        db.add(
            Keyframe(
                asset_id=asset.id,
                timestamp=float(keyframe["timestamp"]),
                file_path=str(keyframe["file_path"]),
                visual_description=None,
            )
        )
    db.commit()
    db.refresh(asset)
    if not keyframes:
        save_json(bundle_paths["visual_descriptions"], [])
        return "Video downloaded but keyframe extraction failed or ffmpeg is unavailable."
    return None


def _describe_keyframes(asset: Asset, db: Session) -> bool:
    visual_descriptions: list[dict[str, Any]] = []
    used_fallback = False
    for frame in sorted(asset.keyframes, key=lambda row: row.timestamp):
        description, frame_used_fallback = describe_image_with_fallback(
            frame.file_path,
            context=f"Video title: {asset.title or asset.bvid}\nDescription: {asset.description or ''}",
        )
        frame.visual_description = description
        db.add(frame)
        visual_descriptions.append(
            {
                "timestamp": frame.timestamp,
                "file_path": frame.file_path,
                "visual_description": description,
            }
        )
        used_fallback = used_fallback or frame_used_fallback
    db.commit()
    db.refresh(asset)
    save_json(asset_bundle_paths(asset.bvid)["visual_descriptions"], visual_descriptions)
    return used_fallback


def _generate_structured_knowledge(asset: Asset) -> tuple[dict[str, Any], bool]:
    asset_payload = _build_asset_payload(asset)
    knowledge, used_fallback = generate_structured_notes_with_fallback(asset_payload)
    validated = StructuredKnowledge.model_validate(knowledge).model_dump()
    save_json(asset_bundle_paths(asset.bvid)["structured_notes"], validated)
    return validated, used_fallback


def _refresh_asset_snippets(asset: Asset, db: Session) -> None:
    _delete_asset_snippets(asset, db)
    metadata = _metadata_payload(asset)
    metadata_summary = ". ".join(
        [
            part
            for part in [
                asset.title or "",
                f"Uploader: {asset.uploader}" if asset.uploader else "",
                asset.description or "",
                f"Tags: {', '.join(metadata.get('tags') or [])}" if metadata.get("tags") else "",
            ]
            if part
        ]
    ).strip()
    if metadata_summary:
        db.add(
            AssetSnippet(
                asset_id=asset.id,
                source_type="metadata",
                timestamp=None,
                text=metadata_summary,
                metadata_json=json.dumps({"title": asset.title, "bvid": asset.bvid}, ensure_ascii=False),
            )
        )

    for chunk in asset.transcript_chunks:
        db.add(
            AssetSnippet(
                asset_id=asset.id,
                source_type="transcript",
                timestamp=chunk.start_time,
                text=chunk.text,
                metadata_json=json.dumps({"end_time": chunk.end_time}, ensure_ascii=False),
            )
        )

    for frame in asset.keyframes:
        if frame.visual_description:
            db.add(
                AssetSnippet(
                    asset_id=asset.id,
                    source_type="visual_description",
                    timestamp=frame.timestamp,
                    text=frame.visual_description,
                    metadata_json=json.dumps({"file_path": frame.file_path}, ensure_ascii=False),
                )
            )

    knowledge = _asset_structured_knowledge(asset)
    if knowledge.get("summary"):
        db.add(
            AssetSnippet(
                asset_id=asset.id,
                source_type="structured_summary",
                timestamp=None,
                text=knowledge["summary"],
                metadata_json="{}",
            )
        )
    for key in ("facts", "opinions", "arguments", "concepts", "causal_chains", "visual_evidence"):
        for item in knowledge.get(key) or []:
            db.add(
                AssetSnippet(
                    asset_id=asset.id,
                    source_type=key,
                    timestamp=None,
                    text=item,
                    metadata_json="{}",
                )
            )
    for item in knowledge.get("timeline") or []:
        if isinstance(item, dict) and item.get("event"):
            db.add(
                AssetSnippet(
                    asset_id=asset.id,
                    source_type="timeline",
                    timestamp=item.get("timestamp"),
                    text=item["event"],
                    metadata_json="{}",
                )
            )

    db.commit()
    db.refresh(asset)


def _derive_asset_warnings(asset: Asset, used_llm_fallback: bool = False) -> list[str]:
    warnings: list[str] = []
    if not asset.transcript_chunks:
        warnings.append("Transcript unavailable.")
    if not asset.keyframes:
        warnings.append("Keyframes unavailable.")
    elif any(not frame.visual_description for frame in asset.keyframes):
        warnings.append("Visual descriptions unavailable for one or more keyframes.")
    knowledge = _asset_structured_knowledge(asset)
    if not knowledge.get("summary"):
        warnings.append("Structured knowledge unavailable.")
    if used_llm_fallback:
        warnings.append("Gemini unavailable or failed; fallback knowledge was used.")
    return warnings


def _finalize_asset(asset: Asset, db: Session, used_llm_fallback: bool = False) -> Asset:
    _refresh_asset_snippets(asset, db)
    warnings = _derive_asset_warnings(asset, used_llm_fallback=used_llm_fallback)
    final_status = "ready" if not warnings else "partial_ready"
    _set_status(asset, final_status, db, "\n".join(warnings) if warnings else None)
    return asset


def ensure_asset_indexed(asset: Asset, db: Session) -> Asset:
    if not asset.snippets:
        _refresh_asset_snippets(asset, db)
    return asset


def _run_extraction_pipeline(asset: Asset, db: Session) -> Asset:
    asset.error_message = None
    db.add(asset)
    db.commit()
    db.refresh(asset)
    llm_fallback_used = not llm_is_configured()

    try:
        _set_status(asset, "fetching_metadata", db)
        metadata = fetch_metadata(asset.bvid)
        asset.aid = metadata.get("aid")
        asset.cid = metadata.get("cid")
        asset.title = metadata.get("title")
        asset.uploader = metadata.get("uploader")
        asset.description = metadata.get("description")
        asset.duration = metadata.get("duration")
        db.add(asset)
        db.commit()
        db.refresh(asset)
        save_json(asset_bundle_paths(asset.bvid)["metadata"], metadata)
    except Exception as exc:
        _set_status(asset, "failed", db, f"Metadata fetch failed: {exc}")
        raise

    _set_status(asset, "extracting_transcript", db)
    _extract_transcript(asset, db)

    _set_status(asset, "extracting_video", db)
    keyframe_warning = _extract_keyframes(asset, db)
    if keyframe_warning is None and asset.keyframes:
        llm_fallback_used = _describe_keyframes(asset, db) or llm_fallback_used

    _set_status(asset, "generating_notes", db)
    _, notes_used_fallback = _generate_structured_knowledge(asset)
    llm_fallback_used = llm_fallback_used or notes_used_fallback
    return _finalize_asset(asset, db, used_llm_fallback=llm_fallback_used)


def _resume_or_create_asset(source_url: str, db: Session) -> Asset:
    bvid = parse_bvid(source_url)
    existing = db.query(Asset).filter(Asset.bvid == bvid).first()
    if existing is not None:
        existing.source_url = source_url
        if existing.status in {"ready", "partial_ready"}:
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        _reset_asset_materialized_data(existing, db)
        return _run_extraction_pipeline(existing, db)

    asset = Asset(bvid=bvid, source_url=source_url, status="created")
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _run_extraction_pipeline(asset, db)


def create_or_get_asset(source_url: str, db: Session) -> Asset:
    return _resume_or_create_asset(source_url, db)


def query_asset(asset_id: int, question: str, db: Session) -> AssetQueryResponse:
    asset = get_asset_by_id(asset_id, db)
    if asset is None:
        raise ValueError("Asset not found")
    asset_payload = _build_asset_payload(asset)
    evidence_snippets = retrieve_relevant_snippets(db, [asset.id], [asset_payload], question, limit=8)
    answer = answer_asset_question(asset_payload, question, evidence_snippets)
    timestamps = sorted(
        {
            float(snippet["timestamp"])
            for snippet in evidence_snippets
            if snippet.get("timestamp") is not None
        }
    )
    evidence = [
        {
            "source_type": snippet["source_type"],
            "timestamp": snippet.get("timestamp"),
            "text": snippet["text"],
            "asset_id": snippet.get("asset_id", asset.id),
        }
        for snippet in evidence_snippets
    ]
    return AssetQueryResponse(answer=answer, evidence=evidence, timestamps=timestamps)


def query_assets(asset_ids: list[int], question: str, db: Session) -> AssetQueryResponse:
    assets = db.query(Asset).filter(Asset.id.in_(asset_ids)).all()
    if len(assets) != len(set(asset_ids)):
        raise ValueError("One or more selected assets were not found")

    refreshed_assets: list[Asset] = []
    for asset in assets:
        if asset.status not in TERMINAL_STATUSES:
            refreshed_assets.append(_resume_or_create_asset(asset.source_url, db))
        else:
            refreshed_assets.append(asset)
    asset_payloads = [_build_asset_payload(asset) for asset in refreshed_assets]
    evidence_snippets = retrieve_relevant_snippets(
        db,
        [asset.id for asset in refreshed_assets],
        asset_payloads,
        question,
        limit=12,
    )
    answer = answer_multi_asset_question(asset_payloads, question, evidence_snippets)
    timestamps = sorted(
        {
            float(snippet["timestamp"])
            for snippet in evidence_snippets
            if snippet.get("timestamp") is not None
        }
    )
    evidence = [
        {
            "source_type": snippet["source_type"],
            "timestamp": snippet.get("timestamp"),
            "text": snippet["text"],
            "asset_id": snippet["asset_id"],
        }
        for snippet in evidence_snippets
    ]
    return AssetQueryResponse(answer=answer, evidence=evidence, timestamps=timestamps)


def retry_asset(asset_id: int, stage: str, db: Session) -> AssetRetryResponse:
    if stage not in RETRY_STAGES:
        raise ValueError(f"Unsupported retry stage '{stage}'")
    asset = get_asset_by_id(asset_id, db)
    if asset is None:
        raise ValueError("Asset not found")

    llm_fallback_used = not llm_is_configured()
    if stage == "all":
        _reset_asset_materialized_data(asset, db)
        retried = _run_extraction_pipeline(asset, db)
        return AssetRetryResponse(asset=serialize_asset_detail(retried, db))

    if stage == "transcript":
        _set_status(asset, "extracting_transcript", db)
        _extract_transcript(asset, db)
    elif stage == "keyframes":
        _set_status(asset, "extracting_video", db)
        _extract_keyframes(asset, db)
    elif stage == "vision":
        _set_status(asset, "extracting_video", db)
        if not asset.keyframes:
            raise ValueError("No keyframes exist yet. Retry keyframes or all first.")
        llm_fallback_used = _describe_keyframes(asset, db) or llm_fallback_used
    elif stage == "notes":
        _set_status(asset, "generating_notes", db)

    if stage == "keyframes" and asset.keyframes:
        llm_fallback_used = _describe_keyframes(asset, db) or llm_fallback_used
    if stage in {"transcript", "keyframes", "vision", "notes"}:
        _set_status(asset, "generating_notes", db)
        _, notes_used_fallback = _generate_structured_knowledge(asset)
        llm_fallback_used = llm_fallback_used or notes_used_fallback

    finalized = _finalize_asset(asset, db, used_llm_fallback=llm_fallback_used)
    return AssetRetryResponse(asset=serialize_asset_detail(finalized, db))


def generate_from_assets(asset_ids: list[int], output_type: str, user_prompt: str | None, db: Session) -> GeneratedOutputResponse:
    allowed_types = {"illustrated_summary", "understanding_quiz", "mermaid_mind_map"}
    if output_type not in allowed_types:
        raise ValueError(f"Unsupported output type '{output_type}'. Allowed: {sorted(allowed_types)}")

    assets = db.query(Asset).filter(Asset.id.in_(asset_ids)).all()
    if len(assets) != len(set(asset_ids)):
        raise ValueError("One or more selected assets were not found")

    refreshed_assets: list[Asset] = []
    for asset in assets:
        if asset.status not in TERMINAL_STATUSES:
            refreshed_assets.append(_resume_or_create_asset(asset.source_url, db))
        else:
            refreshed_assets.append(asset)
    assets = refreshed_assets
    if any(asset.status == "failed" for asset in assets):
        raise ValueError("One or more selected assets failed extraction. Retry the asset creation first.")

    asset_payloads = [_build_asset_payload(asset) for asset in assets]
    evidence_snippets = retrieve_relevant_snippets(
        db,
        [asset.id for asset in assets],
        asset_payloads,
        user_prompt or output_type,
        limit=12,
    )
    content = generate_output(asset_payloads, output_type, user_prompt, evidence_snippets)

    output = GeneratedOutput(
        asset_ids=json.dumps(asset_ids),
        output_type=output_type,
        user_prompt=user_prompt,
        content=content,
    )
    db.add(output)
    db.commit()
    db.refresh(output)
    return serialize_generated_output(output)
