from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup


# ============================================================
# Time
# ============================================================

def utcnow() -> datetime:
    """
    Naive UTC, matching the `datetime.utcnow` defaults
    used by the database models.
    """

    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


def to_naive_utc(
    value: datetime | None,
) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is not None:
        value = value.astimezone(
            timezone.utc
        ).replace(
            tzinfo=None
        )

    return value


def parse_iso_datetime(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    try:
        return to_naive_utc(
            datetime.fromisoformat(
                value.strip().replace(
                    "Z",
                    "+00:00",
                )
            )
        )
    except ValueError:
        return None


# ============================================================
# URLs
# ============================================================

_TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
    "guccounter",
}


def canonical_url(
    url: str,
) -> str:
    """
    Normalize a URL so the same page fetched from two
    sources maps to one row.

    Drops fragments, tracking parameters and trailing
    slashes, and lowercases the host.
    """

    parsed = urlparse(
        url.strip()
    )

    query = [
        (key, value)
        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=False,
        )
        if not key.lower().startswith("utm_")
        and key.lower() not in _TRACKING_PARAMS
    ]

    path = parsed.path or "/"

    if len(path) > 1:
        path = path.rstrip("/")

    return urlunparse(
        (
            parsed.scheme.lower() or "https",
            parsed.netloc.lower(),
            path,
            "",
            urlencode(query),
            "",
        )
    )


_ARXIV_URL = re.compile(
    r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})",
)

_HF_PAPER_URL = re.compile(
    r"huggingface\.co/papers/(\d{4}\.\d{4,5})",
)

_GITHUB_REPO_URL = re.compile(
    r"^https?://github\.com/([\w.-]+)/([\w.-]+)/?$",
)

_HF_REPO_URL = re.compile(
    r"^https?://huggingface\.co/(spaces/)?([\w.-]+)/([\w.-]+)/?$",
)

_HF_RESERVED = {
    "papers",
    "blog",
    "datasets",
    "docs",
    "learn",
    "models",
    "spaces",
    "collections",
}


def external_id_for_url(
    url: str,
) -> str | None:
    """
    Derive the cross-source id for links to papers, repos
    and models, so e.g. an HN post linking to an arXiv paper
    merges with the Daily Papers entry for it.
    """

    for pattern in (_ARXIV_URL, _HF_PAPER_URL):
        match = pattern.search(url)

        if match:
            return f"arxiv:{match.group(1)}"

    match = _GITHUB_REPO_URL.match(url)

    if match:
        owner, repo = match.groups()
        return f"github:{owner.lower()}/{repo.lower()}"

    match = _HF_REPO_URL.match(url)

    if match and match.group(2) not in _HF_RESERVED:
        space, owner, repo = match.groups()
        prefix = "hf-space" if space else "hf-model"
        return f"{prefix}:{owner}/{repo}"

    return None


# ============================================================
# Text
# ============================================================

def clean_text(
    value: str | None,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        value or "",
    ).strip()


def html_to_text(
    html: str | None,
) -> str:
    """
    Convert an HTML fragment (RSS summary/content) to
    paragraph-separated plain text.
    """

    if not html:
        return ""

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for node in soup(
        ["script", "style", "noscript"]
    ):
        node.decompose()

    blocks = [
        clean_text(
            node.get_text(
                " ",
                strip=True,
            )
        )
        for node in soup.find_all(
            ["p", "li", "h2", "h3", "h4", "blockquote", "pre"]
        )
    ]

    blocks = [
        block
        for block in blocks
        if block
    ]

    if blocks:
        return "\n\n".join(blocks)

    return clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )


def first_image_in_html(
    html: str | None,
) -> str | None:
    if not html:
        return None

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    image = soup.find(
        "img",
        src=True,
    )

    if image is None:
        return None

    src = str(
        image.get("src", "")
    ).strip()

    if src.startswith(
        ("http://", "https://")
    ):
        return src

    return None


def truncate(
    value: str | None,
    limit: int,
) -> str | None:
    if value is None:
        return None

    if len(value) <= limit:
        return value

    return value[:limit].rsplit(
        " ",
        1,
    )[0] + "…"


# ============================================================
# AI relevance (for general-topic sources)
# ============================================================

# Deliberately excludes words that are common outside AI
# ("agent", "inference", "GPU", "cursor", "RAG"): on Hacker
# News they let through SSH agents and hardware posts.
_AI_PATTERN = re.compile(
    r"\b("
    r"ai|a\.i\.|agi|artificial intelligence|machine learning|"
    r"deep learning|neural net\w*|llms?|large language models?|"
    r"language models?|foundation models?|generative|genai|"
    r"diffusion models?|multimodal|reinforcement learning|"
    r"ai agents?|agentic|chatbots?|fine-?tun\w*|"
    r"openai|anthropic|claude|gemini|deepmind|gpt-?\w*|chatgpt|"
    r"llama|mistral|deepseek|qwen|hugging ?face|copilot|"
    r"stable diffusion|midjourney|sora|grok|xai|perplexity"
    r")\b",
    re.IGNORECASE,
)


def is_ai_related(
    text: str,
) -> bool:
    return bool(
        _AI_PATTERN.search(
            text or ""
        )
    )
