"""
Sources without an RSS feed, reusing the page extractors
already written in `app.research.web_sources`.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

import httpx

from app.ingest.http import get_with_retry
from app.ingest.utils import (
    canonical_url,
    clean_text,
    to_naive_utc,
)
from app.research.web_sources import (
    _extract_anthropic_records,
)
from app.schemas.ingest import IngestedItem

if TYPE_CHECKING:
    from app.ingest.registry import IngestSource


_EXTRACTORS: dict[str, Callable[[str], list[dict[str, Any]]]] = {
    "anthropic": _extract_anthropic_records,
}


async def fetch_scraped(
    client: httpx.AsyncClient,
    source: IngestSource,
    since: datetime,
) -> list[IngestedItem]:
    del since

    extractor = _EXTRACTORS[source.key]

    response = await get_with_retry(
        client,
        source.url,
    )

    items: list[IngestedItem] = []

    for record in extractor(response.text)[: source.max_items]:
        url = record.get("url")
        title = clean_text(record.get("title"))

        if not url or not title:
            continue

        description = clean_text(
            record.get("description")
        )

        items.append(
            IngestedItem(
                source_key=source.key,
                source_name=source.name,
                kind=source.kind,
                category=source.category,
                trust_tier=source.trust_tier,
                url=canonical_url(url),
                title=title,
                summary=description or None,
                authors=(
                    [clean_text(record["author"])]
                    if record.get("author")
                    else []
                ),
                published_at=to_naive_utc(
                    record.get("published_at")
                ),
            )
        )

    return items
