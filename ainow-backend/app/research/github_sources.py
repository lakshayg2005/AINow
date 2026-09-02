from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.mcp.client import MCPClient
from app.mcp.registry import get_mcp_server
from app.schemas.research import ResearchCandidate


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

    # GitHub MCP returns the actual JSON response inside
    # TextContent.text.
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

    model_dump = getattr(
        content,
        "model_dump",
        None,
    )

    if callable(model_dump):
        try:
            dumped = model_dump()

            if isinstance(
                dumped,
                dict,
            ):
                dumped_text = dumped.get(
                    "text"
                )

                if isinstance(
                    dumped_text,
                    str,
                ):
                    dumped_text = dumped_text.strip()

                    if dumped_text:
                        try:
                            return json.loads(
                                dumped_text
                            )
                        except json.JSONDecodeError:
                            return dumped_text

            return dumped

        except Exception:
            pass

    return str(content)


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
        _content_to_python(item)
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
        datetime.now(timezone.utc)
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
            str(value).replace(
                ",",
                "",
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def _safe_str(
    value: Any,
) -> str | None:
    if value is None:
        return None

    value = str(value).strip()

    return value or None


# ============================================================
# Structured repository extraction
# ============================================================

def _is_repository_record(
    value: dict[str, Any],
) -> bool:
    repository_keys = {
        "full_name",
        "fullName",
        "nameWithOwner",
    }

    url_keys = {
        "html_url",
        "htmlUrl",
    }

    return bool(
        repository_keys.intersection(
            value.keys()
        )
    ) and bool(
        url_keys.intersection(
            value.keys()
        )
    )


def _find_repository_records(
    payload: Any,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[int] = set()

    def walk(
        value: Any,
    ) -> None:
        if value is None:
            return

        if isinstance(
            value,
            dict,
        ):
            object_id = id(value)

            if object_id in seen:
                return

            seen.add(object_id)

            if _is_repository_record(value):
                found.append(value)

            for nested in value.values():
                walk(nested)

            return

        if isinstance(
            value,
            (list, tuple),
        ):
            for item in value:
                walk(item)

    walk(payload)

    unique: dict[
        str,
        dict[str, Any],
    ] = {}

    for item in found:
        key = (
            _safe_str(
                item.get("full_name")
            )
            or _safe_str(
                item.get("fullName")
            )
            or _safe_str(
                item.get("nameWithOwner")
            )
            or _safe_str(
                item.get("html_url")
            )
            or _safe_str(
                item.get("htmlUrl")
            )
        )

        if key:
            unique[key] = item

    return list(unique.values())


# ============================================================
# Repository -> ResearchCandidate
# ============================================================

def _repository_to_candidate(
    item: dict[str, Any],
    lookback_days: int,
) -> ResearchCandidate | None:

    full_name = (
        _safe_str(
            item.get("full_name")
        )
        or _safe_str(
            item.get("fullName")
        )
        or _safe_str(
            item.get("nameWithOwner")
        )
    )

    # Fallback owner + repository.
    if not full_name:
        owner = item.get("owner")

        owner_name = None

        if isinstance(
            owner,
            dict,
        ):
            owner_name = (
                _safe_str(
                    owner.get("login")
                )
                or _safe_str(
                    owner.get("name")
                )
            )

        repo_name = _safe_str(
            item.get("name")
        )

        if owner_name and repo_name:
            full_name = (
                f"{owner_name}/{repo_name}"
            )

    if not full_name:
        return None

    updated_at = (
        item.get("updated_at")
        or item.get("updatedAt")
        or item.get("pushed_at")
        or item.get("pushedAt")
    )

    updated_at = _parse_datetime(
        updated_at
    )

    if updated_at is not None:
        if not _within_lookback(
            updated_at,
            lookback_days,
        ):
            return None

    url = (
        _safe_str(
            item.get("html_url")
        )
        or _safe_str(
            item.get("htmlUrl")
        )
        or f"https://github.com/{full_name}"
    )

    description = (
        _safe_str(
            item.get("description")
        )
        or ""
    )

    language = (
        _safe_str(
            item.get("language")
        )
        or "unknown"
    )

    stars = _safe_int(
        item.get("stargazers_count")
        or item.get("stargazersCount")
        or item.get("stars")
    )

    forks = _safe_int(
        item.get("forks_count")
        or item.get("forksCount")
        or item.get("forks")
    )

    topics = item.get("topics")

    if not isinstance(
        topics,
        list,
    ):
        topics = []

    topics = [
        str(topic)
        for topic in topics
        if topic
    ]

    owner = item.get(
        "owner"
    )

    author = None

    if isinstance(
        owner,
        dict,
    ):
        author = (
            _safe_str(
                owner.get("login")
            )
            or _safe_str(
                owner.get("name")
            )
        )

    if author is None:
        author = (
            full_name.split(
                "/",
                1,
            )[0]
            if "/" in full_name
            else None
        )

    raw_content = (
        f"GitHub repository: {full_name}\n"
        f"Description: {description}\n"
        f"Language: {language}\n"
        f"Stars: {stars}\n"
        f"Forks: {forks}\n"
        f"Topics: {', '.join(topics)}"
    )

    return ResearchCandidate(
        title=full_name,
        url=url,
        source_name="GitHub",
        category="open-source",
        raw_content=raw_content,
        published_at=updated_at,
        trust_tier=1,
        topics=[
            "github",
            "open-source",
            "repository",
            *topics,
        ],
        citation_count=stars,
        authors=(
            [author]
            if author
            else []
        ),
    )


# ============================================================
# Repository search
# ============================================================

async def search_github_repositories(
    query: str,
    lookback_days: int,
    limit: int = 10,
) -> list[ResearchCandidate]:

    client = MCPClient(
        get_mcp_server("github")
    )

    result = await client.call_tool(
        "search_repositories",
        {
            "query": query,
            "sort": "updated",
            "order": "desc",
            "page": 1,
            "perPage": min(
                limit,
                100,
            ),
            "minimal_output": True,
        },
    )

    payload = _result_to_python(
        result
    )

    repositories = _find_repository_records(
        payload
    )

    print(
        "[GitHub MCP] Raw repository records:",
        len(repositories),
    )

    candidates: list[
        ResearchCandidate
    ] = []

    for repository in repositories:
        candidate = _repository_to_candidate(
            repository,
            lookback_days,
        )

        if candidate is not None:
            candidates.append(candidate)

    candidates = candidates[:limit]

    print(
        "[GitHub MCP] Repository candidates:",
        len(candidates),
    )

    return candidates


# ============================================================
# File contents
# ============================================================

async def get_github_file_contents(
    owner: str,
    repo: str,
    path: str = "README.md",
) -> Any:

    client = MCPClient(
        get_mcp_server("github")
    )

    result = await client.call_tool(
        "get_file_contents",
        {
            "owner": owner,
            "repo": repo,
            "path": path,
        },
    )

    return _result_to_python(
        result
    )


def _decode_github_content(
    value: str,
) -> str:

    if not value:
        return ""

    compact = (
        value
        .replace("\n", "")
        .replace("\r", "")
        .strip()
    )

    if (
        len(compact) % 4 != 0
        or not re.fullmatch(
            r"[A-Za-z0-9+/=]+",
            compact,
        )
        or len(compact) < 40
    ):
        return value

    try:
        decoded = base64.b64decode(
            compact,
            validate=True,
        )

        text = decoded.decode(
            "utf-8"
        )

        if text:
            return text

    except Exception:
        pass

    return value


def _extract_file_text(
    payload: Any,
) -> str:

    if payload is None:
        return ""

    if isinstance(
        payload,
        str,
    ):
        return _decode_github_content(
            payload
        )

    if isinstance(
        payload,
        list,
    ):
        pieces = [
            _extract_file_text(item)
            for item in payload
        ]

        return "\n".join(
            piece
            for piece in pieces
            if piece
        )

    if isinstance(
        payload,
        dict,
    ):
        for key in (
            "content",
            "text",
            "decoded_content",
            "decodedContent",
        ):
            value = payload.get(key)

            if isinstance(
                value,
                str,
            ):
                return _decode_github_content(
                    value
                )

        for value in payload.values():
            if isinstance(
                value,
                (dict, list),
            ):
                text = _extract_file_text(
                    value
                )

                if text:
                    return text

    return ""


# ============================================================
# README enrichment
# ============================================================

async def enrich_github_repository(
    candidate: ResearchCandidate,
) -> ResearchCandidate:

    if "/" not in candidate.title:
        return candidate

    owner, repo = candidate.title.split(
        "/",
        1,
    )

    try:
        payload = await get_github_file_contents(
            owner=owner,
            repo=repo,
            path="README.md",
        )

        readme = _extract_file_text(
            payload
        )

        if readme:
            candidate.raw_content = (
                f"{candidate.raw_content}\n\n"
                f"README:\n"
                f"{readme[:12000]}"
            )

    except Exception as error:
        print(
            "[GitHub MCP] README enrichment failed "
            f"for {candidate.title}: {error}"
        )

    return candidate


# ============================================================
# GitHub source
# ============================================================

async def search_github_source(
    query: str,
    lookback_days: int,
    max_results: int = 10,
) -> list[ResearchCandidate]:

    candidates = await search_github_repositories(
        query=query,
        lookback_days=lookback_days,
        limit=max_results,
    )

    enriched: list[
        ResearchCandidate
    ] = []

    # Enrich only first five repositories.
    for candidate in candidates[:5]:
        enriched_candidate = (
            await enrich_github_repository(
                candidate
            )
        )

        enriched.append(
            enriched_candidate
        )

    enriched.extend(
        candidates[5:]
    )

    return enriched


# ============================================================
# Generic GitHub MCP dispatcher
# ============================================================

async def search_github_mcp_source(
    source_name: str,
    query: str,
    lookback_days: int,
    max_results: int = 10,
) -> list[ResearchCandidate]:

    if source_name != "GitHub":
        raise ValueError(
            "Unsupported GitHub MCP source: "
            f"{source_name}"
        )

    return await search_github_source(
        query=query,
        lookback_days=lookback_days,
        max_results=max_results,
    )