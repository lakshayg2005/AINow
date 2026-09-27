from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, String,ForeignKey,Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from typing import Any, Optional

from app.db.database import Base
from pgvector.sqlalchemy import Vector



class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        nullable=False,
    )  # active, canceled, pending
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

class NewsletterIssue(Base):
    __tablename__ = "newsletter_issues"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    raw_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    html_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        nullable=False,
    )  # draft, published

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

class NewsletterSection(Base):
    __tablename__ = "newsletter_sections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    newsletter_issue_id: Mapped[int] = mapped_column(
        ForeignKey("newsletter_issues.id"),
        nullable=False,
        index=True,
    )

    section_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    # QUICK_NEWS
    # RESEARCH_SPOTLIGHT
    # AI_DEEP_DIVE
    # AI_TRENDS
    # AI_CONCEPT
    # AI_RESOURCES
    # OUR_TAKE
    # SOURCES

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    display_order: Mapped[int] = mapped_column(
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

class AIConcept(Base):
    __tablename__ = "ai_concepts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

class NewsletterConcept(Base):
    __tablename__ = "newsletter_concepts"

    newsletter_issue_id: Mapped[int] = mapped_column(
        ForeignKey("newsletter_issues.id"),
        primary_key=True,
    )

    concept_id: Mapped[int] = mapped_column(
        ForeignKey("ai_concepts.id"),
        primary_key=True,
    )

class ResearchPaper(Base):
    __tablename__ = "research_papers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    authors: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    url: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )

    abstract: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(384),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

class NewsletterPaper(Base):
    __tablename__ = "newsletter_papers"

    newsletter_issue_id: Mapped[int] = mapped_column(
        ForeignKey("newsletter_issues.id"),
        primary_key=True,
    )

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("research_papers.id"),
        primary_key=True,
    )

    is_paper_of_week: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

class AIResource(Base):
    __tablename__ = "ai_resources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    # PRODUCT
    # TOOL
    # GITHUB_REPO
    # MODEL
    # API
    # FRAMEWORK

    url: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

class NewsletterResource(Base):
    __tablename__ = "newsletter_resources"

    newsletter_issue_id: Mapped[int] = mapped_column(
        ForeignKey("newsletter_issues.id"),
        primary_key=True,
    )

    resource_id: Mapped[int] = mapped_column(
        ForeignKey("ai_resources.id"),
        primary_key=True,
    )

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    url: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )

    source_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    raw_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(384),
        nullable=True,
    )

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

class NewsletterSource(Base):
    __tablename__ = "newsletter_sources"

    newsletter_issue_id: Mapped[int] = mapped_column(
        ForeignKey("newsletter_issues.id"),
        primary_key=True,
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id"),
        primary_key=True,
    )

class NewsletterDelivery(Base):
    __tablename__ = "newsletter_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    newsletter_issue_id: Mapped[int] = mapped_column(
        ForeignKey("newsletter_issues.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
    )
    # pending, sent, failed

    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    failed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )


# =========================================================
# INGESTION LAYER
#
# raw_items   : every item fetched from every source,
#               updated in place as signals grow.
# item_chunks : full-text chunks + embeddings (RAG store).
# stories     : clusters of raw_items about the same event.
# ingest_runs : per-run stats for observability.
# =========================================================

class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    title: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    # model_release, research, tool, open_source,
    # industry, policy, benchmark, ...

    importance: Mapped[Optional[int]] = mapped_column(
        nullable=True,
    )

    image_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="open",
        nullable=False,
        index=True,
    )
    # open, covered, archived

    item_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    source_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    signals: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    centroid: Mapped[Optional[list[float]]] = mapped_column(
        Vector(384),
        nullable=True,
    )

    # Versioned names used to join items, e.g. "gemini 3.8".
    entities: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    is_promotional: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    triage_method: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    # "llm:<provider>:<model>" or "heuristic"

    triaged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # item_count when last triaged; re-triage when it grows.
    triaged_item_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )


class RawItem(Base):
    __tablename__ = "raw_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    source_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    source_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    kind: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    # article, paper, repo, model, space, discussion

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    trust_tier: Mapped[int] = mapped_column(
        default=2,
        nullable=False,
    )

    url: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )

    external_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    image_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    discussion_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    authors: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    signals: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    # hn_points, hn_comments, hf_upvotes, stars,
    # likes, downloads, trending_score, ...

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    enrichment_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
        index=True,
    )
    # pending, done, skipped, failed

    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(384),
        nullable=True,
    )

    story_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stories.id"),
        nullable=True,
        index=True,
    )


class ItemChunk(Base):
    __tablename__ = "item_chunks"

    __table_args__ = (
        Index(
            "ix_item_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={
                "m": 16,
                "ef_construction": 64,
            },
            postgresql_ops={
                "embedding": "vector_cosine_ops",
            },
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    raw_item_id: Mapped[int] = mapped_column(
        ForeignKey(
            "raw_items.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(384),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class CoveredStory(Base):
    """
    Memory of what past issues already told readers.

    Checked before selecting stories so an issue never
    repeats an earlier one (except as a genuine update).
    """

    __tablename__ = "covered_stories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Null for entries seeded from issues written before
    # stories existed.
    story_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stories.id"),
        nullable=True,
        index=True,
    )

    newsletter_issue_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("newsletter_issues.id"),
        nullable=True,
        index=True,
    )

    section_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    headline: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    # What we told readers; used to write "what's new" updates.
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    entities: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(384),
        nullable=True,
    )

    covered_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    status: Mapped[str] = mapped_column(
        String(30),
        default="running",
        nullable=False,
    )
    # running, completed, failed

    stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    errors: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

