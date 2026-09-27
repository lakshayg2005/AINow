from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import feedparser
import httpx

from app.ingest.http import get_with_retry
from app.ingest.utils import (
    canonical_url,
    clean_text,
    external_id_for_url,
    first_image_in_html,
    html_to_text,
    truncate,
)
from app.schemas.ingest import IngestedItem

if TYPE_CHECKING:
    from app.ingest.registry import IngestSource


# ============================================================
# Entry helpers
# ============================================================

def _entry_datetime(
    entry: Any,
) -> datetime | None:
    for key in (
        "published_parsed",
        "updated_parsed",
    ):
        value = entry.get(key)

        if value:
            # feedparser normalizes struct_time to UTC.
            return datetime.fromtimestamp(
                calendar.timegm(value),
                timezone.utc,
            ).replace(
                tzinfo=None
            )

    return None


def _entry_image(
    entry: Any,
    content_html: str,
    summary_html: str,
) -> str | None:
    for key in (
        "media_content",
        "media_thumbnail",
    ):
        for media in entry.get(key) or []:
            url = media.get("url")
            medium = media.get("medium", "image")

            if url and medium == "image":
                return url

    for enclosure in entry.get("enclosures") or []:
        if str(
            enclosure.get("type", "")
        ).startswith("image"):
            return enclosure.get("href")

    return (
        first_image_in_html(content_html)
        or first_image_in_html(summary_html)
    )


def parse_feed(
    source: IngestSource,
    body: str,
) -> list[IngestedItem]:
    feed = feedparser.parse(body)

    items: list[IngestedItem] = []

    for entry in feed.entries[: source.max_items]:
        link = entry.get("link")
        title = clean_text(
            entry.get("title")
        )

        if not link or not title:
            continue

        content_html = ""

        if entry.get("content"):
            content_html = entry["content"][0].get(
                "value",
                "",
            )

        summary_html = entry.get(
            "summary",
            "",
        )

        content = html_to_text(content_html)
        summary = html_to_text(summary_html)

        # Some feeds put the full post in <description>.
        if not content and len(summary) > 1500:
            content = summary

        authors = [
            clean_text(author.get("name"))
            for author in entry.get("authors") or []
            if author.get("name")
        ]

        tags = [
            clean_text(tag.get("term"))
            for tag in entry.get("tags") or []
            if tag.get("term")
        ]

        url = canonical_url(link)

        items.append(
            IngestedItem(
                source_key=source.key,
                source_name=source.name,
                kind=source.kind,
                category=source.category,
                trust_tier=source.trust_tier,
                url=url,
                external_id=external_id_for_url(url),
                title=title,
                summary=truncate(summary, 1000) or None,
                content=content or None,
                image_url=_entry_image(
                    entry,
                    content_html,
                    summary_html,
                ),
                authors=authors,
                tags=tags[:10],
                published_at=_entry_datetime(entry),
            )
        )

    return items


# ============================================================
# Fetcher
# ============================================================

async def fetch_rss(
    client: httpx.AsyncClient,
    source: IngestSource,
    since: datetime,
) -> list[IngestedItem]:
    del since

    response = await get_with_retry(
        client,
        source.url,
    )

    return parse_feed(
        source,
        response.text,
    )
