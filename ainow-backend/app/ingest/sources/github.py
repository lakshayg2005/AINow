from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import settings
from app.ingest.http import get_with_retry
from app.ingest.utils import (
    canonical_url,
    clean_text,
    parse_iso_datetime,
)
from app.schemas.ingest import IngestedItem

if TYPE_CHECKING:
    from app.ingest.registry import IngestSource


GITHUB_SEARCH = "https://api.github.com/search/repositories"

# One search request per topic. Unauthenticated search allows
# 10 requests/minute, so keep this list short.
GITHUB_TOPICS = (
    "llm",
    "ai-agents",
    "generative-ai",
    "large-language-models",
    "rag",
    "mcp",
)

GITHUB_MIN_STARS = 50


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
    }

    if settings.GITHUB_TOKEN:
        headers["Authorization"] = (
            f"Bearer {settings.GITHUB_TOKEN}"
        )

    return headers


def github_repo_to_item(
    source: IngestSource,
    repo: dict[str, Any],
) -> IngestedItem | None:
    full_name = repo.get("full_name")

    if not full_name or repo.get("fork") or repo.get("archived"):
        return None

    description = clean_text(
        repo.get("description")
    )

    summary = description

    if repo.get("language"):
        summary += f" (Language: {repo['language']})"

    return IngestedItem(
        source_key=source.key,
        source_name=source.name,
        kind="repo",
        category=source.category,
        trust_tier=source.trust_tier,
        url=canonical_url(
            repo.get("html_url")
            or f"https://github.com/{full_name}"
        ),
        external_id=f"github:{full_name.lower()}",
        title=full_name,
        summary=summary or None,
        image_url=(
            f"https://opengraph.githubassets.com/1/{full_name}"
        ),
        authors=[full_name.split("/")[0]],
        tags=list(repo.get("topics") or [])[:15],
        signals={
            "stars": float(repo.get("stargazers_count") or 0),
            "forks": float(repo.get("forks_count") or 0),
        },
        published_at=parse_iso_datetime(
            repo.get("created_at")
        ),
    )


async def fetch_github(
    client: httpx.AsyncClient,
    source: IngestSource,
    since: datetime,
) -> list[IngestedItem]:
    repos: dict[str, dict[str, Any]] = {}

    for topic in GITHUB_TOPICS:
        response = await get_with_retry(
            client,
            GITHUB_SEARCH,
            headers=_github_headers(),
            params={
                "q": (
                    f"topic:{topic} "
                    f"created:>={since.date().isoformat()} "
                    f"stars:>={GITHUB_MIN_STARS}"
                ),
                "sort": "stars",
                "order": "desc",
                "per_page": source.max_items,
            },
        )

        for repo in response.json().get("items", []):
            repos.setdefault(
                repo.get("full_name"),
                repo,
            )

    items = [
        github_repo_to_item(
            source,
            repo,
        )
        for repo in repos.values()
    ]

    return [
        item
        for item in items
        if item is not None
    ]
