from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx

from app.ingest.http import get_with_retry
from app.ingest.utils import (
    canonical_url,
    clean_text,
    external_id_for_url,
    html_to_text,
    parse_iso_datetime,
)
from app.schemas.ingest import IngestedItem

if TYPE_CHECKING:
    from app.ingest.registry import IngestSource


HN_SEARCH = "https://hn.algolia.com/api/v1/search"

# Algolia search is keyword-based, so cast a wide net and let
# the AI filter plus point threshold do the precision work.
HN_QUERIES = (
    "AI",
    "LLM",
    "GPT",
    "OpenAI",
    "Anthropic",
    "Claude",
    "Gemini",
    "DeepSeek",
    "Qwen",
    "Llama",
    "Mistral",
    "agents",
    "machine learning",
    "neural",
    "model",
)

HN_MIN_POINTS = 40


def hn_hit_to_item(
    source: IngestSource,
    hit: dict[str, Any],
) -> IngestedItem | None:
    object_id = hit.get("objectID")
    title = clean_text(hit.get("title"))

    if not object_id or not title:
        return None

    discussion_url = (
        f"https://news.ycombinator.com/item?id={object_id}"
    )

    link = hit.get("url")
    url = canonical_url(link or discussion_url)

    return IngestedItem(
        source_key=source.key,
        source_name=source.name,
        kind=(
            "article"
            if link
            else "discussion"
        ),
        category=source.category,
        trust_tier=source.trust_tier,
        url=url,
        external_id=external_id_for_url(url),
        title=title,
        # story_text is HTML (often just a link for launch posts).
        summary=html_to_text(hit.get("story_text"))[:1000] or None,
        discussion_url=discussion_url,
        authors=(
            [hit["author"]]
            if hit.get("author")
            else []
        ),
        signals={
            "hn_points": float(hit.get("points") or 0),
            "hn_comments": float(hit.get("num_comments") or 0),
        },
        published_at=parse_iso_datetime(
            hit.get("created_at")
        ),
    )


async def fetch_hackernews(
    client: httpx.AsyncClient,
    source: IngestSource,
    since: datetime,
) -> list[IngestedItem]:
    since_ts = int(
        since.replace(
            tzinfo=timezone.utc
        ).timestamp()
    )

    hits: dict[str, dict[str, Any]] = {}

    for query in HN_QUERIES:
        response = await get_with_retry(
            client,
            HN_SEARCH,
            params={
                "query": query,
                "tags": "story",
                "numericFilters": (
                    f"created_at_i>{since_ts},"
                    f"points>={HN_MIN_POINTS}"
                ),
                "hitsPerPage": source.max_items,
            },
        )

        for hit in response.json().get("hits", []):
            hits.setdefault(
                hit.get("objectID"),
                hit,
            )

    items = [
        hn_hit_to_item(
            source,
            hit,
        )
        for hit in hits.values()
    ]

    return [
        item
        for item in items
        if item is not None
    ]
