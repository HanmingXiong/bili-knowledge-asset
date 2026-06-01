from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Asset, GeneratedOutput, Keyframe, TranscriptChunk
from app.schemas import AssetDetailResponse, AssetSummaryResponse, GeneratedOutputResponse, KeyframeResponse
from app.services.bilibili import fetch_metadata, fetch_subtitle_chunks, parse_bvid
from app.services.llm import (
    describe_image_with_fallback,
    generate_output,
    generate_structured_notes_with_fallback,
    llm_is_configured,
)
from app.services.storage import asset_bundle_paths, load_json, save_json, to_media_path
from app.services.video import download_video, extract_keyframes

TERMINAL_STATUSES = {"ready", "partial_ready", "failed"}


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


def _asset_tags(asset: Asset) -> list[str]:
    metadata = load_json(asset_bundle_paths(asset.bvid)["metadata"], {})
    return metadata.get("tags") or []


def _asset_visual_descriptions(asset: Asset) -> list[dict[str, Any]]:
    return load_json(asset_bundle_paths(asset.bvid)["visual_descriptions"], [])


def _asset_structured_notes(asset: Asset) -> str | None:
    payload = load_json(asset_bundle_paths(asset.bvid)["structured_notes"], {})
    return payload.get("content")


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
    transcript_status = "available" if asset.transcript_chunks else "transcript unavailable"
    return AssetDetailResponse(
        **serialize_asset_summary(asset).model_dump(),
        description=asset.description,
        tags=_asset_tags(asset),
        transcript_status=transcript_status,
        transcript_chunks=asset.transcript_chunks,
        keyframes=keyframes,
        generated_outputs=[serialize_generated_output(output) for output in _generated_outputs_for_asset(asset.id, db)],
        structured_notes=_asset_structured_notes(asset),
        visual_descriptions=_asset_visual_descriptions(asset),
    )


def _build_asset_payload(asset: Asset) -> dict[str, Any]:
    metadata_path = asset_bundle_paths(asset.bvid)["metadata"]
    metadata = load_json(metadata_path, {})
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
            {
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "text": chunk.text,
            }
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
        "structured_notes": _asset_structured_notes(asset),
    }


def _reset_asset_materialized_data(asset: Asset, db: Session) -> None:
    bundle_paths = asset_bundle_paths(asset.bvid)
    for chunk in list(asset.transcript_chunks):
        db.delete(chunk)
    for frame in list(asset.keyframes):
        db.delete(frame)
    db.commit()
    db.refresh(asset)

    for path in [
        bundle_paths["metadata"],
        bundle_paths["transcript"],
        bundle_paths["visual_descriptions"],
        bundle_paths["structured_notes"],
        bundle_paths["audio"],
    ]:
        if path.exists():
            path.unlink()

    for candidate in bundle_paths["asset_dir"].glob("video.*"):
        if candidate.is_file():
            candidate.unlink()

    frames_dir = bundle_paths["frames_dir"]
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)


def _run_extraction_pipeline(asset: Asset, db: Session) -> Asset:
    warnings: list[str] = []
    llm_fallback_used = not llm_is_configured()
    bvid = asset.bvid
    asset.error_message = None
    db.add(asset)
    db.commit()
    db.refresh(asset)

    try:
        _set_status(asset, "fetching_metadata", db)
        metadata = fetch_metadata(bvid)
        asset.aid = metadata.get("aid")
        asset.cid = metadata.get("cid")
        asset.title = metadata.get("title")
        asset.uploader = metadata.get("uploader")
        asset.description = metadata.get("description")
        asset.duration = metadata.get("duration")
        _set_status(asset, "extracting_transcript", db)
        save_json(asset_bundle_paths(bvid)["metadata"], metadata)
    except Exception as exc:
        _set_status(asset, "failed", db, f"Metadata fetch failed: {exc}")
        raise

    try:
        transcript_chunks = fetch_subtitle_chunks(bvid, asset.cid)
        save_json(asset_bundle_paths(bvid)["transcript"], transcript_chunks)
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
        if not transcript_chunks:
            warnings.append("Transcript unavailable.")
    except Exception as exc:
        warnings.append(f"Transcript unavailable: {exc}")
        save_json(asset_bundle_paths(bvid)["transcript"], {"status": "transcript unavailable", "error": str(exc)})

    _set_status(asset, "extracting_video", db)
    video_path = download_video(asset.source_url, bvid, asset.cid, asset_bundle_paths(bvid)["asset_dir"])
    if video_path is None:
        warnings.append("Video download failed; metadata-only asset created.")
    else:
        keyframes = extract_keyframes(video_path, asset_bundle_paths(bvid)["frames_dir"], asset.duration)
        visual_descriptions: list[dict[str, Any]] = []
        for keyframe in keyframes:
            frame_path = Path(str(keyframe["file_path"]))
            description, used_fallback = describe_image_with_fallback(
                str(frame_path),
                context=f"Video title: {asset.title or bvid}\nDescription: {asset.description or ''}",
            )
            llm_fallback_used = llm_fallback_used or used_fallback
            frame_row = Keyframe(
                asset_id=asset.id,
                timestamp=float(keyframe["timestamp"]),
                file_path=str(frame_path),
                visual_description=description,
            )
            db.add(frame_row)
            db.flush()
            visual_descriptions.append(
                {
                    "timestamp": float(keyframe["timestamp"]),
                    "file_path": str(frame_path),
                    "visual_description": description,
                }
            )
        db.commit()
        db.refresh(asset)
        save_json(asset_bundle_paths(bvid)["visual_descriptions"], visual_descriptions)
        if not keyframes:
            warnings.append("Video downloaded but keyframe extraction failed or ffmpeg is unavailable.")

    _set_status(asset, "generating_notes", db)
    asset_payload = _build_asset_payload(asset)
    notes, notes_used_fallback = generate_structured_notes_with_fallback(asset_payload)
    llm_fallback_used = llm_fallback_used or notes_used_fallback
    save_json(asset_bundle_paths(bvid)["structured_notes"], {"content": notes})
    if llm_fallback_used:
        warnings.append("Gemini unavailable or failed; local fallback descriptions/notes were used. Retry later if needed.")

    final_status = "ready" if not warnings else "partial_ready"
    error_message = "\n".join(warnings) if warnings else None
    _set_status(asset, final_status, db, error_message)
    return asset


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
    content = generate_output(asset_payloads, output_type, user_prompt)

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
