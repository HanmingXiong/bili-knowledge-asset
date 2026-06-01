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
    transcript_chunks: list[TranscriptChunkResponse] = Field(default_factory=list)
    keyframes: list[KeyframeResponse] = Field(default_factory=list)
    generated_outputs: list[GeneratedOutputResponse] = Field(default_factory=list)
    structured_notes: str | None = None
    visual_descriptions: list[dict] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    asset_ids: list[int] = Field(..., min_length=1)
    output_type: str
    user_prompt: str | None = None


class GenerateResponse(BaseModel):
    output: GeneratedOutputResponse


class HealthResponse(BaseModel):
    status: str
