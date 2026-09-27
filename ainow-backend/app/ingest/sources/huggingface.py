from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from app.ingest.http import get_with_retry
from app.ingest.utils import (
    clean_text,
    parse_iso_datetime,
    utcnow,
)
from app.schemas.ingest import IngestedItem

if TYPE_CHECKING:
    from app.ingest.registry import IngestSource


HF_API = "https://huggingface.co/api"
HF_THUMBNAILS = "https://cdn-thumbnails.huggingface.co/social-thumbnails"

# Daily Papers is date-partitioned; cap how far back we walk.
MAX_DAILY_PAPER_DAYS = 7


# ============================================================
# Daily Papers (community-curated arXiv papers with upvotes)
# ============================================================

def daily_paper_to_item(
    source: IngestSource,
    record: dict[str, Any],
) -> IngestedItem | None:
    paper = record.get("paper") or {}
    arxiv_id = paper.get("id")
    title = clean_text(
        paper.get("title")
        or record.get("title")
    )

    if not arxiv_id or not title:
        return None

    abstract = clean_text(
        paper.get("summary")
        or record.get("summary")
    )

    authors = [
        clean_text(author.get("name"))
        for author in paper.get("authors") or []
        if author.get("name")
    ]

    organization = (
        (record.get("organization") or {}).get("fullname")
        or (paper.get("organization") or {}).get("fullname")
    )

    content = (
        f"{abstract}\n\n"
        f"arXiv: https://arxiv.org/abs/{arxiv_id}"
    )

    return IngestedItem(
        source_key=source.key,
        source_name=source.name,
        kind="paper",
        category=source.category,
        trust_tier=source.trust_tier,
        url=f"https://huggingface.co/papers/{arxiv_id}",
        external_id=f"arxiv:{arxiv_id}",
        title=title,
        summary=abstract[:1000] or None,
        content=content,
        image_url=(
            record.get("thumbnail")
            or f"{HF_THUMBNAILS}/papers/{arxiv_id}.png"
        ),
        authors=authors[:20],
        tags=(
            [organization]
            if organization
            else []
        ),
        signals={
            "hf_upvotes": float(
                paper.get("upvotes") or 0
            ),
            "hf_comments": float(
                record.get("numComments") or 0
            ),
        },
        published_at=(
            parse_iso_datetime(paper.get("publishedAt"))
            or parse_iso_datetime(record.get("publishedAt"))
        ),
    )


async def fetch_hf_daily_papers(
    client: httpx.AsyncClient,
    source: IngestSource,
    since: datetime,
) -> list[IngestedItem]:
    today = utcnow().date()

    days = min(
        MAX_DAILY_PAPER_DAYS,
        max(1, (today - since.date()).days + 1),
    )

    items: list[IngestedItem] = []

    for offset in range(days):
        day = today - timedelta(days=offset)

        response = await get_with_retry(
            client,
            f"{HF_API}/daily_papers",
            params={
                "date": day.isoformat(),
                "limit": source.max_items,
            },
        )

        for record in response.json():
            item = daily_paper_to_item(
                source,
                record,
            )

            if item is not None:
                items.append(item)

    return items


# ============================================================
# Trending models / spaces
# ============================================================

def _repo_summary(
    kind: str,
    record: dict[str, Any],
) -> str:
    repo_id = record["id"]
    owner = repo_id.split("/")[0]

    parts = [
        f"Hugging Face {kind} '{repo_id}' by {owner}."
    ]

    if record.get("pipeline_tag"):
        parts.append(
            f"Task: {record['pipeline_tag']}."
        )

    if record.get("library_name"):
        parts.append(
            f"Library: {record['library_name']}."
        )

    if record.get("sdk"):
        parts.append(
            f"SDK: {record['sdk']}."
        )

    tags = [
        tag
        for tag in record.get("tags") or []
        if ":" not in tag
        and tag not in {"region", "endpoints_compatible"}
    ]

    if tags:
        parts.append(
            "Tags: " + ", ".join(tags[:12]) + "."
        )

    return " ".join(parts)


def hf_repo_to_item(
    source: IngestSource,
    record: dict[str, Any],
) -> IngestedItem | None:
    repo_id = record.get("id")

    if not repo_id or record.get("private"):
        return None

    if source.kind == "space":
        url = f"https://huggingface.co/spaces/{repo_id}"
        image = f"{HF_THUMBNAILS}/spaces/{repo_id}.png"
        external_id = f"hf-space:{repo_id}"
    else:
        url = f"https://huggingface.co/{repo_id}"
        image = f"{HF_THUMBNAILS}/models/{repo_id}.png"
        external_id = f"hf-model:{repo_id}"

    signals = {
        "likes": float(record.get("likes") or 0),
        "trending_score": float(record.get("trendingScore") or 0),
    }

    if "downloads" in record:
        signals["downloads"] = float(
            record.get("downloads") or 0
        )

    return IngestedItem(
        source_key=source.key,
        source_name=source.name,
        kind=source.kind,
        category=source.category,
        trust_tier=source.trust_tier,
        url=url,
        external_id=external_id,
        title=repo_id,
        summary=_repo_summary(
            source.kind,
            record,
        ),
        image_url=image,
        authors=[repo_id.split("/")[0]],
        tags=[
            tag
            for tag in record.get("tags") or []
            if ":" not in tag
        ][:15],
        signals=signals,
        published_at=parse_iso_datetime(
            record.get("createdAt")
        ),
    )


async def fetch_hf_trending(
    client: httpx.AsyncClient,
    source: IngestSource,
    since: datetime,
) -> list[IngestedItem]:
    del since

    endpoint = (
        "spaces"
        if source.kind == "space"
        else "models"
    )

    response = await get_with_retry(
        client,
        f"{HF_API}/{endpoint}",
        params={
            "sort": "trendingScore",
            "limit": source.max_items,
        },
    )

    items = [
        hf_repo_to_item(
            source,
            record,
        )
        for record in response.json()
    ]

    return [
        item
        for item in items
        if item is not None
    ]
