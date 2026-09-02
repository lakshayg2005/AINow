from __future__ import annotations

import json
import re
from typing import Iterable

import httpx
from bs4 import BeautifulSoup


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
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


async def fetch_web_page(
    url: str,
) -> str:
    timeout = httpx.Timeout(
        connect=10.0,
        read=30.0,
        write=10.0,
        pool=10.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


# ============================================================
# Cleaning
# ============================================================

_BOILERPLATE_SELECTORS = (
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
    "canvas",
    ".advertisement",
    ".advert",
    ".ads",
    ".cookie",
    ".cookies",
    ".newsletter",
    ".subscribe",
    ".social-share",
    ".share",
    ".related",
    ".recommended",
    ".comments",
    "#comments",
    ".sidebar",
    ".site-header",
    ".site-footer",
)


def _clean_text(
    value: str,
) -> str:
    value = re.sub(
        r"\s+",
        " ",
        value or "",
    )

    return value.strip()


def _remove_boilerplate(
    soup: BeautifulSoup,
) -> None:
    for selector in _BOILERPLATE_SELECTORS:
        for node in soup.select(
            selector
        ):
            node.decompose()


# ============================================================
# JSON-LD helpers
# ============================================================

def _extract_jsonld_article(
    soup: BeautifulSoup,
) -> dict:
    for script in soup.find_all(
        "script",
        type="application/ld+json",
    ):
        raw = script.string

        if not raw:
            raw = script.get_text()

        if not raw:
            continue

        try:
            data = json.loads(
                raw
            )
        except (
            TypeError,
            json.JSONDecodeError,
        ):
            continue

        objects = (
            data
            if isinstance(data, list)
            else [data]
        )

        for obj in objects:
            if not isinstance(
                obj,
                dict,
            ):
                continue

            article_type = obj.get(
                "@type"
            )

            if isinstance(
                article_type,
                list,
            ):
                article_types = {
                    str(value).lower()
                    for value in article_type
                }
            else:
                article_types = {
                    str(article_type).lower()
                }

            if article_types.intersection(
                {
                    "article",
                    "newsarticle",
                    "blogposting",
                }
            ):
                return obj

            graph = obj.get(
                "@graph"
            )

            if isinstance(
                graph,
                list,
            ):
                for graph_item in graph:
                    if not isinstance(
                        graph_item,
                        dict,
                    ):
                        continue

                    graph_type = graph_item.get(
                        "@type",
                        "",
                    )

                    if isinstance(
                        graph_type,
                        list,
                    ):
                        graph_types = {
                            str(value).lower()
                            for value in graph_type
                        }
                    else:
                        graph_types = {
                            str(graph_type).lower()
                        }

                    if graph_types.intersection(
                        {
                            "article",
                            "newsarticle",
                            "blogposting",
                        }
                    ):
                        return graph_item

    return {}


# ============================================================
# Candidate containers
# ============================================================

def _candidate_containers(
    soup: BeautifulSoup,
) -> Iterable:
    selectors = (
        "[itemprop='articleBody']",
        "[itemprop='articleBody'] [itemprop='articleBody']",
        "article",
        "main",
        ".article-body",
        ".article-content",
        ".entry-content",
        ".post-content",
        ".story-body",
        ".content-body",
        ".article__body",
        ".story__body",
        "[class*='article-body']",
        "[class*='article-content']",
        "[class*='articleBody']",
        "[class*='story-body']",
        "[class*='story-content']",
    )

    seen_ids: set[int] = set()

    for selector in selectors:
        for node in soup.select(
            selector
        ):
            node_id = id(node)

            if node_id in seen_ids:
                continue

            seen_ids.add(
                node_id
            )

            yield node


# ============================================================
# Article extraction
# ============================================================

def extract_article_text(
    html: str,
) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    _remove_boilerplate(
        soup
    )

    # --------------------------------------------------------
    # JSON-LD article body
    # --------------------------------------------------------

    jsonld = _extract_jsonld_article(
        soup
    )

    jsonld_body = jsonld.get(
        "articleBody"
    )

    if isinstance(
        jsonld_body,
        str,
    ):
        cleaned = _clean_text(
            jsonld_body
        )

        if len(cleaned) >= 300:
            return cleaned

    # --------------------------------------------------------
    # Semantic article containers
    # --------------------------------------------------------

    best_text = ""

    for container in _candidate_containers(
        soup
    ):
        chunks: list[str] = []
        seen_chunks: set[str] = set()

        for element in container.find_all(
            [
                "p",
                "h2",
                "h3",
                "blockquote",
                "li",
            ]
        ):
            text = _clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(text) < 25:
                continue

            normalized = text.lower()

            if normalized in seen_chunks:
                continue

            seen_chunks.add(
                normalized
            )
            chunks.append(text)

        candidate_text = "\n\n".join(
            chunks
        )

        if len(candidate_text) > len(
            best_text
        ):
            best_text = candidate_text

    # --------------------------------------------------------
    # Paragraph fallback
    # --------------------------------------------------------

    if len(best_text) < 300:
        chunks = []
        seen_chunks: set[str] = set()

        for paragraph in soup.find_all(
            "p"
        ):
            text = _clean_text(
                paragraph.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(text) < 30:
                continue

            normalized = text.lower()

            if normalized in seen_chunks:
                continue

            seen_chunks.add(
                normalized
            )
            chunks.append(text)

        fallback_text = "\n\n".join(
            chunks
        )

        if len(fallback_text) > len(
            best_text
        ):
            best_text = fallback_text

    # --------------------------------------------------------
    # Final cleanup
    # --------------------------------------------------------

    best_text = re.sub(
        r"\n{3,}",
        "\n\n",
        best_text,
    )

    return best_text.strip()


# ============================================================
# Full article fetch
# ============================================================

async def fetch_article_text(
    url: str,
) -> str:
    html = await fetch_web_page(
        url
    )

    return extract_article_text(
        html
    )