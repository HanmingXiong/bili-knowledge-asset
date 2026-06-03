"use client";

import { useEffect, useMemo, useState, useTransition } from "react";

import { generateOutput, listAssets, queryAssets } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import type { AssetQueryResult, AssetSummary, GeneratedOutput } from "@/lib/types";
import { MermaidViewer } from "./mermaid-viewer";
import { RichText } from "./rich-text";

const OUTPUT_OPTIONS = [
  { value: "illustrated_summary", label: "Illustrated Summary", body: "Sectioned notes that combine transcript, keyframes, and structured evidence." },
  { value: "understanding_quiz", label: "Understanding Quiz", body: "Multiple-choice and short-answer questions with an answer key." },
  { value: "mermaid_mind_map", label: "Mermaid Mind Map", body: "A visual knowledge structure for fast review and navigation." },
];

export function GenerateForm({ preselectedAssetId }: { preselectedAssetId?: number }) {
  const [assets, setAssets] = useState<AssetSummary[]>([]);
  const [selectedAssetIds, setSelectedAssetIds] = useState<number[]>(preselectedAssetId ? [preselectedAssetId] : []);
  const [outputType, setOutputType] = useState("illustrated_summary");
  const [userPrompt, setUserPrompt] = useState("");
  const [output, setOutput] = useState<GeneratedOutput | null>(null);
  const [comparisonQuestion, setComparisonQuestion] = useState("");
  const [queryResult, setQueryResult] = useState<AssetQueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [isQueryPending, startQueryTransition] = useTransition();

  useEffect(() => {
    async function load() {
      try {
        const data = await listAssets();
        setAssets(data);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Failed to load assets");
      }
    }

    void load();
  }, []);

  const selectableAssets = useMemo(() => {
    return assets.filter((asset) => asset.status !== "failed");
  }, [assets]);

  function toggleAsset(assetId: number) {
    setSelectedAssetIds((current) =>
      current.includes(assetId) ? current.filter((item) => item !== assetId) : [...current, assetId],
    );
  }

  function handleGenerate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    startTransition(async () => {
      try {
        const response = await generateOutput({
          asset_ids: selectedAssetIds,
          output_type: outputType,
          user_prompt: userPrompt || undefined,
        });
        setOutput(response.output);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Generation failed");
      }
    });
  }

  function handleCompareQuery(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    startQueryTransition(async () => {
      try {
        const result = await queryAssets(selectedAssetIds, comparisonQuestion);
        setQueryResult(result);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Query failed");
      }
    });
  }

  return (
    <div className="stack">
      <form className="card stack" onSubmit={handleGenerate}>
        <div>
          <p className="eyebrow">Output Generator</p>
          <h2>Generate from one or more stored assets</h2>
          <p className="section-copy">Choose the assets, choose the output mode, then steer the generation with a focus prompt such as facts, controversy, action steps, or review notes.</p>
        </div>
        <div className="checkbox-list">
          {selectableAssets.map((asset) => (
            <label className="checkbox-card" key={asset.id}>
              <input
                type="checkbox"
                checked={selectedAssetIds.includes(asset.id)}
                onChange={() => toggleAsset(asset.id)}
              />
              <strong>{asset.title || asset.bvid}</strong>
              <div className="muted">{asset.status.replaceAll("_", " ")}</div>
            </label>
          ))}
        </div>
        {!selectableAssets.length ? <div className="empty">Create an asset first.</div> : null}
        <div className="feature-grid">
          {OUTPUT_OPTIONS.map((option) => (
            <article key={option.value} className={`feature-card compact ${outputType === option.value ? "selected" : ""}`}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <h3>{option.label}</h3>
                  <p>{option.body}</p>
                </div>
                <button className="button secondary" type="button" onClick={() => setOutputType(option.value)}>
                  {outputType === option.value ? "Selected" : "Use"}
                </button>
              </div>
            </article>
          ))}
        </div>
        <select className="select" value={outputType} onChange={(event) => setOutputType(event.target.value)}>
          {OUTPUT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <textarea
          className="textarea"
          placeholder="Optional instruction: focus on facts, controversy, action steps, practical lessons, or review-style notes."
          value={userPrompt}
          onChange={(event) => setUserPrompt(event.target.value)}
        />
        <button className="button" disabled={isPending || selectedAssetIds.length === 0}>
          {isPending ? "Generating..." : "Generate Output"}
        </button>
        {error ? <div className="meta-item">{error}</div> : null}
      </form>

      {output ? (
        <section className="card stack">
          <div>
            <p className="eyebrow">Generated Result</p>
            <h3>{output.output_type.replaceAll("_", " ")}</h3>
          </div>
          {output.output_type === "mermaid_mind_map" ? (
            <MermaidViewer chart={output.content} />
          ) : (
            <div className="output-block">
              <RichText content={output.content} />
            </div>
          )}
        </section>
      ) : null}

      <form className="card stack" onSubmit={handleCompareQuery}>
        <div>
          <p className="eyebrow">Cross-Asset Query</p>
          <h3>Ask across the selected assets</h3>
          <p className="section-copy">Useful for comparisons, repeated themes, disagreements, and synthesis across multiple videos.</p>
        </div>
        <textarea
          className="textarea"
          placeholder="What do these assets have in common?"
          value={comparisonQuestion}
          onChange={(event) => setComparisonQuestion(event.target.value)}
        />
        <button className="button" disabled={isQueryPending || selectedAssetIds.length === 0 || !comparisonQuestion.trim()}>
          {isQueryPending ? "Querying..." : "Ask Selected Assets"}
        </button>
        {queryResult ? (
          <div className="output-block">
            <h4>Answer</h4>
            <RichText content={queryResult.answer} />
            {queryResult.evidence.length ? (
              <>
                <h4>Evidence</h4>
                <ul className="plain-list">
                  {queryResult.evidence.map((item, index) => (
                    <li key={`multi-evidence-${index}`}>
                      <strong>
                        Asset {item.asset_id} · {item.source_type.replaceAll("_", " ")}
                        {item.timestamp != null ? ` · ${formatTimestamp(item.timestamp)}` : ""}
                      </strong>
                      : {item.text}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        ) : null}
      </form>
    </div>
  );
}
