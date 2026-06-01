"use client";

import Link from "next/link";
import { useEffect, useState, useTransition } from "react";

import { createAsset, listAssets } from "@/lib/api";
import type { AssetSummary } from "@/lib/types";
import { AssetList } from "./asset-list";

export function HomeClient() {
  const [assets, setAssets] = useState<AssetSummary[]>([]);
  const [sourceUrl, setSourceUrl] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function refreshAssets() {
    try {
      const data = await listAssets();
      setAssets(data);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to load assets");
    }
  }

  useEffect(() => {
    refreshAssets();
  }, []);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage("Creating asset. Metadata succeeds first, then transcript/video/keyframes/notes are attempted.");
    startTransition(async () => {
      try {
        const asset = await createAsset(sourceUrl);
        setMessage(`Asset ${asset.bvid} is stored locally with status: ${asset.status}.`);
        setSourceUrl("");
        await refreshAssets();
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Asset creation failed");
      }
    });
  }

  return (
    <>
      <section className="hero-grid">
        <div className="card stack">
          <p className="eyebrow">Video Knowledge Platform</p>
          <h2>Turn public Bilibili videos into structured, reusable knowledge assets.</h2>
          <p className="lead">
            Store metadata, visual evidence, transcripts, and generated outputs in one place, then repurpose them
            across summaries, quizzes, and future knowledge workflows.
          </p>
          <form className="stack" onSubmit={handleSubmit}>
            <input
              className="input"
              placeholder="https://www.bilibili.com/video/BV..."
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              required
            />
            <div className="row">
              <button className="button" disabled={isPending}>
                {isPending ? "Creating Asset..." : "Create Asset"}
              </button>
              <Link href="/generate" className="button secondary">
                Open Generator
              </Link>
            </div>
          </form>
          {message ? <div className="meta-item">{message}</div> : null}
          {error ? <div className="meta-item">{error}</div> : null}
        </div>
        <div className="card stack">
          <h3>What gets stored</h3>
          <div className="meta-list">
            <div className="meta-item">
              <strong>Metadata</strong>
              <div className="muted">BVID, aid, cid, title, uploader, description, duration, tags.</div>
            </div>
            <div className="meta-item">
              <strong>Transcript</strong>
              <div className="muted">Subtitle chunks when available, otherwise the asset remains usable.</div>
            </div>
            <div className="meta-item">
              <strong>Visual Layer</strong>
              <div className="muted">Keyframes plus frame descriptions, which satisfies the non-audio-only requirement.</div>
            </div>
            <div className="meta-item">
              <strong>Generated Outputs</strong>
              <div className="muted">Illustrated summaries, quizzes, and optional Mermaid mind maps.</div>
            </div>
          </div>
        </div>
      </section>

      <section className="card stack">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <p className="eyebrow">Stored Assets</p>
            <h3 className="section-title">Knowledge library</h3>
          </div>
          <button className="button secondary" onClick={() => void refreshAssets()}>
            Refresh
          </button>
        </div>
        <AssetList assets={assets} />
      </section>
    </>
  );
}
