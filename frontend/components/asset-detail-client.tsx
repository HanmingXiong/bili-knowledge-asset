"use client";

import Link from "next/link";
import { useEffect, useState, useTransition } from "react";

import { getAsset, queryAsset, retryAsset } from "@/lib/api";
import { formatDate, formatTimestamp } from "@/lib/format";
import type { AssetDetail, AssetQueryResult, StructuredKnowledge } from "@/lib/types";
import { GenerateForm } from "./generate-form";
import { MermaidViewer } from "./mermaid-viewer";
import { RichText } from "./rich-text";
import { StatusBadge } from "./status-badge";

const SECTION_LINKS = [
  { id: "overview", label: "Overview" },
  { id: "knowledge", label: "Structured Knowledge" },
  { id: "ask", label: "Ask Asset" },
  { id: "keyframes", label: "Keyframes" },
  { id: "transcript", label: "Transcript" },
  { id: "outputs", label: "Generate Outputs" },
];

function compactText(text?: string | null, maxLength = 180): string {
  if (!text) {
    return "No description available.";
  }

  const cleaned = text
    .replace(/\r\n/g, "\n")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/^\s*[-*]\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\s*---+\s*/g, " ")
    .replace(/\n+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (cleaned.length <= maxLength) {
    return cleaned;
  }

  const shortened = cleaned.slice(0, Math.max(maxLength - 3, 1));
  const cutAt = Math.max(shortened.lastIndexOf("."), shortened.lastIndexOf(","), shortened.lastIndexOf(" "));
  return `${shortened.slice(0, cutAt > maxLength / 2 ? cutAt : shortened.length).trim()}...`;
}

export function AssetDetailClient({ assetId }: { assetId: number }) {
  const [asset, setAsset] = useState<AssetDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [queryResult, setQueryResult] = useState<AssetQueryResult | null>(null);
  const [retryStage, setRetryStage] = useState<"transcript" | "keyframes" | "vision" | "notes" | "all">("all");
  const [retryMessage, setRetryMessage] = useState<string | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [isQueryPending, startQueryTransition] = useTransition();
  const [isRetryPending, startRetryTransition] = useTransition();

  async function loadAsset() {
    try {
      const data = await getAsset(assetId);
      setAsset(data);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Failed to load asset");
    }
  }

  useEffect(() => {
    void loadAsset();
  }, [assetId]);

  function renderKnowledgeList(title: string, items: string[]) {
    if (!items.length) {
      return null;
    }
    return (
      <div className="knowledge-section">
        <h4>{title}</h4>
        <ul>
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{compactText(item, 150)}</li>
          ))}
        </ul>
      </div>
    );
  }

  function renderTimeline(knowledge: StructuredKnowledge) {
    if (!knowledge.timeline.length) {
      return null;
    }
    return (
      <div className="knowledge-section">
        <h4>Timeline</h4>
        <ul>
          {knowledge.timeline.map((item, index) => (
            <li key={`timeline-${index}`}>
              {item.timestamp != null ? `${formatTimestamp(item.timestamp)}: ` : ""}
              {compactText(item.event, 140)}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  function handleAskAsset(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) {
      return;
    }
    setQueryError(null);
    startQueryTransition(async () => {
      try {
        const result = await queryAsset(assetId, question.trim());
        setQueryResult(result);
      } catch (nextError) {
        setQueryError(nextError instanceof Error ? nextError.message : "Asset query failed");
      }
    });
  }

  function handleRetry() {
    setRetryError(null);
    startRetryTransition(async () => {
      try {
        const response = await retryAsset(assetId, retryStage);
        setAsset(response.asset);
        setRetryMessage(`Retry completed for ${retryStage}. Current status: ${response.asset.status}.`);
      } catch (nextError) {
        setRetryError(nextError instanceof Error ? nextError.message : "Retry failed");
      }
    });
  }

  if (error) {
    return <div className="card">{error}</div>;
  }

  if (!asset) {
    return <div className="card">Loading asset...</div>;
  }

  return (
    <div className="stack">
      <section id="overview" className="card stack asset-hero-card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="stack" style={{ gap: 10 }}>
            <p className="eyebrow">Asset Detail</p>
            <h2 className="asset-page-title">{asset.title || asset.bvid}</h2>
            <p>{asset.description || "No description from source metadata."}</p>
            <div className="row">
              <a href={asset.source_url} target="_blank" rel="noreferrer" className="button secondary">
                Open Source Video
              </a>
              <Link href="/generate" className="button secondary">
                Open Multi-Asset Generator
              </Link>
            </div>
          </div>
          <div className="stack" style={{ gap: 10, alignItems: "flex-end" }}>
            <StatusBadge status={asset.status} />
            <button className="button secondary" disabled={isRetryPending} onClick={handleRetry} type="button">
              {isRetryPending ? "Retrying..." : `Retry ${retryStage}`}
            </button>
          </div>
        </div>
        <div className="stats-grid">
          <div className="stat-card">
            <strong>Transcript Chunks</strong>
            <span>{asset.transcript_chunks.length}</span>
          </div>
          <div className="stat-card">
            <strong>Keyframes</strong>
            <span>{asset.keyframes.length}</span>
          </div>
          <div className="stat-card">
            <strong>Memory Snippets</strong>
            <span>{asset.snippets.length}</span>
          </div>
          <div className="stat-card">
            <strong>Generated Outputs</strong>
            <span>{asset.generated_outputs.length}</span>
          </div>
        </div>
        <div className="meta-list detail-meta-list">
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
            <strong>Transcript</strong>
            <div className="muted">{asset.transcript_source || asset.transcript_status}</div>
          </div>
          <div className="meta-item">
            <strong>Created</strong>
            <div className="muted">{formatDate(asset.created_at)}</div>
          </div>
        </div>
        <div className="chips">
          {asset.tags.length ? asset.tags.map((tag) => <span key={tag} className="chip">{tag}</span>) : <span className="chip">No tags available</span>}
        </div>
        {asset.error_message ? <div className="meta-item meta-item-warning">{asset.error_message}</div> : null}
      </section>

      <nav className="section-nav">
        {SECTION_LINKS.map((section) => (
          <a key={section.id} href={`#${section.id}`} className="section-link">
            {section.label}
          </a>
        ))}
      </nav>

      <section className="content-grid">
        <div id="knowledge" className="card stack">
          <p className="eyebrow">Structured Knowledge</p>
          <div className="notes-block">
            <div className="knowledge-stack">
              <div className="knowledge-section knowledge-summary">
                <h4>Summary</h4>
                <p>{compactText(asset.structured_knowledge.summary, 260) || "No summary available."}</p>
              </div>
              {renderKnowledgeList("Facts", asset.structured_knowledge.facts)}
              {renderKnowledgeList("Arguments", asset.structured_knowledge.arguments)}
              {renderKnowledgeList("Opinions", asset.structured_knowledge.opinions)}
              {renderTimeline(asset.structured_knowledge)}
              {renderKnowledgeList("Concepts", asset.structured_knowledge.concepts)}
              {renderKnowledgeList("Causal Chains", asset.structured_knowledge.causal_chains)}
              {renderKnowledgeList("Visual Evidence", asset.structured_knowledge.visual_evidence)}
            </div>
          </div>
        </div>
        <div className="card stack">
          <p className="eyebrow">Reusable Memory</p>
          <div className="meta-item">{asset.transcript_status}</div>
          <div className="muted">
            The memory index stores metadata, transcript evidence, visual descriptions, and structured knowledge for
            later retrieval and generation.
          </div>
          <div className="snippet-stack">
            {asset.snippets.slice(0, 8).map((snippet) => (
              <div key={snippet.id} className="snippet-card">
                <strong>
                  {snippet.source_type.replaceAll("_", " ")}
                  {snippet.timestamp != null ? ` · ${formatTimestamp(snippet.timestamp)}` : ""}
                </strong>
                <div className="muted">{compactText(snippet.text, 150)}</div>
              </div>
            ))}
            {!asset.snippets.length ? <div className="empty">No indexed snippets yet.</div> : null}
          </div>
        </div>
      </section>

      <section className="content-grid">
        <div id="ask" className="card stack">
          <p className="eyebrow">Ask This Asset</p>
          <div className="muted">Ask for main arguments, facts, comparisons, or practical takeaways. Responses cite retrieved evidence.</div>
          <form className="stack" onSubmit={handleAskAsset}>
            <textarea
              className="textarea"
              placeholder="What are the main arguments?"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <button className="button" disabled={isQueryPending || !question.trim()}>
              {isQueryPending ? "Asking..." : "Ask This Asset"}
            </button>
          </form>
          {queryError ? <div className="meta-item">{queryError}</div> : null}
          {queryResult ? (
            <div className="output-block">
              <h4>Answer</h4>
              <RichText content={queryResult.answer} />
              {queryResult.evidence.length ? (
                <>
                  <h4>Evidence</h4>
                  <div className="evidence-grid">
                    {queryResult.evidence.map((item, index) => (
                      <article key={`evidence-${index}`} className="evidence-card">
                        <div className="evidence-topline">
                          <strong>{item.source_type.replaceAll("_", " ")}</strong>
                          <span className="muted">
                            Asset {item.asset_id}
                            {item.timestamp != null ? ` · ${formatTimestamp(item.timestamp)}` : ""}
                          </span>
                        </div>
                        <div>{compactText(item.text, 180)}</div>
                      </article>
                    ))}
                  </div>
                </>
              ) : null}
              {queryResult.timestamps.length ? (
                <div className="muted">
                  Timestamps: {queryResult.timestamps.map((timestamp) => formatTimestamp(timestamp)).join(", ")}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="card stack">
          <p className="eyebrow">Retry Extraction</p>
          <div className="muted">Retry one stage when subtitles, video download, frame descriptions, or structured notes need another pass.</div>
          <select className="select" value={retryStage} onChange={(event) => setRetryStage(event.target.value as typeof retryStage)}>
            <option value="all">All</option>
            <option value="transcript">Transcript</option>
            <option value="keyframes">Keyframes</option>
            <option value="vision">Vision</option>
            <option value="notes">Notes</option>
          </select>
          <div className="row">
            <button className="button" disabled={isRetryPending} onClick={handleRetry} type="button">
              {isRetryPending ? "Retrying..." : "Retry Extraction"}
            </button>
            <button className="button secondary" onClick={() => void loadAsset()} type="button">
              Refresh Asset
            </button>
          </div>
          {retryError ? <div className="meta-item">{retryError}</div> : null}
          {retryMessage ? <div className="meta-item">{retryMessage}</div> : null}
        </div>
      </section>

      <section id="keyframes" className="card stack">
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
                  <div className="frame-description">{compactText(frame.visual_description, 180)}</div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty">No keyframes available. The asset still remains usable from metadata and notes.</div>
        )}
      </section>

      <section className="content-grid">
        <div id="transcript" className="card stack">
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
        <div id="outputs" className="card stack">
          <p className="eyebrow">Generated Outputs</p>
          {asset.generated_outputs.length ? (
            asset.generated_outputs.map((output) => (
              <div key={output.id} className="output-block">
                <h4>{output.output_type.replaceAll("_", " ")}</h4>
                {output.output_type === "mermaid_mind_map" ? (
                  <MermaidViewer chart={output.content} />
                ) : (
                  <RichText content={output.content} />
                )}
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
