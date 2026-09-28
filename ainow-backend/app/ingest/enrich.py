from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.ingest.http import get_with_retry
from app.ingest.utils import (
    clean_text,
    parse_iso_datetime,
    truncate,
)
from app.research.web_extract import extract_article_text
from app.schemas.ingest import IngestedItem


ENRICH_CONCURRENCY = 8

# Feed content shorter than this is treated as a teaser and
# the full page is fetched.
MIN_FULL_TEXT = 1500

MAX_CONTENT_CHARS = 30000

# Pages we should never try to scrape as articles.
_SKIP_HOSTS = {
    "news.ycombinator.com",
    "twitter.com",
    "x.com",
    "www.youtube.com",
    "youtube.com",
    "youtu.be",
}

_SKIP_EXTENSIONS = (
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".mp4",
    ".zip",
)


# ============================================================
# Page metadata
# ============================================================

@dataclass
class PageMetadata:
    text: str = ""
    image_url: str | None = None
    description: str | None = None
    published_at: datetime | None = None


def _meta_content(
    soup: BeautifulSoup,
    *names: str,
) -> str | None:
    for name in names:
        node = (
            soup.find("meta", attrs={"property": name})
            or soup.find("meta", attrs={"name": name})
        )

        if node and node.get("content"):
            return str(node["content"]).strip()

    return None


_JSONLD_DATE = re.compile(
    r'"datePublished"\s*:\s*"([^"]+)"'
)


def extract_page_metadata(
    html: str,
    page_url: str,
) -> PageMetadata:
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    image = _meta_content(
        soup,
        "og:image:secure_url",
        "og:image",
        "twitter:image",
        "twitter:image:src",
    )

    if image:
        image = urljoin(
            page_url,
            image,
        )

    published = parse_iso_datetime(
        _meta_content(
            soup,
            "article:published_time",
            "og:article:published_time",
            "date",
            "pubdate",
        )
    )

    if published is None:
        match = _JSONLD_DATE.search(html)

        if match:
            published = parse_iso_datetime(
                match.group(1)
            )

    description = _meta_content(
        soup,
        "og:description",
        "description",
        "twitter:description",
    )

    return PageMetadata(
        text=extract_article_text(html),
        image_url=image,
        description=clean_text(description) or None,
        published_at=published,
    )


# ============================================================
# README cleanup (GitHub / Hugging Face)
# ============================================================

_FRONT_MATTER = re.compile(
    r"\A---\s*\n.*?\n---\s*\n",
    re.DOTALL,
)

_HTML_TAG = re.compile(r"<[^>]+>")

_BADGE_LINE = re.compile(
    r"^\s*(\[!\[|!\[|<img|<a href)",
)


def clean_readme(
    markdown: str,
) -> str:
    markdown = _FRONT_MATTER.sub(
        "",
        markdown,
    )

    lines = [
        _HTML_TAG.sub("", line).rstrip()
        for line in markdown.splitlines()
        if not _BADGE_LINE.match(line)
    ]

    text = "\n".join(lines)

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def _readme_url(
    item: IngestedItem,
) -> str | None:
    if not item.external_id:
        return None

    prefix, _, repo_id = item.external_id.partition(":")

    if prefix == "github":
        return (
            "https://raw.githubusercontent.com/"
            f"{item.title}/HEAD/README.md"
        )

    if prefix == "hf-model":
        return f"https://huggingface.co/{repo_id}/raw/main/README.md"

    if prefix == "hf-space":
        return f"https://huggingface.co/spaces/{repo_id}/raw/main/README.md"

    return None


# ============================================================
# Per-item enrichment
# ============================================================

def _should_fetch_page(
    item: IngestedItem,
) -> bool:
    parsed = urlparse(item.url)

    if parsed.netloc in _SKIP_HOSTS:
        return False

    if parsed.path.lower().endswith(_SKIP_EXTENSIONS):
        return False

    return (
        len(item.content or "") < MIN_FULL_TEXT
        or not item.image_url
        or item.published_at is None
    )


async def _enrich_article(
    client: httpx.AsyncClient,
    item: IngestedItem,
) -> str:
    if not _should_fetch_page(item):
        return "skipped"

    response = await get_with_retry(
        client,
        item.url,
        attempts=2,
    )

    if "html" not in response.headers.get("content-type", ""):
        return "skipped"

    meta = extract_page_metadata(
        response.text,
        str(response.url),
    )

    if len(meta.text) > len(item.content or ""):
        item.content = meta.text[:MAX_CONTENT_CHARS]

    item.image_url = item.image_url or meta.image_url
    item.published_at = item.published_at or meta.published_at

    if not item.summary and meta.description:
        item.summary = truncate(
            meta.description,
            1000,
        )

    return "done"


async def _enrich_readme(
    client: httpx.AsyncClient,
    item: IngestedItem,
) -> str:
    url = _readme_url(item)

    if url is None:
        return "skipped"

    try:
        response = await get_with_retry(
            client,
            url,
            attempts=2,
        )
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            return "skipped"
        raise

    readme = clean_readme(response.text)

    if readme:
        item.content = readme[:MAX_CONTENT_CHARS]

    return "done"


async def enrich_item(
    client: httpx.AsyncClient,
    item: IngestedItem,
) -> str:
    """
    Fill in full text, image, date and summary in place.

    Returns the enrichment status: done, skipped or failed.
    """

    try:
        if item.kind in ("article", "discussion"):
            return await _enrich_article(
                client,
                item,
            )

        if item.kind in ("repo", "model", "space"):
            return await _enrich_readme(
                client,
                item,
            )

        return "skipped"

    except httpx.HTTPStatusError as error:
        # 401/403/402 are paywalls and bot walls; expected.
        print(
            f"[Enrich] HTTP {error.response.status_code}: {item.url}"
        )
        return "failed"

    except Exception as error:
        print(
            f"[Enrich] {type(error).__name__}: {item.url}"
        )
        return "failed"


async def enrich_items(
    client: httpx.AsyncClient,
    items: list[IngestedItem],
) -> dict[str, str]:
    """
    Enrich items concurrently. Returns {url: status}.
    """

    semaphore = asyncio.Semaphore(
        ENRICH_CONCURRENCY
    )

    async def run(
        item: IngestedItem,
    ) -> tuple[str, str]:
        async with semaphore:
            return (
                item.url,
                await enrich_item(
                    client,
                    item,
                ),
            )

    results = await asyncio.gather(
        *(run(item) for item in items)
    )

    return dict(results)
