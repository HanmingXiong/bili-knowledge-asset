"use client";

import { useEffect, useMemo, useState, useTransition } from "react";

import { generateOutput, listAssets } from "@/lib/api";
import type { AssetSummary, GeneratedOutput } from "@/lib/types";
import { RichText } from "./rich-text";

const OUTPUT_OPTIONS = [
  { value: "illustrated_summary", label: "Illustrated Summary" },
  { value: "understanding_quiz", label: "Understanding Quiz" },
  { value: "mermaid_mind_map", label: "Mermaid Mind Map" },
];

export function GenerateForm({ preselectedAssetId }: { preselectedAssetId?: number }) {
  const [assets, setAssets] = useState<AssetSummary[]>([]);
  const [selectedAssetIds, setSelectedAssetIds] = useState<number[]>(preselectedAssetId ? [preselectedAssetId] : []);
  const [outputType, setOutputType] = useState("illustrated_summary");
  const [userPrompt, setUserPrompt] = useState("");
  const [output, setOutput] = useState<GeneratedOutput | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

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

  return (
    <div className="stack">
      <form className="card stack" onSubmit={handleGenerate}>
        <div>
          <p className="eyebrow">Output Generator</p>
          <h2>Generate from one or more stored assets</h2>
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
        <select className="select" value={outputType} onChange={(event) => setOutputType(event.target.value)}>
          {OUTPUT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <textarea
          className="textarea"
          placeholder="Optional instruction: focus on facts, controversy, practical actions, etc."
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
          <div className="output-block">
            <RichText content={output.content} />
          </div>
        </section>
      ) : null}
    </div>
  );
}
