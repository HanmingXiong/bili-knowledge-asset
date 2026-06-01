from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bvid: Mapped[str] = mapped_column(Text, unique=True, index=True)
    aid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploader: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    transcript_chunks: Mapped[list["TranscriptChunk"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )
    keyframes: Mapped[list["Keyframe"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="transcript_chunks")


class Keyframe(Base):
    __tablename__ = "keyframes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    timestamp: Mapped[float] = mapped_column(Float)
    file_path: Mapped[str] = mapped_column(Text)
    visual_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset: Mapped[Asset] = relationship(back_populates="keyframes")


class GeneratedOutput(Base):
    __tablename__ = "generated_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_ids: Mapped[str] = mapped_column(Text)
    output_type: Mapped[str] = mapped_column(Text)
    user_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
