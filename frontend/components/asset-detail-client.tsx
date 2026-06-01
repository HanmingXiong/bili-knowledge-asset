"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getAsset } from "@/lib/api";
import { formatDate, formatTimestamp } from "@/lib/format";
import type { AssetDetail } from "@/lib/types";
import { GenerateForm } from "./generate-form";
import { RichText } from "./rich-text";
import { StatusBadge } from "./status-badge";

function compactDescription(text?: string | null): string {
  if (!text) {
    return "No visual description available.";
  }

  const cleaned = text
    .replace(/\r\n/g, "\n")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*[-*]\s+/gm, "")
    .replace(/\n+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (cleaned.length <= 180) {
    return cleaned;
  }

  const shortened = cleaned.slice(0, 177);
  const cutAt = Math.max(shortened.lastIndexOf("."), shortened.lastIndexOf(","), shortened.lastIndexOf(" "));
  return `${shortened.slice(0, cutAt > 90 ? cutAt : shortened.length).trim()}...`;
}

export function AssetDetailClient({ assetId }: { assetId: number }) {
  const [asset, setAsset] = useState<AssetDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAsset() {
      try {
        const data = await getAsset(assetId);
        setAsset(data);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Failed to load asset");
      }
    }

    void loadAsset();
  }, [assetId]);

  if (error) {
    return <div className="card">{error}</div>;
  }

  if (!asset) {
    return <div className="card">Loading asset...</div>;
  }

  return (
    <div className="stack">
      <section className="card stack">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <p className="eyebrow">Asset Detail</p>
            <h2>{asset.title || asset.bvid}</h2>
            <p>{asset.description || "No description from source metadata."}</p>
          </div>
          <StatusBadge status={asset.status} />
        </div>
        <div className="meta-list">
          <div className="meta-item">
            <strong>BVID</strong>
            <div className="muted">{asset.bvid}</div>
          </div>
          <div className="meta-item">
            <strong>Uploader</strong>
            <div className="muted">{asset.uploader || "Unknown"}</div>
          </div>
          <div className="meta-item">
            <strong>Duration</strong>
            <div className="muted">{formatTimestamp(asset.duration)}</div>
          </div>
          <div className="meta-item">
            <strong>Created</strong>
            <div className="muted">{formatDate(asset.created_at)}</div>
          </div>
        </div>
        <div className="chips">
          {asset.tags.length ? asset.tags.map((tag) => <span key={tag} className="chip">{tag}</span>) : <span className="chip">No tags available</span>}
        </div>
        {asset.error_message ? <div className="meta-item">{asset.error_message}</div> : null}
        <div className="row">
          <a href={asset.source_url} target="_blank" rel="noreferrer" className="button secondary">
            Open Source Video
          </a>
          <Link href="/generate" className="button secondary">
            Open Multi-Asset Generator
          </Link>
        </div>
      </section>

      <section className="content-grid">
        <div className="card stack">
          <p className="eyebrow">Structured Notes</p>
          <div className="notes-block">
            {asset.structured_notes ? <RichText content={asset.structured_notes} /> : "Structured notes are unavailable."}
          </div>
        </div>
        <div className="card stack">
          <p className="eyebrow">Transcript Status</p>
          <div className="meta-item">{asset.transcript_status}</div>
          <div className="muted">
            Transcript chunks: {asset.transcript_chunks.length} | Keyframes: {asset.keyframes.length} | Outputs:{" "}
            {asset.generated_outputs.length}
          </div>
        </div>
      </section>

      <section className="card stack">
        <div>
          <p className="eyebrow">Visual Evidence</p>
          <h3>Keyframes and frame descriptions</h3>
        </div>
        {asset.keyframes.length ? (
          <div className="frame-grid">
            {asset.keyframes.map((frame) => (
              <article key={frame.id} className="frame-card">
                <img src={`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}${frame.file_url}`} alt={`Frame at ${frame.timestamp}s`} />
                <div className="frame-meta">
                  <div className="frame-time">{formatTimestamp(frame.timestamp)}</div>
                  <div className="frame-description">{compactDescription(frame.visual_description)}</div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty">No keyframes available. The asset still remains usable from metadata and notes.</div>
        )}
      </section>

      <section className="content-grid">
        <div className="card stack">
          <p className="eyebrow">Transcript Chunks</p>
          {asset.transcript_chunks.length ? (
            asset.transcript_chunks.map((chunk) => (
              <div key={chunk.id} className="transcript-block">
                <strong>
                  {formatTimestamp(chunk.start_time)} - {formatTimestamp(chunk.end_time)}
                </strong>
                {"\n"}
                {chunk.text}
              </div>
            ))
          ) : (
            <div className="empty">Transcript unavailable.</div>
          )}
        </div>
        <div className="card stack">
          <p className="eyebrow">Generated Outputs</p>
          {asset.generated_outputs.length ? (
            asset.generated_outputs.map((output) => (
              <div key={output.id} className="output-block">
                <h4>{output.output_type.replaceAll("_", " ")}</h4>
                <RichText content={output.content} />
              </div>
            ))
          ) : (
            <div className="empty">No generated outputs saved for this asset yet.</div>
          )}
        </div>
      </section>

      <GenerateForm preselectedAssetId={asset.id} />
    </div>
  );
}
