from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.mcp.client import MCPClient
from app.mcp.registry import get_mcp_server
from app.schemas.research import ResearchCandidate
from app.research.github_sources import (
    search_github_mcp_source,
)


# ============================================================
# MCP response normalization
# ============================================================

def _content_to_python(
    content: Any,
) -> Any:

    if content is None:
        return None

    if isinstance(
        content,
        (dict, list, str, int, float, bool),
    ):
        return content

    model_dump = getattr(
        content,
        "model_dump",
        None,
    )

    if callable(model_dump):
        try:
            return model_dump()
        except Exception:
            pass

    text = getattr(
        content,
        "text",
        None,
    )

    if text is not None:

        text = text.strip()

        if not text:
            return None

        try:
            return json.loads(text)

        except json.JSONDecodeError:
            return text

    structured = getattr(
        content,
        "structured_content",
        None,
    )

    if structured is not None:
        return _content_to_python(
            structured
        )

    return str(
        content
    )


def _result_to_python(
    result: Any,
) -> Any:

    structured = getattr(
        result,
        "structured_content",
        None,
    )

    if structured is not None:
        return _content_to_python(
            structured
        )

    content = getattr(
        result,
        "content",
        None,
    )

    if not content:
        return None

    values = [
        _content_to_python(
            item
        )
        for item in content
    ]

    values = [
        value
        for value in values
        if value is not None
    ]

    if len(values) == 1:
        return values[0]

    return values


# ============================================================
# Common helpers
# ============================================================

def _parse_datetime(
    value: Any,
) -> datetime | None:

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):

        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    try:

        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except ValueError:
        return None


def _within_lookback(
    timestamp: datetime | None,
    lookback_days: int,
) -> bool:

    if timestamp is None:
        return False

    cutoff = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            days=lookback_days
        )
    )

    return timestamp >= cutoff


def _safe_int(
    value: Any,
) -> int:

    if value is None:
        return 0

    try:

        return int(
            str(
                value
            ).replace(
                ",",
                "",
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0


# ============================================================
# Hugging Face structured response helper
# ============================================================

def _extract_hf_entries(
    payload: Any,
) -> list[dict[str, Any]]:

    if not isinstance(
        payload,
        dict,
    ):
        return []

    entries: list[
        dict[str, Any]
    ] = []

    for operation in payload.get(
        "results",
        [],
    ):

        if not isinstance(
            operation,
            dict,
        ):
            continue

        if operation.get(
            "status"
        ) != "success":
            continue

        result = operation.get(
            "result",
            {},
        )

        if not isinstance(
            result,
            dict,
        ):
            continue

        operation_entries = result.get(
            "entries",
            [],
        )

        if not isinstance(
            operation_entries,
            list,
        ):
            continue

        entries.extend(
            entry
            for entry in operation_entries
            if isinstance(
                entry,
                dict,
            )
        )

    return entries


# ============================================================
# Hugging Face repositories
# ============================================================

async def search_huggingface_repositories(
    query: str,
    lookback_days: int,
    limit: int = 10,
) -> list[ResearchCandidate]:

    client = MCPClient(
        get_mcp_server(
            "huggingface"
        )
    )

    result = await client.call_tool(
        "hf_fs",
        {
            "operations": [
                {
                    "cmd": "search",
                    "args": [
                        "hf://models",
                        query,
                        "--limit",
                        str(
                            min(
                                limit,
                                100,
                            )
                        ),
                    ],
                }
            ]
        },
    )

    payload = _result_to_python(
        result
    )

    entries = _extract_hf_entries(
        payload
    )

    candidates: list[
        ResearchCandidate
    ] = []

    for item in entries:

        if item.get(
            "type"
        ) != "repo":
            continue

        repo_id = (
            item.get(
                "path"
            )
            or item.get(
                "name"
            )
        )

        if not repo_id:
            continue

        repo_id = str(
            repo_id
        )

        updated_at = _parse_datetime(
            item.get(
                "updated_at"
            )
            or item.get(
                "last_modified"
            )
        )

        if not _within_lookback(
            updated_at,
            lookback_days,
        ):
            continue

        repo_type = str(
            item.get(
                "repo_type",
                "model",
            )
        )

        task = item.get(
            "task"
        )

        likes = _safe_int(
            item.get(
                "likes"
            )
        )

        downloads = _safe_int(
            item.get(
                "downloads"
            )
        )

        author = None

        if "/" in repo_id:
            author = repo_id.split(
                "/",
                1,
            )[0]

        raw_content = (
            f"Hugging Face repository: "
            f"{repo_id}\n"
            f"Repository type: "
            f"{repo_type}\n"
            f"Task: "
            f"{task or 'unknown'}\n"
            f"Likes: "
            f"{likes}\n"
            f"Downloads: "
            f"{downloads}"
        )

        candidates.append(
            ResearchCandidate(
                title=repo_id,
                url=(
                    "https://huggingface.co/"
                    f"{repo_id}"
                ),
                source_name="Hugging Face",
                category="open-source",
                raw_content=raw_content,
                published_at=updated_at,
                trust_tier=1,
                topics=[
                    "hugging-face",
                    "open-source",
                    repo_type,
                    "models",
                ],
                citation_count=likes,
                authors=(
                    [author]
                    if author
                    else []
                ),
            )
        )

    print(
        "[HF MCP] Model candidates:",
        len(candidates),
    )

    return candidates


# ============================================================
# Hugging Face papers
# ============================================================

async def search_huggingface_papers(
    query: str,
    lookback_days: int,
    limit: int = 10,
) -> list[ResearchCandidate]:

    client = MCPClient(
        get_mcp_server(
            "huggingface"
        )
    )

    result = await client.call_tool(
        "hf_fs",
        {
            "operations": [
                {
                    "cmd": "search",
                    "args": [
                        "hf://papers",
                        query,
                        "--limit",
                        str(
                            min(
                                limit,
                                100,
                            )
                        ),
                    ],
                }
            ]
        },
    )

    payload = _result_to_python(
        result
    )

    entries = _extract_hf_entries(
        payload
    )

    candidates: list[
        ResearchCandidate
    ] = []

    for item in entries:

        if item.get(
            "type"
        ) != "paper":
            continue

        paper_id = (
            item.get(
                "name"
            )
            or item.get(
                "path"
            )
        )

        if not paper_id:
            continue

        paper_id = str(
            paper_id
        )

        published_at = _parse_datetime(
            item.get(
                "published_at"
            )
        )

        if not _within_lookback(
            published_at,
            lookback_days,
        ):
            continue

        title = str(
            item.get(
                "title"
            )
            or paper_id
        ).strip()

        description = str(
            item.get(
                "description"
            )
            or ""
        ).strip()

        url = str(
            item.get(
                "url"
            )
            or item.get(
                "arxiv_url"
            )
            or (
                "https://huggingface.co/"
                f"papers/{paper_id}"
            )
        )

        arxiv_url = item.get(
            "arxiv_url"
        )

        raw_content = description

        if arxiv_url:
            raw_content = (
                f"{description}\n\n"
                f"arXiv: {arxiv_url}"
            ).strip()

        candidates.append(
            ResearchCandidate(
                title=title,
                url=url,
                source_name="Hugging Face Papers",
                category="research",
                raw_content=raw_content,
                published_at=published_at,
                trust_tier=1,
                topics=[
                    "hugging-face",
                    "papers",
                    "research",
                ],
                citation_count=_safe_int(
                    item.get(
                        "upvotes"
                    )
                ),
            )
        )

    print(
        "[HF MCP] Paper candidates:",
        len(candidates),
    )

    return candidates


# ============================================================
# Hugging Face trending
# ============================================================

async def get_huggingface_trending_models(
    lookback_days: int,
    limit: int = 10,
) -> list[ResearchCandidate]:

    client = MCPClient(
        get_mcp_server(
            "huggingface"
        )
    )

    result = await client.call_tool(
        "hf_fs",
        {
            "operations": [
                {
                    "cmd": "ls",
                    "args": [
                        "hf://models/trending",
                        "--limit",
                        str(
                            min(
                                limit,
                                100,
                            )
                        ),
                    ],
                }
            ]
        },
    )

    payload = _result_to_python(
        result
    )

    entries = _extract_hf_entries(
        payload
    )

    candidates: list[
        ResearchCandidate
    ] = []

    for item in entries:

        if item.get(
            "type"
        ) != "repo":
            continue

        repo_id = (
            item.get(
                "path"
            )
            or item.get(
                "name"
            )
        )

        if not repo_id:
            continue

        repo_id = str(
            repo_id
        )

        updated_at = _parse_datetime(
            item.get(
                "updated_at"
            )
        )

        if not _within_lookback(
            updated_at,
            lookback_days,
        ):
            continue

        repo_type = str(
            item.get(
                "repo_type",
                "model",
            )
        )

        task = item.get(
            "task"
        )

        likes = _safe_int(
            item.get(
                "likes"
            )
        )

        downloads = _safe_int(
            item.get(
                "downloads"
            )
        )

        author = None

        if "/" in repo_id:
            author = repo_id.split(
                "/",
                1,
            )[0]

        raw_content = (
            f"Hugging Face trending "
            f"{repo_type}: "
            f"{repo_id}\n"
            f"Task: "
            f"{task or 'unknown'}\n"
            f"Likes: "
            f"{likes}\n"
            f"Downloads: "
            f"{downloads}"
        )

        candidates.append(
            ResearchCandidate(
                title=repo_id,
                url=(
                    "https://huggingface.co/"
                    f"{repo_id}"
                ),
                source_name=(
                    "Hugging Face Leaderboard"
                ),
                category="leaderboard",
                raw_content=raw_content,
                published_at=updated_at,
                trust_tier=1,
                topics=[
                    "hugging-face",
                    "llm",
                    "models",
                    "benchmarks",
                    repo_type,
                ],
                citation_count=likes,
                authors=(
                    [author]
                    if author
                    else []
                ),
            )
        )

    print(
        "[HF MCP] Trending candidates:",
        len(candidates),
    )

    return candidates


# ============================================================
# Hugging Face dispatcher
# ============================================================

async def search_huggingface_source(
    source_name: str,
    query: str,
    lookback_days: int,
    max_results: int = 10,
) -> list[ResearchCandidate]:

    if source_name == "Hugging Face":

        return await search_huggingface_repositories(
            query=query,
            lookback_days=lookback_days,
            limit=max_results,
        )

    if source_name == "Hugging Face Leaderboard":

        return await get_huggingface_trending_models(
            lookback_days=lookback_days,
            limit=max_results,
        )

    if source_name == "Hugging Face Papers":

        return await search_huggingface_papers(
            query=query,
            lookback_days=lookback_days,
            limit=max_results,
        )

    print(
        "[Research] "
        f"No Hugging Face MCP adapter for "
        f"'{source_name}'"
    )

    return []


# ============================================================
# Generic MCP dispatcher
# ============================================================

async def search_mcp_source(
    source_name: str,
    query: str,
    lookback_days: int,
    max_results: int = 10,
) -> list[ResearchCandidate]:

    if source_name in {
        "Hugging Face",
        "Hugging Face Leaderboard",
        "Hugging Face Papers",
    }:

        return await search_huggingface_source(
            source_name=source_name,
            query=query,
            lookback_days=lookback_days,
            max_results=max_results,
        )

    if source_name == "GitHub":

        return await search_github_mcp_source(
            source_name=source_name,
            query=query,
            lookback_days=lookback_days,
            max_results=max_results,
        )

    raise ValueError(
        f"Unsupported MCP source: "
        f"{source_name}"
    )