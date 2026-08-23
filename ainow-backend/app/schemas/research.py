from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ResearchCategory = Literal[
    "company",
    "research",
    "leaderboard",
    "news",
    "tools",
    "open-source",
    "technical",
]


class ResearchSource(BaseModel):
    name: str
    category: ResearchCategory

    trust_tier: int = Field(
        default=2,
        ge=1,
        le=3,
    )

    lookback_days: int = Field(
        default=7,
        ge=1,
    )

    topics: list[str] = Field(
        default_factory=list
    )

    enabled: bool = True


class ResearchCandidate(BaseModel):
    title: str
    url: str
    source_name: str
    category: ResearchCategory
    raw_content: str

    published_at: datetime | None = None

    trust_tier: int = Field(
        default=2,
        ge=1,
        le=3,
    )

    topics: list[str] = Field(
        default_factory=list
    )

    citation_count: int = 0

    authors: list[str] = Field(
        default_factory=list
    )

    # How many independent sources
    # confirmed this candidate?
    cross_source_count: int = 1

    # Example:
    # ["arXiv", "Crossref"]
    supporting_sources: list[str] = Field(
        default_factory=list
    )


class ResearchResult(BaseModel):
    candidate: ResearchCandidate

    is_fresh: bool

    duplicate_reason: str | None = None

    existing_source_id: int | None = None

    semantic_distance: float | None = None


class RankedCandidate(BaseModel):
    candidate: ResearchCandidate
    score: float

    reasons: list[str] = Field(
        default_factory=list
    )


class ResearchPlan(BaseModel):
    topic: str

    queries: list[str] = Field(
        default_factory=list
    )

    lookback_days: int = 7

class EditorialSelection(BaseModel):
    selected_candidate_indices: list[int] = Field(
        default_factory=list
    )

    research_spotlight_indices: list[int] = Field(
        default_factory=list
    )

    paper_of_week_index: int | None = None

    deep_dive_index: int | None = None

    trend_indices: list[int] = Field(
        default_factory=list
    )

    reasoning: str = ""