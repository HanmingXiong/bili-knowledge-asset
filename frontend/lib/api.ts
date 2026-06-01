import type { AssetDetail, AssetSummary, GeneratedOutput } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function listAssets(): Promise<AssetSummary[]> {
  return apiFetch<AssetSummary[]>("/api/assets");
}

export function getAsset(assetId: number): Promise<AssetDetail> {
  return apiFetch<AssetDetail>(`/api/assets/${assetId}`);
}

export function createAsset(sourceUrl: string): Promise<AssetDetail> {
  return apiFetch<AssetDetail>("/api/assets/create", {
    method: "POST",
    body: JSON.stringify({ source_url: sourceUrl }),
  });
}

export function generateOutput(payload: {
  asset_ids: number[];
  output_type: string;
  user_prompt?: string;
}): Promise<{ output: GeneratedOutput }> {
  return apiFetch<{ output: GeneratedOutput }>("/api/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
