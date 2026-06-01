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

export type AssetDetail = AssetSummary & {
  description?: string | null;
  tags: string[];
  transcript_status: string;
  transcript_chunks: TranscriptChunk[];
  keyframes: Keyframe[];
  generated_outputs: GeneratedOutput[];
  structured_notes?: string | null;
  visual_descriptions: Array<Record<string, unknown>>;
};
