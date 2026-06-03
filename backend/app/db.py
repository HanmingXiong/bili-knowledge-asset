from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base

settings = get_settings()
engine = create_engine(f"sqlite:///{settings.db_path}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.assets_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS asset_snippets_fts
                USING fts5(text, content='asset_snippets', content_rowid='id')
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS asset_snippets_ai
                AFTER INSERT ON asset_snippets BEGIN
                  INSERT INTO asset_snippets_fts(rowid, text) VALUES (new.id, new.text);
                END
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS asset_snippets_ad
                AFTER DELETE ON asset_snippets BEGIN
                  INSERT INTO asset_snippets_fts(asset_snippets_fts, rowid, text)
                  VALUES ('delete', old.id, old.text);
                END
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS asset_snippets_au
                AFTER UPDATE ON asset_snippets BEGIN
                  INSERT INTO asset_snippets_fts(asset_snippets_fts, rowid, text)
                  VALUES ('delete', old.id, old.text);
                  INSERT INTO asset_snippets_fts(rowid, text) VALUES (new.id, new.text);
                END
                """
            )
        )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
