from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.schemas.research import ResearchCandidate


# ============================================================
# Source configuration
# ============================================================

@dataclass(frozen=True)
class WebSourceConfig:
    name: str
    category: str
    url: str
    mode: str
    trust_tier: int = 1
    fallback_url: str | None = None


WEB_SOURCES: dict[str, WebSourceConfig] = {
    "OpenAI": WebSourceConfig(
        name="OpenAI",
        category="company",
        url="https://openai.com/news/rss.xml",
        mode="rss",
        trust_tier=1,
        fallback_url="https://openai.com/news/",
    ),
    "Google DeepMind": WebSourceConfig(
        name="Google DeepMind",
        category="company",
        url="https://deepmind.google/blog/",
        mode="deepmind",
        trust_tier=1,
    ),
    "Anthropic": WebSourceConfig(
        name="Anthropic",
        category="company",
        url="https://www.anthropic.com/news",
        mode="anthropic",
        trust_tier=1,
    ),
    "NVIDIA": WebSourceConfig(
        name="NVIDIA",
        category="company",
        url="https://nvidianews.nvidia.com/",
        mode="nvidia",
        trust_tier=1,
    ),
    "TechCrunch AI": WebSourceConfig(
        name="TechCrunch AI",
        category="news",
        url="https://techcrunch.com/category/artificial-intelligence/feed/",
        mode="rss",
        trust_tier=2,
    ),
    "MIT Technology Review AI": WebSourceConfig(
        name="MIT Technology Review AI",
        category="news",
        url="https://www.technologyreview.com/feed/",
        mode="rss",
        trust_tier=2,
    ),
    "Artificial Intelligence News": WebSourceConfig(
        name="Artificial Intelligence News",
        category="news",
        url="https://www.artificialintelligence-news.com/",
        mode="ai_news",
        trust_tier=2,
    ),
    "IEEE Spectrum AI": WebSourceConfig(
        name="IEEE Spectrum AI",
        category="technical",
        url="https://spectrum.ieee.org/topic/artificial-intelligence/",
        mode="ieee",
        trust_tier=1,
    ),
    "FutureTools": WebSourceConfig(
        name="FutureTools",
        category="tools",
        url="https://www.futuretools.io/",
        mode="html",
        trust_tier=2,
    ),
    "LMSYS Chatbot Arena": WebSourceConfig(
        name="LMSYS Chatbot Arena",
        category="leaderboard",
        url="https://lmarena.ai/",
        mode="html",
        trust_tier=1,
    ),
    "Artificial Analysis": WebSourceConfig(
        name="Artificial Analysis",
        category="leaderboard",
        url="https://artificialanalysis.ai/leaderboards/models",
        mode="artificial_analysis",
        trust_tier=1,
    ),
    "LLM Stats": WebSourceConfig(
        name="LLM Stats",
        category="leaderboard",
        url="https://llm-stats.com/",
        mode="html",
        trust_tier=2,
    ),
}


# ============================================================
# HTTP
# ============================================================

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36 "
        "AINowResearch/1.0"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml,text/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


async def _fetch(
    url: str,
) -> str:
    timeout = httpx.Timeout(
        connect=10.0,
        read=30.0,
        write=10.0,
        pool=10.0,
    )

    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def _fetch_with_retry(
    url: str,
    attempts: int = 2,
) -> str:
    """
    Retry transient source failures.

    This is especially useful for RSS endpoints such as OpenAI,
    where a temporary connection error should not immediately
    force a fallback to an HTML page that may return 403.
    """

    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return await _fetch(url)

        except Exception as error:
            last_error = error

            print(
                f"[Web] fetch attempt {attempt}/{attempts} failed "
                f"for {url}: "
                f"{type(error).__name__}: {error}"
            )

    if last_error is not None:
        raise last_error

    raise RuntimeError(
        f"Unable to fetch {url}"
    )


# ============================================================
# Helpers
# ============================================================

def _clean_text(
    value: str,
) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )
        return value

    if not isinstance(value, str):
        return None

    value = _clean_text(value)

    if not value:
        return None

    # ISO timestamps.
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except ValueError:
        pass

    # RFC / RSS timestamps.
    formats = (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%a, %d %b %Y %H:%M GMT",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
    )

    for fmt in formats:
        try:
            parsed = datetime.strptime(
                value,
                fmt,
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed

        except ValueError:
            continue

    # Embedded full date.
    match = re.search(
        r"\b"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{1,2},\s+\d{4}"
        r"\b",
        value,
        re.IGNORECASE,
    )

    if match:
        for fmt in (
            "%B %d, %Y",
            "%b %d, %Y",
        ):
            try:
                return datetime.strptime(
                    match.group(0),
                    fmt,
                ).replace(
                    tzinfo=timezone.utc
                )

            except ValueError:
                continue

    return None


def _parse_month_year(
    value: str,
) -> datetime | None:
    value = _clean_text(value)

    for fmt in (
        "%B %Y",
        "%b %Y",
    ):
        try:
            return datetime.strptime(
                value,
                fmt,
            ).replace(
                tzinfo=timezone.utc
            )

        except ValueError:
            continue

    return None


def _within_lookback(
    timestamp: datetime | None,
    lookback_days: int,
) -> bool:
    """
    Keep unknown dates because many HTML listing pages do not
    expose reliable machine-readable timestamps.

    Reject obviously future-dated records and records older than
    the requested lookback window.
    """

    now = datetime.now(timezone.utc)

    if timestamp is None:
        return True

    if timestamp > now + timedelta(hours=24):
        return False

    cutoff = now - timedelta(
        days=lookback_days
    )

    return timestamp >= cutoff


def _safe_description(
    value: Any,
) -> str:
    if value is None:
        return ""

    return _clean_text(
        str(value)
    )


def _same_host(
    url: str,
    host: str,
) -> bool:
    parsed = urlparse(url)

    return (
        parsed.netloc.lower()
        == host.lower()
    )


def _looks_like_content_link(
    url: str,
) -> bool:
    lowered = url.lower()
    parsed = urlparse(url)

    if lowered.startswith(
        (
            "mailto:",
            "javascript:",
            "tel:",
            "#",
        )
    ):
        return False

    excluded = (
        "/about",
        "/contact",
        "/privacy",
        "/terms",
        "/login",
        "/signin",
        "/signup",
        "/subscribe",
        "/careers",
        "/jobs",
        "/search",
        "/press",
        "/rss",
        "/feed",
        "/author/",
        "/tag/",
        "/category/",
        "/categories/",
        "/topic/",
        "/type/",
        "/page/",
        "/blog/page/",
        "/magazine",
        "/file",
        "/st/",
    )

    if any(
        marker in lowered
        for marker in excluded
    ):
        return False

    if parsed.path.lower().endswith(
        (
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".svg",
            ".pdf",
            ".mp4",
            ".mov",
            ".avi",
            ".zip",
        )
    ):
        return False

    return True


def _extract_date_from_text(
    text: str,
) -> datetime | None:
    text = _clean_text(text)

    # Full month/day/year.
    full_date = re.search(
        r"\b"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{1,2},\s+\d{4}"
        r"\b",
        text,
        re.IGNORECASE,
    )

    if full_date:
        parsed = _parse_datetime(
            full_date.group(0)
        )

        if parsed:
            return parsed

    # ISO date.
    iso_date = re.search(
        r"\b\d{4}-\d{2}-\d{2}\b",
        text,
    )

    if iso_date:
        parsed = _parse_datetime(
            iso_date.group(0)
        )

        if parsed:
            return parsed

    # Month/year.
    month_year = re.search(
        r"\b"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{4}"
        r"\b",
        text,
        re.IGNORECASE,
    )

    if month_year:
        return _parse_month_year(
            month_year.group(0)
        )

    return None


def _nearest_container(
    node: Any,
    max_levels: int = 8,
) -> Any:
    current = node

    preferred_names = {
        "article",
        "li",
        "section",
    }

    for _ in range(max_levels):
        parent = getattr(
            current,
            "parent",
            None,
        )

        if parent is None:
            break

        current = parent

        if getattr(
            current,
            "name",
            None,
        ) in preferred_names:
            return current

    return current


def _find_local_heading(
    node: Any,
) -> str:
    """
    Find a heading associated with this exact link.

    Preference:
    1. Heading inside the anchor.
    2. Heading in the immediate parent.
    """

    heading = node.find(
        [
            "h1",
            "h2",
            "h3",
            "h4",
        ]
    )

    if heading:
        return _clean_text(
            heading.get_text(
                " ",
                strip=True,
            )
        )

    parent = node.parent

    if parent is not None:
        headings = parent.find_all(
            [
                "h1",
                "h2",
                "h3",
                "h4",
            ]
        )

        if headings:
            return _clean_text(
                headings[0].get_text(
                    " ",
                    strip=True,
                )
            )

    return ""


def _normalize_model_name(
    slug: str,
) -> str:
    """
    Convert an Artificial Analysis model slug into a
    human-readable model name.

    Examples:
        claude-fable-5-1
            -> Claude Fable 5.1

        claude-fable-5-1-xhigh
            -> Claude Fable 5.1 Xhigh
    """

    slug = unquote(slug)

    name = re.sub(
        r"[-_]+",
        " ",
        slug,
    )

    name = re.sub(
        r"\s+",
        " ",
        name,
    ).strip()

    # 5 1 -> 5.1
    name = re.sub(
        r"\b(\d+)\s+(\d+)\b",
        r"\1.\2",
        name,
    )

    return name.title()


# ============================================================
# RSS / Atom
# ============================================================

def _parse_rss(
    xml_text: str,
) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(
            xml_text
        )

    except ET.ParseError as error:
        print(
            f"[Web] RSS parse failed: {error}"
        )
        return []

    records: list[dict[str, Any]] = []

    # --------------------------------------------------------
    # RSS 2.0
    # --------------------------------------------------------

    for item in root.findall(
        ".//item"
    ):
        title = _clean_text(
            item.findtext("title")
            or ""
        )

        description = _clean_text(
            item.findtext("description")
            or item.findtext("summary")
            or ""
        )

        link = _clean_text(
            item.findtext("link")
            or ""
        )

        published_at = _parse_datetime(
            item.findtext("pubDate")
            or item.findtext("published")
            or item.findtext("updated")
        )

        author = _clean_text(
            item.findtext(
                "{http://purl.org/dc/elements/1.1/}creator"
            )
            or item.findtext("author")
            or ""
        )

        if title and link:
            records.append(
                {
                    "title": title,
                    "description": description,
                    "url": link,
                    "published_at": published_at,
                    "author": author,
                }
            )

    # --------------------------------------------------------
    # Atom
    # --------------------------------------------------------

    if not records:
        namespace = (
            "{http://www.w3.org/2005/Atom}"
        )

        for entry in root.findall(
            f".//{namespace}entry"
        ):
            title = _clean_text(
                entry.findtext(
                    f"{namespace}title"
                )
                or ""
            )

            description = _clean_text(
                entry.findtext(
                    f"{namespace}summary"
                )
                or entry.findtext(
                    f"{namespace}content"
                )
                or ""
            )

            published_at = _parse_datetime(
                entry.findtext(
                    f"{namespace}published"
                )
                or entry.findtext(
                    f"{namespace}updated"
                )
            )

            link = ""

            for link_node in entry.findall(
                f"{namespace}link"
            ):
                rel = link_node.attrib.get(
                    "rel",
                    "alternate",
                )

                href = link_node.attrib.get(
                    "href"
                )

                if href and rel in {
                    "alternate",
                    "",
                }:
                    link = href
                    break

            if title and link:
                records.append(
                    {
                        "title": title,
                        "description": description,
                        "url": link,
                        "published_at": published_at,
                        "author": "",
                    }
                )

    return records


# ============================================================
# Generic HTML extraction
# ============================================================

def _extract_html_records(
    source: WebSourceConfig,
    html_text: str,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    host = urlparse(
        source.url
    ).netloc

    containers = soup.find_all(
        "article"
    )

    if not containers:
        containers = soup.find_all(
            [
                "section",
                "main",
            ]
        )

    def process_link(
        link: Any,
        container: Any,
    ) -> None:
        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        if not href:
            return

        url = urljoin(
            source.url,
            href,
        )

        parsed = urlparse(
            url
        )

        if not _same_host(
            url,
            host,
        ):
            return

        if source.name == "IEEE Spectrum AI":
            if parsed.path.startswith(
                "/magazine"
            ):
                return

        if not _looks_like_content_link(
            url
        ):
            return

        if url in seen_urls:
            return

        title = _clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        if len(title) < 8:
            title = _find_local_heading(
                link
            )

        if len(title) < 8:
            return

        if title.lower() in {
            "news",
            "blog",
            "research",
            "careers",
            "contact",
            "about",
            "subscribe",
            "sign in",
            "log in",
            "press",
            "robotics",
            "sponsored article",
            "sponsored",
            "advertisement",
            "learn more",
            "read more",
            "view all",
            "magazine",
        }:
            return

        description = ""

        for paragraph in container.find_all(
            "p"
        ):
            text = _clean_text(
                paragraph.get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                len(text) >= 25
                and text.lower() != title.lower()
            ):
                description = text
                break

        published_at = None

        time_node = container.find(
            "time"
        )

        if time_node:
            published_at = _parse_datetime(
                time_node.get("datetime")
                or time_node.get_text(
                    " ",
                    strip=True,
                )
            )

        if published_at is None:
            published_at = _extract_date_from_text(
                _clean_text(
                    container.get_text(
                        " ",
                        strip=True,
                    )
                )
            )

        records.append(
            {
                "title": title,
                "description": description,
                "url": url,
                "published_at": published_at,
                "author": "",
            }
        )

        seen_urls.add(url)

    for container in containers:
        for link in container.find_all(
            "a",
            href=True,
        ):
            process_link(
                link,
                container,
            )

    # --------------------------------------------------------
    # Site-wide fallback
    # --------------------------------------------------------

    if len(records) < 3:
        for link in soup.find_all(
            "a",
            href=True,
        ):
            href = str(
                link.get(
                    "href",
                    "",
                )
            ).strip()

            if not href:
                continue

            url = urljoin(
                source.url,
                href,
            )

            parsed = urlparse(
                url
            )

            if not _same_host(
                url,
                host,
            ):
                continue

            if source.name == "IEEE Spectrum AI":
                if parsed.path.startswith(
                    "/magazine"
                ):
                    continue

            if not _looks_like_content_link(
                url
            ):
                continue

            if url in seen_urls:
                continue

            title = _clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(title) < 15:
                title = _find_local_heading(
                    link
                )

            if len(title) < 15:
                continue

            if title.lower() in {
                "news",
                "blog",
                "research",
                "careers",
                "contact",
                "about",
                "subscribe",
                "sign in",
                "log in",
                "press",
                "robotics",
                "sponsored article",
                "sponsored",
                "advertisement",
                "learn more",
                "read more",
                "view all",
                "magazine",
            }:
                continue

            container = _nearest_container(
                link,
                max_levels=6,
            )

            description = ""

            if container is not None:
                paragraph = container.find(
                    "p"
                )

                if paragraph:
                    description = _clean_text(
                        paragraph.get_text(
                            " ",
                            strip=True,
                        )
                    )

            published_at = None

            if container is not None:
                published_at = _extract_date_from_text(
                    _clean_text(
                        container.get_text(
                            " ",
                            strip=True,
                        )
                    )
                )

            records.append(
                {
                    "title": title,
                    "description": description,
                    "url": url,
                    "published_at": published_at,
                    "author": "",
                }
            )

            seen_urls.add(url)

    return records


# ============================================================
# Google DeepMind
# ============================================================

def _extract_deepmind_records(
    html_text: str,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    base_url = "https://deepmind.google"

    for link in soup.find_all(
        "a",
        href=True,
    ):
        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        if not href:
            continue

        url = urljoin(
            base_url,
            href,
        )

        parsed = urlparse(
            url
        )

        path = parsed.path.rstrip(
            "/"
        ).lower()

        if parsed.netloc.lower() not in {
            "deepmind.google",
            "www.deepmind.google",
        }:
            continue

        if not path.startswith(
            "/blog/"
        ):
            continue

        if re.match(
            r"^/blog/page/\d+$",
            path,
        ):
            continue

        if path in {
            "/blog",
            "/blog/",
        }:
            continue

        if not _looks_like_content_link(
            url
        ):
            continue

        if url in seen_urls:
            continue

        container = _nearest_container(
            link,
            max_levels=8,
        )

        title = _find_local_heading(
            link
        )

        if not title:
            title = _clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

        if len(title) < 8:
            continue

        if title.lower() in {
            "read more",
            "learn more",
            "view all",
            "explore",
        }:
            continue

        description = ""

        if container is not None:
            for paragraph in container.find_all(
                "p"
            ):
                text = _clean_text(
                    paragraph.get_text(
                        " ",
                        strip=True,
                    )
                )

                if (
                    len(text) >= 30
                    and text.lower() != title.lower()
                ):
                    description = text
                    break

        published_at = None

        if container is not None:
            time_node = container.find(
                "time"
            )

            if time_node:
                published_at = _parse_datetime(
                    time_node.get(
                        "datetime"
                    )
                    or time_node.get_text(
                        " ",
                        strip=True,
                    )
                )

            if published_at is None:
                published_at = _extract_date_from_text(
                    _clean_text(
                        container.get_text(
                            " ",
                            strip=True,
                        )
                    )
                )

        records.append(
            {
                "title": title,
                "description": description,
                "url": url,
                "published_at": published_at,
                "author": "",
            }
        )

        seen_urls.add(url)

    return records


# ============================================================
# Anthropic
# ============================================================

def _extract_anthropic_records(
    html_text: str,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    base_url = "https://www.anthropic.com"

    for link in soup.find_all(
        "a",
        href=True,
    ):
        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        if not href:
            continue

        url = urljoin(
            base_url,
            href,
        )

        parsed = urlparse(
            url
        )

        if parsed.netloc.lower() != (
            "www.anthropic.com"
        ):
            continue

        if not parsed.path.startswith(
            "/news/"
        ):
            continue

        if url in seen_urls:
            continue

        container = _nearest_container(
            link,
            max_levels=8,
        )

        title = _find_local_heading(
            link
        )

        if not title:
            title = _clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

        title = re.sub(
            r"^(Announcements|Product|Research|Features|Economic Research)\s+",
            "",
            title,
            flags=re.IGNORECASE,
        )

        title = re.sub(
            r"^(?:"
            r"Jan(?:uary)?|"
            r"Feb(?:ruary)?|"
            r"Mar(?:ch)?|"
            r"Apr(?:il)?|"
            r"May|"
            r"Jun(?:e)?|"
            r"Jul(?:y)?|"
            r"Aug(?:ust)?|"
            r"Sep(?:tember)?|"
            r"Oct(?:ober)?|"
            r"Nov(?:ember)?|"
            r"Dec(?:ember)?"
            r")\s+\d{1,2},\s+\d{4}\s+",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

        if len(title) > 180:
            split_candidates = re.split(
                r"\s{2,}|(?<=[.!?])\s+(?=[A-Z])",
                title,
                maxsplit=1,
            )

            if split_candidates:
                title = _clean_text(
                    split_candidates[0]
                )

        if len(title) < 10:
            continue

        if title.lower() in {
            "read more",
            "learn more",
            "view all",
        }:
            continue

        published_at = None

        if container is not None:
            time_node = container.find(
                "time"
            )

            if time_node:
                published_at = _parse_datetime(
                    time_node.get(
                        "datetime"
                    )
                    or time_node.get_text(
                        " ",
                        strip=True,
                    )
                )

            if published_at is None:
                published_at = _extract_date_from_text(
                    _clean_text(
                        container.get_text(
                            " ",
                            strip=True,
                        )
                    )
                )

        description = ""

        if container is not None:
            for paragraph in container.find_all(
                "p"
            ):
                text = _clean_text(
                    paragraph.get_text(
                        " ",
                        strip=True,
                    )
                )

                if not text:
                    continue

                if text.lower() == title.lower():
                    continue

                if len(text) < 20:
                    continue

                description = text
                break

        records.append(
            {
                "title": title,
                "description": description,
                "url": url,
                "published_at": published_at,
                "author": "",
            }
        )

        seen_urls.add(url)

    return records


# ============================================================
# NVIDIA
# ============================================================

def _extract_nvidia_records(
    html_text: str,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    base_url = "https://nvidianews.nvidia.com"
    host = "nvidianews.nvidia.com"

    for link in soup.find_all(
        "a",
        href=True,
    ):
        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        if not href:
            continue

        url = urljoin(
            base_url,
            href,
        )

        parsed = urlparse(
            url
        )

        if parsed.netloc.lower() != host:
            continue

        if parsed.path == "/file":
            continue

        if not _looks_like_content_link(
            url
        ):
            continue

        if url in seen_urls:
            continue

        container = _nearest_container(
            link,
            max_levels=8,
        )

        title = _find_local_heading(
            link
        )

        if not title:
            title = _clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

        if len(title) < 15:
            continue

        if title.lower() in {
            "newsroom",
            "press room",
            "subscribe",
            "contact us",
            "about",
            "read more",
            "learn more",
            "view all",
        }:
            continue

        description = ""

        if container is not None:
            for paragraph in container.find_all(
                "p"
            ):
                text = _clean_text(
                    paragraph.get_text(
                        " ",
                        strip=True,
                    )
                )

                if (
                    len(text) >= 25
                    and text.lower() != title.lower()
                ):
                    description = text
                    break

        published_at = None

        if container is not None:
            time_node = container.find(
                "time"
            )

            if time_node:
                published_at = _parse_datetime(
                    time_node.get(
                        "datetime"
                    )
                    or time_node.get_text(
                        " ",
                        strip=True,
                    )
                )

            if published_at is None:
                published_at = _extract_date_from_text(
                    _clean_text(
                        container.get_text(
                            " ",
                            strip=True,
                        )
                    )
                )

        records.append(
            {
                "title": title,
                "description": description,
                "url": url,
                "published_at": published_at,
                "author": "",
            }
        )

        seen_urls.add(url)

    return records


# ============================================================
# Artificial Intelligence News
# ============================================================

def _extract_ai_news_records(
    html_text: str,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    base_url = (
        "https://www.artificialintelligence-news.com"
    )
    host = (
        "www.artificialintelligence-news.com"
    )

    for link in soup.find_all(
        "a",
        href=True,
    ):
        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        if not href:
            continue

        url = urljoin(
            base_url,
            href,
        )

        parsed = urlparse(
            url
        )

        if parsed.netloc.lower() != host:
            continue

        path = parsed.path.rstrip(
            "/"
        )

        # Only actual news articles.
        if not path.startswith(
            "/news/"
        ):
            continue

        # Reject known non-article routes.
        if path in {
            "/news",
            "/news/videos",
            "/news/video",
        }:
            continue

        # Reject deeper utility/navigation routes.
        if path.startswith(
            "/news/videos/"
        ):
            continue

        if url in seen_urls:
            continue

        container = _nearest_container(
            link,
            max_levels=8,
        )

        title = _find_local_heading(
            link
        )

        if not title:
            title = _clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

        if len(title) < 15:
            continue

        if title.lower() in {
            "read more",
            "learn more",
            "view all",
            "news",
            "video interviews",
        }:
            continue

        description = ""

        if container is not None:
            for paragraph in container.find_all(
                "p"
            ):
                text = _clean_text(
                    paragraph.get_text(
                        " ",
                        strip=True,
                    )
                )

                if (
                    len(text) >= 25
                    and text.lower() != title.lower()
                ):
                    description = text
                    break

        published_at = None

        if container is not None:
            time_node = container.find(
                "time"
            )

            if time_node:
                published_at = _parse_datetime(
                    time_node.get(
                        "datetime"
                    )
                    or time_node.get_text(
                        " ",
                        strip=True,
                    )
                )

            if published_at is None:
                published_at = _extract_date_from_text(
                    _clean_text(
                        container.get_text(
                            " ",
                            strip=True,
                        )
                    )
                )

        records.append(
            {
                "title": title,
                "description": description,
                "url": url,
                "published_at": published_at,
                "author": "",
            }
        )

        seen_urls.add(url)

    return records


# ============================================================
# IEEE Spectrum
# ============================================================

def _extract_ieee_records(
    html_text: str,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    base_url = "https://spectrum.ieee.org"
    host = "spectrum.ieee.org"

    for link in soup.find_all(
        "a",
        href=True,
    ):
        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        if not href:
            continue

        url = urljoin(
            base_url,
            href,
        )

        parsed = urlparse(
            url
        )

        if parsed.netloc.lower() != host:
            continue

        path = parsed.path.rstrip(
            "/"
        ).lower()

        if path.startswith(
            "/st/"
        ):
            continue

        if path.startswith(
            "/magazine"
        ):
            continue

        if path.startswith(
            "/topic/"
        ):
            continue

        if path in {
            "",
            "/",
        }:
            continue

        if not _looks_like_content_link(
            url
        ):
            continue

        if url in seen_urls:
            continue

        container = _nearest_container(
            link,
            max_levels=8,
        )

        title = _find_local_heading(
            link
        )

        if not title:
            title = _clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

        if len(title) < 15:
            continue

        if title.lower() in {
            "magazine",
            "read more",
            "learn more",
            "view all",
        }:
            continue

        description = ""

        if container is not None:
            for paragraph in container.find_all(
                "p"
            ):
                text = _clean_text(
                    paragraph.get_text(
                        " ",
                        strip=True,
                    )
                )

                if (
                    len(text) >= 25
                    and text.lower() != title.lower()
                ):
                    description = text
                    break

        published_at = None

        if container is not None:
            time_node = container.find(
                "time"
            )

            if time_node:
                published_at = _parse_datetime(
                    time_node.get(
                        "datetime"
                    )
                    or time_node.get_text(
                        " ",
                        strip=True,
                    )
                )

            if published_at is None:
                published_at = _extract_date_from_text(
                    _clean_text(
                        container.get_text(
                            " ",
                            strip=True,
                        )
                    )
                )

        records.append(
            {
                "title": title,
                "description": description,
                "url": url,
                "published_at": published_at,
                "author": "",
            }
        )

        seen_urls.add(url)

    return records


# ============================================================
# Artificial Analysis
# ============================================================

def _extract_artificial_analysis_records(
    html_text: str,
) -> list[dict[str, Any]]:
    """
    Conservative HTML fallback.

    Accept only canonical model pages:

        /models/<slug>

    Reject:

        /models/<slug>/providers
        /models/<slug>/anything-else
    """

    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    base_url = (
        "https://artificialanalysis.ai"
    )
    host = "artificialanalysis.ai"

    for link in soup.find_all(
        "a",
        href=True,
    ):
        href = str(
            link.get(
                "href",
                "",
            )
        ).strip()

        if not href:
            continue

        url = urljoin(
            base_url,
            href,
        )

        parsed = urlparse(
            url
        )

        if parsed.netloc.lower() != host:
            continue

        path = parsed.path.rstrip(
            "/"
        )

        parts = [
            part
            for part in path.split("/")
            if part
        ]

        # Must be exactly:
        # /models/<slug>
        if len(parts) != 2:
            continue

        if parts[0].lower() != "models":
            continue

        slug = unquote(
            parts[1]
        ).strip()

        if not slug:
            continue

        if url in seen_urls:
            continue

        title = _clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        # Replace generic navigation labels.
        if title.lower() in {
            "",
            "model",
            "models",
            "providers",
            "view model",
            "details",
        }:
            title = _normalize_model_name(
                slug
            )
        else:
            title = re.sub(
                r"\b(\d+)\s+(\d+)\b",
                r"\1.\2",
                title,
            )

        if len(title) < 3:
            continue

        records.append(
            {
                "title": title,
                "description": "",
                "url": url,
                "published_at": None,
                "author": "",
            }
        )

        seen_urls.add(url)

    return records


# ============================================================
# Candidate conversion
# ============================================================

def _record_to_candidate(
    source: WebSourceConfig,
    record: dict[str, Any],
) -> ResearchCandidate:
    title = _clean_text(
        str(
            record.get("title")
            or source.name
        )
    )

    description = _safe_description(
        record.get("description")
    )

    url = _clean_text(
        str(
            record.get("url")
            or source.url
        )
    )

    published_at = record.get(
        "published_at"
    )

    author = _clean_text(
        str(
            record.get("author")
            or ""
        )
    )

    published_text = (
        published_at.isoformat()
        if published_at
        else "unknown"
    )

    raw_content = (
        f"Source: {source.name}\n"
        f"Title: {title}\n"
        f"Published: {published_text}\n"
        f"URL: {url}\n"
    )

    if author:
        raw_content += (
            f"Author: {author}\n"
        )

    if description:
        raw_content += (
            "\nDescription:\n"
            f"{description}"
        )

    return ResearchCandidate(
        title=title,
        url=url,
        source_name=source.name,
        category=source.category,
        raw_content=raw_content[:12000],
        published_at=published_at,
        trust_tier=source.trust_tier,
        topics=[
            "web",
            source.category,
        ],
        citation_count=0,
        authors=(
            [author]
            if author
            else []
        ),
    )


# ============================================================
# Main web-source search
# ============================================================

async def search_web_source(
    source_name: str,
    query: str,
    lookback_days: int,
    max_results: int = 10,
) -> list[ResearchCandidate]:
    """
    Discover recent candidates from a web source.

    Query filtering deliberately does NOT happen here.
    Relevance filtering belongs to the downstream relevance
    layer so discovery preserves recall.
    """

    del query

    source = WEB_SOURCES.get(
        source_name
    )

    if source is None:
        raise ValueError(
            f"Unsupported web source: {source_name}"
        )

    # --------------------------------------------------------
    # Fetch
    # --------------------------------------------------------

    try:
        # Retry RSS sources more aggressively.
        fetch_attempts = (
            2
            if source.mode == "rss"
            else 1
        )

        body = await _fetch_with_retry(
            source.url,
            attempts=fetch_attempts,
        )

    except Exception as error:
        print(
            f"[Web] {source_name} primary fetch failed "
            f"after retry: "
            f"{type(error).__name__}: {error}"
        )

        if not source.fallback_url:
            return []

        try:
            print(
                f"[Web] {source_name}: "
                f"trying fallback URL"
            )

            body = await _fetch_with_retry(
                source.fallback_url,
                attempts=1,
            )

        except Exception as fallback_error:
            print(
                f"[Web] {source_name} fallback failed: "
                f"{type(fallback_error).__name__}: "
                f"{fallback_error}"
            )

            return []

    # --------------------------------------------------------
    # Extraction
    # --------------------------------------------------------

    try:
        if source.mode == "rss":
            records = _parse_rss(
                body
            )

            if not records:
                soup = BeautifulSoup(
                    body,
                    "html.parser",
                )

                if soup.find("html"):
                    records = _extract_html_records(
                        source,
                        body,
                    )

        elif source.mode == "deepmind":
            records = _extract_deepmind_records(
                body
            )

        elif source.mode == "anthropic":
            records = _extract_anthropic_records(
                body
            )

        elif source.mode == "nvidia":
            records = _extract_nvidia_records(
                body
            )

        elif source.mode == "ai_news":
            records = _extract_ai_news_records(
                body
            )

        elif source.mode == "ieee":
            records = _extract_ieee_records(
                body
            )

        elif source.mode == "artificial_analysis":
            records = _extract_artificial_analysis_records(
                body
            )

        else:
            records = _extract_html_records(
                source,
                body,
            )

        # ----------------------------------------------------
        # Convert and normalize
        # ----------------------------------------------------

        candidates: list[ResearchCandidate] = []
        seen_keys: set[str] = set()

        for record in records:
            published_at = record.get(
                "published_at"
            )

            if not _within_lookback(
                published_at,
                lookback_days,
            ):
                continue

            candidate = _record_to_candidate(
                source,
                record,
            )

            dedup_key = (
                candidate.url.rstrip("/")
                .lower()
            )

            if dedup_key in seen_keys:
                continue

            seen_keys.add(
                dedup_key
            )

            candidates.append(
                candidate
            )

            if len(candidates) >= max_results:
                break

        print(
            f"[Web] {source_name}: "
            f"{len(candidates)} candidates"
        )

        return candidates

    except Exception as error:
        print(
            f"[Web] {source_name} extraction failed: "
            f"{type(error).__name__}: {error}"
        )

        return []