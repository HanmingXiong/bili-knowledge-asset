from __future__ import annotations

from fastapi.testclient import TestClient
import pytest


def _seed_asset(
    app_ctx,
    *,
    with_transcript: bool = True,
    with_keyframe: bool = True,
    with_knowledge: bool = True,
    bvid: str = "BVTEST123456",
    title: str = "Test Asset",
):
    db_module = app_ctx["db_module"]
    models = app_ctx["models_module"]
    extraction = app_ctx["extraction_module"]
    storage = app_ctx["storage_module"]

    with db_module.SessionLocal() as db:
        asset = models.Asset(
            bvid=bvid,
            aid=1,
            cid=2,
            title=title,
            uploader="Tester",
            description="An asset about wolves and arguments.",
            duration=180,
            source_url=f"https://www.bilibili.com/video/{bvid}",
            status="partial_ready",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        storage.save_json(
            storage.asset_bundle_paths(asset.bvid)["metadata"],
            {
                "bvid": asset.bvid,
                "title": asset.title,
                "uploader": asset.uploader,
                "description": asset.description,
                "tags": ["animals", "analysis"],
            },
        )

        if with_transcript:
            transcript_chunks = [
                {
                    "start_time": 12.0,
                    "end_time": 24.0,
                    "text": "The main argument is that wolves coordinate because survival depends on group timing.",
                }
            ]
            db.add(
                models.TranscriptChunk(
                    asset_id=asset.id,
                    start_time=12.0,
                    end_time=24.0,
                    text=transcript_chunks[0]["text"],
                )
            )
            storage.save_json(
                storage.asset_bundle_paths(asset.bvid)["transcript"],
                {"source": "subtitles", "chunks": transcript_chunks},
            )
        if with_keyframe:
            db.add(
                models.Keyframe(
                    asset_id=asset.id,
                    timestamp=60.0,
                    file_path=str(storage.asset_bundle_paths(asset.bvid)["frames_dir"] / "frame_001.jpg"),
                    visual_description="A pack of wolves crossing snow in a tight formation.",
                )
            )
        db.commit()
        db.refresh(asset)

        if with_knowledge:
            storage.save_json(
                storage.asset_bundle_paths(asset.bvid)["structured_notes"],
                {
                    "summary": "A structured explanation of wolf coordination.",
                    "facts": ["Wolves move as a coordinated group."],
                    "opinions": [],
                    "arguments": ["Group timing improves survival odds."],
                    "timeline": [{"timestamp": 12.0, "event": "The narrator introduces the main argument."}],
                    "concepts": ["coordination", "survival"],
                    "causal_chains": ["Coordination leads to better hunting outcomes."],
                    "visual_evidence": ["60s: Wolves move in formation across snow."],
                },
            )

        asset = extraction.ensure_asset_indexed(asset, db)
        return asset.id


def test_asset_detail_exposes_structured_knowledge_and_snippets(app_ctx):
    client = TestClient(app_ctx["app"])
    asset_id = _seed_asset(app_ctx)

    response = client.get(f"/api/assets/{asset_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["structured_knowledge"]["summary"] == "A structured explanation of wolf coordination."
    assert payload["structured_knowledge"]["arguments"] == ["Group timing improves survival odds."]
    assert payload["transcript_source"] == "subtitles"
    assert len(payload["snippets"]) >= 3


def test_query_endpoint_returns_answer_evidence_and_timestamps(app_ctx, monkeypatch: pytest.MonkeyPatch):
    client = TestClient(app_ctx["app"])
    asset_id = _seed_asset(app_ctx)
    extraction = app_ctx["extraction_module"]

    monkeypatch.setattr(
        extraction,
        "answer_asset_question",
        lambda asset_data, question, evidence: "The main argument is that coordinated timing improves survival.",
    )

    response = client.post(f"/api/assets/{asset_id}/query", json={"question": "What are the main arguments?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("The main argument")
    assert payload["evidence"]
    assert payload["evidence"][0]["source_type"]
    assert payload["evidence"][0]["asset_id"] == asset_id
    assert 12.0 in payload["timestamps"]


def test_retry_endpoint_regenerates_structured_knowledge(app_ctx, monkeypatch: pytest.MonkeyPatch):
    client = TestClient(app_ctx["app"])
    asset_id = _seed_asset(app_ctx, with_knowledge=False)
    extraction = app_ctx["extraction_module"]
    storage = app_ctx["storage_module"]

    def fake_generate_structured_knowledge(asset):
        payload = {
            "summary": "Retry generated a structured summary.",
            "facts": ["Retry fact"],
            "opinions": [],
            "arguments": ["Retry argument"],
            "timeline": [],
            "concepts": ["retry"],
            "causal_chains": [],
            "visual_evidence": [],
        }
        storage.save_json(storage.asset_bundle_paths(asset.bvid)["structured_notes"], payload)
        return payload, False

    monkeypatch.setattr(extraction, "_generate_structured_knowledge", fake_generate_structured_knowledge)

    response = client.post(f"/api/assets/{asset_id}/retry", json={"stage": "notes"})
    assert response.status_code == 200
    payload = response.json()["asset"]
    assert payload["structured_knowledge"]["summary"] == "Retry generated a structured summary."
    assert payload["status"] in {"ready", "partial_ready"}


def test_transcript_falls_back_to_gemini_asr_when_subtitles_are_missing(app_ctx, monkeypatch: pytest.MonkeyPatch):
    models = app_ctx["models_module"]
    extraction = app_ctx["extraction_module"]
    storage = app_ctx["storage_module"]
    db_module = app_ctx["db_module"]

    with db_module.SessionLocal() as db:
        asset = models.Asset(
            bvid="BVASR123456",
            aid=5,
            cid=6,
            title="ASR Asset",
            uploader="Tester",
            description="An asset that needs ASR fallback.",
            duration=90,
            source_url="https://www.bilibili.com/video/BVASR123456",
            status="created",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        storage.save_json(storage.asset_bundle_paths(asset.bvid)["metadata"], {"bvid": asset.bvid, "title": asset.title})
        audio_path = storage.asset_bundle_paths(asset.bvid)["audio"]

        monkeypatch.setattr(extraction, "fetch_subtitle_chunks", lambda bvid, cid: [])
        monkeypatch.setattr(extraction, "download_video", lambda *args, **kwargs: storage.asset_bundle_paths(asset.bvid)["video"])
        monkeypatch.setattr(extraction, "extract_audio_track", lambda *args, **kwargs: audio_path)
        monkeypatch.setattr(
            extraction,
            "transcribe_audio_with_fallback",
            lambda *args, **kwargs: (
                [
                    {"start_time": 0.0, "end_time": 11.0, "text": "A homemade flying sword prototype lifts off."},
                    {"start_time": 11.0, "end_time": 24.0, "text": "The creator explains how the design works."},
                ],
                False,
            ),
        )

        warning = extraction._extract_transcript(asset, db)
        assert warning is None
        detail = extraction.serialize_asset_detail(asset, db)
        assert detail.transcript_source == "gemini_asr"
        assert len(detail.transcript_chunks) == 2


def test_multi_asset_query_endpoint_returns_structured_evidence(app_ctx, monkeypatch: pytest.MonkeyPatch):
    client = TestClient(app_ctx["app"])
    extraction = app_ctx["extraction_module"]
    first_asset_id = _seed_asset(app_ctx, bvid="BVQUERY11111", title="First Asset")
    second_asset_id = _seed_asset(app_ctx, with_transcript=False, bvid="BVQUERY22222", title="Second Asset")

    monkeypatch.setattr(
        extraction,
        "answer_multi_asset_question",
        lambda asset_data_list, question, evidence: "Both assets emphasize visible coordination and motion.",
    )

    response = client.post(
        "/api/query",
        json={"asset_ids": [first_asset_id, second_asset_id], "question": "What do these assets have in common?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("Both assets")
    assert payload["evidence"]
    assert all("asset_id" in item for item in payload["evidence"])
