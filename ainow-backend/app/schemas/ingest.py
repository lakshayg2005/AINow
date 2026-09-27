from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ItemKind = Literal[
    "article",
    "paper",
    "repo",
    "model",
    "space",
    "discussion",
]


class IngestedItem(BaseModel):
    """
    One item produced by a source fetcher, before it is
    written to `raw_items`.
    """

    source_key: str
    source_name: str
    kind: ItemKind
    category: str
    trust_tier: int = Field(
        default=2,
        ge=1,
        le=3,
    )

    url: str
    title: str

    # Stable cross-source identity, e.g. "arxiv:2609.28603"
    # or "github:owner/repo". Lets two sources that link to
    # different URLs for the same thing merge into one row.
    external_id: str | None = None

    summary: str | None = None
    content: str | None = None
    image_url: str | None = None
    discussion_url: str | None = None

    authors: list[str] = Field(
        default_factory=list
    )

    tags: list[str] = Field(
        default_factory=list
    )

    # Engagement signals, e.g. {"hn_points": 412}.
    signals: dict[str, float] = Field(
        default_factory=dict
    )

    # Naive UTC, matching the rest of the database.
    published_at: datetime | None = None
