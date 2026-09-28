from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

import feedparser
import httpx

from app.ingest.http import get_with_retry
from app.ingest.utils import (
    clean_text,
    parse_iso_datetime,
)
from app.schemas.ingest import IngestedItem

if TYPE_CHECKING:
    from app.ingest.registry import IngestSource


ARXIV_API = "https://export.arxiv.org/api/query"

ARXIV_CATEGORIES = (
    "cs.CL",
    "cs.AI",
    "cs.LG",
)

_VERSION_SUFFIX = re.compile(r"v\d+$")


def parse_arxiv_feed(
    source: IngestSource,
    body: str,
) -> list[IngestedItem]:
    feed = feedparser.parse(body)

    items: list[IngestedItem] = []

    for entry in feed.entries:
        raw_id = str(
            entry.get("id", "")
        ).rsplit("/abs/", 1)[-1]

        arxiv_id = _VERSION_SUFFIX.sub(
            "",
            raw_id,
        )

        title = clean_text(entry.get("title"))
        abstract = clean_text(entry.get("summary"))

        if not arxiv_id or not title:
            continue

        items.append(
            IngestedItem(
                source_key=source.key,
                source_name=source.name,
                kind="paper",
                category=source.category,
                trust_tier=source.trust_tier,
                url=f"https://arxiv.org/abs/{arxiv_id}",
                external_id=f"arxiv:{arxiv_id}",
                title=title,
                summary=abstract[:1000] or None,
                content=abstract or None,
                authors=[
                    clean_text(author.get("name"))
                    for author in entry.get("authors") or []
                    if author.get("name")
                ][:20],
                tags=[
                    tag.get("term")
                    for tag in entry.get("tags") or []
                    if tag.get("term")
                ][:10],
                published_at=parse_iso_datetime(
                    entry.get("published")
                ),
            )
        )

    return items


async def fetch_arxiv(
    client: httpx.AsyncClient,
    source: IngestSource,
    since: datetime,
) -> list[IngestedItem]:
    del since

    query = " OR ".join(
        f"cat:{category}"
        for category in ARXIV_CATEGORIES
    )

    response = await get_with_retry(
        client,
        ARXIV_API,
        params={
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": source.max_items,
        },
    )

    return parse_arxiv_feed(
        source,
        response.text,
    )
