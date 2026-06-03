"use client";

import Link from "next/link";
import { useEffect, useState, useTransition } from "react";

import { createAsset, listAssets } from "@/lib/api";
import type { AssetSummary } from "@/lib/types";
import { AssetList } from "./asset-list";

const FEATURE_CARDS = [
  {
    title: "Visual Keyframes",
    body: "Sample frames, attach timestamps, and preserve visual evidence so each asset is more than transcript-only text.",
  },
  {
    title: "Transcript / ASR",
    body: "Use Bilibili subtitles first, then fall back to Gemini ASR when the platform does not expose subtitle files.",
  },
  {
    title: "Ask Your Asset",
    body: "Query one asset or compare several assets using retrieved transcript, visual, and structured evidence.",
  },
  {
    title: "Multi-Output Generation",
    body: "Generate illustrated summaries, understanding quizzes, and Mermaid mind maps from one or more stored assets.",
  },
  {
    title: "Reusable Memory",
    body: "Index transcript chunks, visual descriptions, and structured knowledge into SQLite FTS memory for later retrieval.",
  },
];

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
      <section className="hero-panel">
        <div className="hero-copy stack">
          <p className="eyebrow">Bilibili videos to reusable knowledge assets</p>
          <h1 className="hero-title">Capture video knowledge once. Reuse it across notes, quizzes, mind maps, and Q&A.</h1>
          <p className="lead">
            Bili Knowledge Asset extracts Bilibili metadata, transcript evidence, keyframes, structured knowledge, and
            searchable memory so the video becomes a durable study asset instead of a one-time watch.
          </p>
          <form className="hero-form" onSubmit={handleSubmit}>
            <input
              className="input input-large"
              placeholder="Paste a public Bilibili URL, for example https://www.bilibili.com/video/BV..."
              value={sourceUrl}
              onChange={(event) => setSourceUrl(event.target.value)}
              required
            />
            <div className="row">
              <button className="button button-large" disabled={isPending}>
                {isPending ? "Creating Knowledge Asset..." : "Create Reusable Asset"}
              </button>
              <Link href="/generate" className="button secondary">
                Open Generator
              </Link>
            </div>
          </form>
          {message ? <div className="meta-item">{message}</div> : null}
          {error ? <div className="meta-item meta-item-danger">{error}</div> : null}
        </div>
        <div className="hero-side card stack">
          <div>
            <p className="eyebrow">Why it feels useful immediately</p>
            <h3>Each asset stores the raw evidence and the reusable abstractions.</h3>
          </div>
          <div className="stats-grid">
            <div className="stat-card">
              <strong>Metadata</strong>
              <span>BVID, uploader, duration, description, tags</span>
            </div>
            <div className="stat-card">
              <strong>Transcript</strong>
              <span>Subtitles first, Gemini ASR fallback when needed</span>
            </div>
            <div className="stat-card">
              <strong>Visual Layer</strong>
              <span>Keyframes, timestamps, and visual descriptions</span>
            </div>
            <div className="stat-card">
              <strong>Outputs</strong>
              <span>Summaries, quizzes, mind maps, and query answers</span>
            </div>
          </div>
          <div className="meta-item">
            Assets remain usable even when extraction is partial. The library keeps metadata, evidence, and retry
            controls instead of failing hard.
          </div>
        </div>
      </section>

      <section className="card stack">
        <div>
          <p className="eyebrow">Core Capabilities</p>
          <h2 className="section-title">From paste-in link to study-ready asset</h2>
        </div>
        <div className="feature-grid">
          {FEATURE_CARDS.map((feature) => (
            <article key={feature.title} className="feature-card">
              <h3>{feature.title}</h3>
              <p>{feature.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="card stack">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <p className="eyebrow">Stored Assets</p>
            <h2 className="section-title">Knowledge library</h2>
            <p className="section-copy">Review previous extractions, reopen structured evidence, and generate new outputs from any saved asset.</p>
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
