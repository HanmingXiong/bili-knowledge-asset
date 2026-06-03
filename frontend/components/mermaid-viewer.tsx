"use client";

import { useEffect, useId, useState } from "react";

function normalizeMermaid(source: string): string {
  return source
    .trim()
    .replace(/^```mermaid\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/```$/i, "")
    .trim();
}

export function MermaidViewer({ chart }: { chart: string }) {
  const id = useId().replace(/:/g, "-");
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const normalized = normalizeMermaid(chart);

  useEffect(() => {
    let cancelled = false;

    async function renderChart() {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" });
        const result = await mermaid.render(`mermaid-${id}`, normalized);
        if (!cancelled) {
          setSvg(result.svg);
          setError(null);
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Mermaid rendering failed");
          setSvg("");
        }
      }
    }

    void renderChart();
    return () => {
      cancelled = true;
    };
  }, [id, normalized]);

  if (error) {
    return (
      <div className="output-block">
        <div className="meta-item">{error}</div>
        <pre className="mermaid-fallback">{normalized}</pre>
      </div>
    );
  }

  if (!svg) {
    return <div className="output-block">Rendering Mermaid diagram...</div>;
  }

  return <div className="mermaid-viewer" dangerouslySetInnerHTML={{ __html: svg }} />;
}
