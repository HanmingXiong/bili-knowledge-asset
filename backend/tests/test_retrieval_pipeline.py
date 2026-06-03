from __future__ import annotations


def test_retrieval_pipeline_uses_indexed_snippets(app_ctx):
    db_module = app_ctx["db_module"]
    models = app_ctx["models_module"]
    extraction = app_ctx["extraction_module"]
    retrieval = app_ctx["retrieval_module"]
    storage = app_ctx["storage_module"]

    with db_module.SessionLocal() as db:
        asset = models.Asset(
            bvid="BVFTS123456",
            aid=10,
            cid=20,
            title="FTS Asset",
            uploader="Tester",
            description="Asset for retrieval testing.",
            duration=90,
            source_url="https://www.bilibili.com/video/BVFTS123456",
            status="ready",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        db.add(
            models.TranscriptChunk(
                asset_id=asset.id,
                start_time=15.0,
                end_time=22.0,
                text="Evaluator reliability matters because clear evidence improves trust.",
            )
        )
        db.commit()
        db.refresh(asset)

        storage.save_json(
            storage.asset_bundle_paths(asset.bvid)["metadata"],
            {"bvid": asset.bvid, "title": asset.title, "tags": ["reliability"]},
        )
        storage.save_json(
            storage.asset_bundle_paths(asset.bvid)["structured_notes"],
            {
                "summary": "A summary about evaluator trust.",
                "facts": ["Evidence improves trust."],
                "opinions": [],
                "arguments": ["Reliable evidence increases evaluator confidence."],
                "timeline": [],
                "concepts": ["trust", "reliability"],
                "causal_chains": [],
                "visual_evidence": [],
            },
        )

        asset = extraction.ensure_asset_indexed(asset, db)
        asset_payload = extraction._build_asset_payload(asset)
        snippets = retrieval.retrieve_relevant_snippets(
            db,
            [asset.id],
            [asset_payload],
            "reliability trust evidence",
            limit=5,
        )

        assert snippets
        assert any("trust" in snippet["text"].lower() or "reliability" in snippet["text"].lower() for snippet in snippets)
