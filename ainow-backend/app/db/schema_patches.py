"""
Idempotent column additions for tables that already exist.

`Base.metadata.create_all` creates missing tables but never
alters existing ones. Until the project adopts Alembic, new
columns on existing tables are added here.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.database import Base
from app.db import models  # noqa: F401  (registers tables)


PATCHES = (
    "ALTER TABLE stories ADD COLUMN IF NOT EXISTS entities JSONB NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE stories ADD COLUMN IF NOT EXISTS is_promotional BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE stories ADD COLUMN IF NOT EXISTS triage_method VARCHAR(100)",
    "ALTER TABLE stories ADD COLUMN IF NOT EXISTS triaged_at TIMESTAMP",
    "ALTER TABLE stories ADD COLUMN IF NOT EXISTS triaged_item_count INTEGER NOT NULL DEFAULT 0",
)


def ensure_schema(
    engine: Engine,
) -> None:
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        for statement in PATCHES:
            connection.execute(text(statement))
