from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AssetCreateRequest(BaseModel):
    source_url: str = Field(..., min_length=5)


class TranscriptChunkResponse(BaseModel):
    id: int
    start_time: float
    end_time: float
    text: str

    model_config = {"from_attributes": True}


class KeyframeResponse(BaseModel):
    id: int
    timestamp: float
    file_path: str
    file_url: str
    visual_description: str | None = None


class StructuredTimelineItem(BaseModel):
    timestamp: float | None = None
    event: str


class StructuredKnowledge(BaseModel):
    summary: str = ""
    facts: list[str] = Field(default_factory=list)
    opinions: list[str] = Field(default_factory=list)
    arguments: list[str] = Field(default_factory=list)
    timeline: list[StructuredTimelineItem] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    causal_chains: list[str] = Field(default_factory=list)
    visual_evidence: list[str] = Field(default_factory=list)


class AssetSnippetResponse(BaseModel):
    id: int
    source_type: str
    timestamp: float | None = None
    text: str
    metadata_json: dict = Field(default_factory=dict)


class EvidenceItemResponse(BaseModel):
    source_type: str
    timestamp: float | None = None
    text: str
    asset_id: int


class GeneratedOutputResponse(BaseModel):
    id: int
    asset_ids: list[int]
    output_type: str
    user_prompt: str | None = None
    content: str
    created_at: datetime


class AssetSummaryResponse(BaseModel):
    id: int
    bvid: str
    aid: int | None = None
    cid: int | None = None
    title: str | None = None
    uploader: str | None = None
    duration: int | None = None
    source_url: str
    status: str
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None

    model_config = {"from_attributes": True}


class AssetDetailResponse(AssetSummaryResponse):
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    transcript_status: str = "transcript unavailable"
    transcript_source: str | None = None
    transcript_chunks: list[TranscriptChunkResponse] = Field(default_factory=list)
    keyframes: list[KeyframeResponse] = Field(default_factory=list)
    generated_outputs: list[GeneratedOutputResponse] = Field(default_factory=list)
    structured_knowledge: StructuredKnowledge = Field(default_factory=StructuredKnowledge)
    snippets: list[AssetSnippetResponse] = Field(default_factory=list)
    visual_descriptions: list[dict] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    asset_ids: list[int] = Field(..., min_length=1)
    output_type: str
    user_prompt: str | None = None


class GenerateResponse(BaseModel):
    output: GeneratedOutputResponse


class AssetQueryRequest(BaseModel):
    question: str = Field(..., min_length=3)


class MultiAssetQueryRequest(BaseModel):
    asset_ids: list[int] = Field(..., min_length=1)
    question: str = Field(..., min_length=3)


class AssetQueryResponse(BaseModel):
    answer: str
    evidence: list[EvidenceItemResponse] = Field(default_factory=list)
    timestamps: list[float] = Field(default_factory=list)


class AssetRetryRequest(BaseModel):
    stage: str = Field(..., pattern="^(transcript|keyframes|vision|notes|all)$")


class AssetRetryResponse(BaseModel):
    asset: AssetDetailResponse


class HealthResponse(BaseModel):
    status: str
    database: bool
    assets_directory: bool
    ffmpeg: bool
    gemini_configured: bool
