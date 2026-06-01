import Link from "next/link";

import { formatDate, formatTimestamp } from "@/lib/format";
import type { AssetSummary } from "@/lib/types";
import { StatusBadge } from "./status-badge";

export function AssetList({ assets }: { assets: AssetSummary[] }) {
  if (!assets.length) {
    return <div className="empty">No assets yet. Create one from a public Bilibili URL.</div>;
  }

  return (
    <div className="asset-list">
      {assets.map((asset) => (
        <article key={asset.id} className="asset-card">
          <StatusBadge status={asset.status} />
          <div>
            <h3>{asset.title || asset.bvid}</h3>
            <p className="muted">{asset.uploader || "Unknown uploader"}</p>
          </div>
          <div className="meta-list">
            <div className="meta-item">
              <strong>BVID</strong>
              <div className="muted">{asset.bvid}</div>
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
          {asset.error_message ? <div className="muted">{asset.error_message}</div> : null}
          <div className="row">
            <Link href={`/assets/${asset.id}`} className="button secondary">
              Open Asset
            </Link>
            <a href={asset.source_url} target="_blank" rel="noreferrer" className="button secondary">
              View Source
            </a>
          </div>
        </article>
      ))}
    </div>
  );
}
