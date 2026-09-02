from __future__ import annotations

import asyncio
from typing import Iterable

from app.research.web_extract import fetch_article_text
from app.schemas.research import ResearchCandidate


# ============================================================
# Configuration
# ============================================================

DEFAULT_MAX_ENRICHMENTS = 12
DEFAULT_CONCURRENCY = 4
MIN_ARTICLE_TEXT_LENGTH = 300


# ============================================================
# Candidate helpers
# ============================================================

def _candidate_copy_with_content(
    candidate: ResearchCandidate,
    article_text: str,
) -> ResearchCandidate:
    """
    Preserve the existing candidate and replace/extend raw_content
    with the full article body.

    Supports Pydantic v2 models.
    """

    existing = candidate.raw_content or ""

    enriched_content = (
        f"{existing}\n\n"
        f"Full article content:\n"
        f"{article_text}"
    )

    return candidate.model_copy(
        update={
            "raw_content": enriched_content[:30000],
        }
    )


async def _enrich_one(
    candidate: ResearchCandidate,
    semaphore: asyncio.Semaphore,
) -> ResearchCandidate:
    async with semaphore:
        try:
            article_text = await fetch_article_text(
                candidate.url
            )

            if not article_text:
                return candidate

            if len(article_text) < MIN_ARTICLE_TEXT_LENGTH:
                return candidate

            return _candidate_copy_with_content(
                candidate,
                article_text,
            )

        except Exception as error:
            print(
                "[Enrichment] failed for "
                f"{candidate.url}: "
                f"{type(error).__name__}: {error}"
            )
            return candidate


# ============================================================
# Public API
# ============================================================

async def enrich_candidates(
    candidates: Iterable[ResearchCandidate],
    max_enrichments: int = DEFAULT_MAX_ENRICHMENTS,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[ResearchCandidate]:
    """
    Fetch full article text for only the top N candidates.

    Candidates beyond max_enrichments are returned unchanged.
    """

    candidate_list = list(candidates)

    if not candidate_list:
        return []

    selected = candidate_list[
        :max(0, max_enrichments)
    ]

    remaining = candidate_list[
        max(0, max_enrichments):
    ]

    semaphore = asyncio.Semaphore(
        max(1, concurrency)
    )

    tasks = [
        _enrich_one(
            candidate,
            semaphore,
        )
        for candidate in selected
    ]

    enriched = await asyncio.gather(
        *tasks
    )

    return enriched + remaining