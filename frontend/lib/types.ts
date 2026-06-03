export type AssetSummary = {
  id: number;
  bvid: string;
  aid?: number | null;
  cid?: number | null;
  title?: string | null;
  uploader?: string | null;
  duration?: number | null;
  source_url: string;
  status: string;
  created_at: string;
  updated_at: string;
  error_message?: string | null;
};

export type TranscriptChunk = {
  id: number;
  start_time: number;
  end_time: number;
  text: string;
};

export type Keyframe = {
  id: number;
  timestamp: number;
  file_path: string;
  file_url: string;
  visual_description?: string | null;
};

export type GeneratedOutput = {
  id: number;
  asset_ids: number[];
  output_type: string;
  user_prompt?: string | null;
  content: string;
  created_at: string;
};

export type StructuredTimelineItem = {
  timestamp?: number | null;
  event: string;
};

export type StructuredKnowledge = {
  summary: string;
  facts: string[];
  opinions: string[];
  arguments: string[];
  timeline: StructuredTimelineItem[];
  concepts: string[];
  causal_chains: string[];
  visual_evidence: string[];
};

export type AssetSnippet = {
  id: number;
  source_type: string;
  timestamp?: number | null;
  text: string;
  metadata_json: Record<string, unknown>;
};

export type AssetQueryResult = {
  answer: string;
  evidence: Array<{
    source_type: string;
    timestamp?: number | null;
    text: string;
    asset_id: number;
  }>;
  timestamps: number[];
};

export type AssetDetail = AssetSummary & {
  description?: string | null;
  tags: string[];
  transcript_status: string;
  transcript_source?: string | null;
  transcript_chunks: TranscriptChunk[];
  keyframes: Keyframe[];
  generated_outputs: GeneratedOutput[];
  structured_knowledge: StructuredKnowledge;
  snippets: AssetSnippet[];
  visual_descriptions: Array<Record<string, unknown>>;
};
