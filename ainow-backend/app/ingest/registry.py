from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable

import httpx

from app.ingest.sources.arxiv import fetch_arxiv
from app.ingest.sources.feeds import fetch_rss
from app.ingest.sources.github import fetch_github
from app.ingest.sources.hackernews import fetch_hackernews
from app.ingest.sources.huggingface import (
    fetch_hf_daily_papers,
    fetch_hf_trending,
)
from app.ingest.sources.scraped import fetch_scraped
from app.schemas.ingest import IngestedItem, ItemKind


Fetcher = Callable[
    [httpx.AsyncClient, "IngestSource", datetime],
    Awaitable[list[IngestedItem]],
]


@dataclass(frozen=True)
class IngestSource:
    key: str
    name: str
    fetcher: Fetcher
    kind: ItemKind
    category: str
    trust_tier: int = 2
    url: str | None = None

    # General-topic feeds: keep only AI-related items.
    ai_filter: bool = False

    # Fetch full text / README for new items.
    enrich: bool = True

    max_items: int = 50

    # Overrides the run's lookback window. Trending models
    # and repos stay newsworthy longer than blog posts.
    max_age_days: int | None = None

    enabled: bool = True


def _rss(
    key: str,
    name: str,
    url: str,
    category: str,
    trust_tier: int = 2,
    **kwargs,
) -> IngestSource:
    return IngestSource(
        key=key,
        name=name,
        fetcher=fetch_rss,
        kind="article",
        category=category,
        trust_tier=trust_tier,
        url=url,
        **kwargs,
    )


INGEST_SOURCES: list[IngestSource] = [

    # =====================================================
    # AI LABS / COMPANIES (primary sources)
    # =====================================================

    _rss("openai", "OpenAI", "https://openai.com/news/rss.xml", "company", 1),
    _rss("deepmind", "Google DeepMind", "https://deepmind.google/blog/rss.xml", "company", 1),
    _rss("google_research", "Google Research", "https://research.google/blog/rss/", "company", 1),
    _rss(
        "microsoft_research",
        "Microsoft Research",
        "https://www.microsoft.com/en-us/research/feed/",
        "company",
        1,
        ai_filter=True,
    ),
    _rss("mistral", "Mistral AI", "https://mistral.ai/rss.xml", "company", 1),
    _rss("hf_blog", "Hugging Face Blog", "https://huggingface.co/blog/feed.xml", "open-source", 1),
    _rss(
        "nvidia_dev",
        "NVIDIA Technical Blog",
        "https://developer.nvidia.com/blog/feed",
        "technical",
        1,
        ai_filter=True,
    ),
    _rss("aws_ml", "AWS Machine Learning Blog", "https://aws.amazon.com/blogs/machine-learning/feed/", "technical", 2),
    _rss("bair", "Berkeley AI Research", "https://bair.berkeley.edu/blog/feed.xml", "research", 1),

    IngestSource(
        key="anthropic",
        name="Anthropic",
        fetcher=fetch_scraped,
        kind="article",
        category="company",
        trust_tier=1,
        url="https://www.anthropic.com/news",
    ),

    # =====================================================
    # NEWS
    # =====================================================

    _rss("techcrunch_ai", "TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "news"),
    _rss("verge_ai", "The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "news"),
    _rss("venturebeat_ai", "VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "news"),
    _rss("mittr_ai", "MIT Technology Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed", "news", 1),
    _rss("ars_ai", "Ars Technica AI", "https://arstechnica.com/ai/feed/", "news"),
    _rss("ieee_ai", "IEEE Spectrum AI", "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss", "technical", 1),
    _rss(
        "simonw",
        "Simon Willison",
        "https://simonwillison.net/atom/everything/",
        "technical",
        2,
        ai_filter=True,
    ),

    # =====================================================
    # RESEARCH
    # =====================================================

    IngestSource(
        key="hf_daily_papers",
        name="Hugging Face Daily Papers",
        fetcher=fetch_hf_daily_papers,
        kind="paper",
        category="research",
        trust_tier=1,
        # Abstracts are the content; no page to scrape.
        enrich=False,
        max_items=50,
        # Papers surface on Daily Papers days after arXiv.
        max_age_days=21,
    ),

    # Raw arXiv firehose: high volume, no quality signal.
    # Daily Papers already covers the notable ones.
    IngestSource(
        key="arxiv",
        name="arXiv",
        fetcher=fetch_arxiv,
        kind="paper",
        category="research",
        trust_tier=2,
        enrich=False,
        max_items=100,
        enabled=False,
    ),

    # =====================================================
    # COMMUNITY SIGNAL
    # =====================================================

    IngestSource(
        key="hackernews",
        name="Hacker News",
        fetcher=fetch_hackernews,
        kind="article",
        category="news",
        trust_tier=2,
        ai_filter=True,
        max_items=50,
    ),

    # =====================================================
    # OPEN SOURCE
    # =====================================================

    IngestSource(
        key="github",
        name="GitHub",
        fetcher=fetch_github,
        kind="repo",
        category="open-source",
        trust_tier=2,
        max_items=30,
        max_age_days=14,
    ),
    IngestSource(
        key="hf_trending_models",
        name="Hugging Face Trending Models",
        fetcher=fetch_hf_trending,
        kind="model",
        category="open-source",
        trust_tier=1,
        max_items=40,
        max_age_days=30,
    ),
    IngestSource(
        key="hf_trending_spaces",
        name="Hugging Face Trending Spaces",
        fetcher=fetch_hf_trending,
        kind="space",
        category="tools",
        trust_tier=2,
        max_items=30,
        max_age_days=30,
    ),
]


def get_ingest_sources(
    keys: list[str] | None = None,
) -> list[IngestSource]:
    if keys:
        wanted = set(keys)

        unknown = wanted - {
            source.key
            for source in INGEST_SOURCES
        }

        if unknown:
            raise ValueError(
                f"Unknown ingest sources: {sorted(unknown)}"
            )

        # Explicitly requested sources run even if disabled.
        return [
            source
            for source in INGEST_SOURCES
            if source.key in wanted
        ]

    return [
        source
        for source in INGEST_SOURCES
        if source.enabled
    ]
