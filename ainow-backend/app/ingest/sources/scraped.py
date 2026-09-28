"""
Sources without an RSS feed: their listing pages are
scraped for article links, titles, dates and teasers.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from app.ingest.http import get_with_retry
from app.ingest.utils import (
    canonical_url,
    clean_text,
    parse_iso_datetime,
    to_naive_utc,
)
from app.schemas.ingest import IngestedItem

if TYPE_CHECKING:
    from app.ingest.registry import IngestSource


# ============================================================
# Page helpers
# ============================================================

_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)

_DATE_IN_TEXT = re.compile(
    rf"\b{_MONTH}\s+\d{{1,2}},\s+\d{{4}}\b",
    re.IGNORECASE,
)

_HEADINGS = ["h1", "h2", "h3", "h4"]


def parse_page_date(
    value: str | None,
) -> datetime | None:
    """ISO timestamps, or the first "Mon D, YYYY" in the text."""

    value = clean_text(value)

    if not value:
        return None

    parsed = parse_iso_datetime(value)

    if parsed is not None:
        return parsed

    match = _DATE_IN_TEXT.search(value)

    if match is None:
        return None

    text = re.sub(r"\bSept\b", "Sep", match.group(0), flags=re.IGNORECASE)

    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def _card_for(
    link: Tag,
    max_levels: int = 8,
) -> Tag | None:
    """The nearest enclosing article/li/section of a link."""

    node = link

    for _ in range(max_levels):
        if node.parent is None:
            break

        node = node.parent

        if node.name in ("article", "li", "section"):
            return node

    return node if isinstance(node, Tag) else None


def _heading_for(
    link: Tag,
) -> str:
    """A heading inside the link, else in its parent."""

    for scope in (link, link.parent):
        if scope is None:
            continue

        heading = scope.find(_HEADINGS)

        if heading is not None:
            return clean_text(heading.get_text(" ", strip=True))

    return ""


# ============================================================
# Anthropic
# ============================================================

_ANTHROPIC_HOST = "www.anthropic.com"

_ANTHROPIC_LABEL = re.compile(
    r"^(?:Announcements|Product|Research|Features|Policy|Science|"
    r"Economic Research|Societal Impacts|Interpretability|Alignment)\s+",
    re.IGNORECASE,
)

_LEADING_DATE = re.compile(
    rf"^{_MONTH}\s+\d{{1,2}},\s+\d{{4}}\s+",
    re.IGNORECASE,
)

_NOT_TITLES = {"read more", "learn more", "view all"}


def extract_anthropic_records(
    html: str,
) -> list[dict[str, Any]]:
    """Article cards on anthropic.com/news."""

    soup = BeautifulSoup(html, "html.parser")

    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        url = urljoin(f"https://{_ANTHROPIC_HOST}", str(link["href"]).strip())
        parsed = urlparse(url)

        if parsed.netloc.lower() != _ANTHROPIC_HOST:
            continue

        if not parsed.path.startswith("/news/") or url in seen:
            continue

        # Cards prefix titles with a category and a date, in
        # either order.
        title = _heading_for(link) or clean_text(link.get_text(" ", strip=True))

        for _ in range(2):
            title = _ANTHROPIC_LABEL.sub("", title)
            title = _LEADING_DATE.sub("", title).strip()

        if len(title) > 180:
            title = clean_text(
                re.split(r"\s{2,}|(?<=[.!?])\s+(?=[A-Z])", title, maxsplit=1)[0]
            )

        if len(title) < 10 or title.lower() in _NOT_TITLES:
            continue

        card = _card_for(link)
        published_at = None
        description = ""

        if card is not None:
            time_node = card.find("time")

            if time_node is not None:
                published_at = parse_page_date(
                    time_node.get("datetime")
                    or time_node.get_text(" ", strip=True)
                )

            if published_at is None:
                published_at = parse_page_date(card.get_text(" ", strip=True))

            for paragraph in card.find_all("p"):
                text = clean_text(paragraph.get_text(" ", strip=True))

                if len(text) >= 20 and text.lower() != title.lower():
                    description = text
                    break

        seen.add(url)

        records.append(
            {
                "title": title,
                "description": description,
                "url": url,
                "published_at": published_at,
                "author": "",
            }
        )

    return records


# ============================================================
# Fetch
# ============================================================

_EXTRACTORS: dict[str, Callable[[str], list[dict[str, Any]]]] = {
    "anthropic": extract_anthropic_records,
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
