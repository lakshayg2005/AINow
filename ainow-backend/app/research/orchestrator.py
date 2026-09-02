from __future__ import annotations

from collections import OrderedDict
from typing import Any

from app.research.academic_sources import (
    search_arxiv,
    search_crossref,
    search_semantic_scholar,
)
from app.research.mcp_sources import (
    search_mcp_source,
)
from app.research.relevance import (
    is_relevant,
)
from app.research.source_router import (
    get_effective_lookback,
    route_sources,
)
from app.research.web_sources import (
    search_web_source,
)
from app.schemas.research import (
    ResearchCandidate,
    ResearchPlan,
)


# ============================================================
# Configuration
# ============================================================

DEFAULT_SOURCE_RESULTS = 10

# Prevent one plan from generating an excessive number
# of network calls per section.
MAX_QUERIES_PER_SECTION = 1


# ============================================================
# Helpers
# ============================================================

def _candidate_key(
    candidate: ResearchCandidate,
) -> str:
    return (
        candidate.url
        .strip()
        .rstrip("/")
        .lower()
    )


def _merge_candidates(
    candidates: list[ResearchCandidate],
) -> list[ResearchCandidate]:
    """
    Merge candidates pointing to the same URL.

    Prefer the candidate with richer content.
    """

    merged: OrderedDict[
        str,
        ResearchCandidate,
    ] = OrderedDict()

    for candidate in candidates:
        key = _candidate_key(candidate)

        existing = merged.get(key)

        if existing is None:
            merged[key] = candidate
            continue

        existing_length = len(
            existing.raw_content or ""
        )

        candidate_length = len(
            candidate.raw_content or ""
        )

        if candidate_length > existing_length:
            merged[key] = candidate

    return list(
        merged.values()
    )


def _title_key(
    title: str,
) -> str:
    normalized = (
        title
        .lower()
        .replace("’", "'")
    )

    normalized = "".join(
        char
        if char.isalnum()
        else " "
        for char in normalized
    )

    return " ".join(
        normalized.split()
    )


def _deduplicate_titles(
    candidates: list[ResearchCandidate],
) -> list[ResearchCandidate]:
    """
    Remove exact normalized-title duplicates.
    """

    seen: set[str] = set()

    result: list[
        ResearchCandidate
    ] = []

    for candidate in candidates:
        key = _title_key(
            candidate.title
        )

        if not key:
            result.append(candidate)
            continue

        if key in seen:
            continue

        seen.add(key)
        result.append(candidate)

    return result


def _source_access_mode(
    source: Any,
) -> str:
    return getattr(
        source,
        "access_mode",
        "",
    )


def _source_name(
    source: Any,
) -> str:
    return getattr(
        source,
        "name",
        "",
    )


def _source_category(
    source: Any,
) -> str:
    return getattr(
        source,
        "category",
        "",
    )


async def _fetch_source_results(
    source: Any,
    query: str,
    lookback_days: int,
    max_results: int,
) -> list[ResearchCandidate]:
    """
    Dispatch a source through its API, MCP, or web adapter.

    Hard-caps the result count even when an upstream source
    ignores the requested limit.
    """

    access_mode = _source_access_mode(
        source
    )

    source_name = _source_name(
        source
    )

    source_name_lower = (
        source_name.lower()
    )

    candidates: list[
        ResearchCandidate
    ] = []

    # --------------------------------------------------------
    # API sources
    # --------------------------------------------------------

    if access_mode == "api":

        if source_name_lower == "arxiv":
            candidates = await search_arxiv(
                query=query,
                lookback_days=lookback_days,
                max_results=max_results,
            )

        elif source_name_lower == "crossref":
            candidates = await search_crossref(
                query=query,
                lookback_days=lookback_days,
                max_results=max_results,
            )

        elif (
            source_name_lower
            == "semantic scholar"
        ):
            candidates = await search_semantic_scholar(
                query=query,
                lookback_days=lookback_days,
                max_results=max_results,
            )

    # --------------------------------------------------------
    # MCP sources
    # --------------------------------------------------------

    elif access_mode == "mcp":
        candidates = await search_mcp_source(
            source_name,
            query,
            lookback_days,
            max_results,
        )

    # --------------------------------------------------------
    # Web sources
    # --------------------------------------------------------

    elif access_mode == "web":
        candidates = await search_web_source(
            source_name,
            query,
            lookback_days,
            max_results,
        )

    # --------------------------------------------------------
    # Final safety cap
    # --------------------------------------------------------

    return candidates[:max_results]


def _get_section_plans(
    plan: ResearchPlan,
) -> list[Any]:
    """
    Support either `sections` or `section_plans`.
    """

    sections = getattr(
        plan,
        "sections",
        None,
    )

    if sections:
        return list(
            sections
        )

    section_plans = getattr(
        plan,
        "section_plans",
        None,
    )

    if section_plans:
        return list(
            section_plans
        )

    return []


def _section_queries(
    plan: ResearchPlan,
    section: Any,
) -> list[str]:
    """
    Prefer section-specific queries.

    When a section has no explicit queries, use only the first
    global planner query. This prevents the same source from
    being queried repeatedly for every global query.
    """

    section_queries = getattr(
        section,
        "queries",
        None,
    )

    if section_queries:
        return list(
            section_queries
        )[:MAX_QUERIES_PER_SECTION]

    plan_queries = list(
        getattr(
            plan,
            "queries",
            [],
        )
    )

    if not plan_queries:
        return []

    return plan_queries[
        :MAX_QUERIES_PER_SECTION
    ]


# ============================================================
# Orchestrator
# ============================================================

class ResearchOrchestrator:

    async def research(
        self,
        plan: ResearchPlan,
    ) -> list[ResearchCandidate]:
        """
        Discovery-only research stage.

        Pipeline:

            section/source routing
                ↓
            source discovery
                ↓
            URL deduplication
                ↓
            relevance filtering
                ↓
            title deduplication

        Freshness and ranking remain graph responsibilities.
        """

        raw_candidates: list[
            ResearchCandidate
        ] = []

        sections = _get_section_plans(
            plan
        )

        if not sections:
            print(
                "[Orchestrator] "
                "No section plans found."
            )
            return []

        # ----------------------------------------------------
        # 1. Source discovery
        # ----------------------------------------------------

        for section in sections:

            sources = route_sources(
                section
            )

            if not sources:
                continue

            queries = _section_queries(
                plan,
                section,
            )

            if not queries:
                continue

            for query in queries:

                for source in sources:

                    source_name = _source_name(
                        source
                    )

                    category = _source_category(
                        source
                    )

                    lookback_days = (
                        get_effective_lookback(
                            section,
                            source,
                        )
                    )

                    try:

                        candidates = (
                            await _fetch_source_results(
                                source=source,
                                query=query,
                                lookback_days=lookback_days,
                                max_results=DEFAULT_SOURCE_RESULTS,
                            )
                        )

                        raw_candidates.extend(
                            candidates
                        )

                        print(
                            f"[Orchestrator] "
                            f"{category} / "
                            f"{source_name} / "
                            f"{query}: "
                            f"{len(candidates)}"
                        )

                    except Exception as error:

                        print(
                            f"[Orchestrator] "
                            f"{source_name} failed: "
                            f"{type(error).__name__}: "
                            f"{error}"
                        )

        print(
            f"[Orchestrator] "
            f"{len(raw_candidates)} raw candidates"
        )

        # ----------------------------------------------------
        # 2. URL deduplication
        # ----------------------------------------------------

        merged = _merge_candidates(
            raw_candidates
        )

        print(
            f"[Orchestrator] "
            f"{len(merged)} after URL merge"
        )

        if not merged:
            return []

        # ----------------------------------------------------
        # 3. Relevance filtering
        # ----------------------------------------------------

        plan_queries = list(
            getattr(
                plan,
                "queries",
                [],
            )
        )

        relevant: list[
            ResearchCandidate
        ] = []

        for candidate in merged:

            candidate_relevant = False

            for query in plan_queries:

                try:

                    if is_relevant(
                        candidate,
                        query,
                    ):
                        candidate_relevant = True
                        break

                except Exception as error:

                    print(
                        "[Orchestrator] "
                        f"relevance failed for "
                        f"{candidate.url}: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )

            if candidate_relevant:
                relevant.append(
                    candidate
                )

        print(
            f"[Orchestrator] "
            f"{len(relevant)} relevant candidates"
        )

        if not relevant:
            return []

        # ----------------------------------------------------
        # 4. Title deduplication
        # ----------------------------------------------------

        relevant = _deduplicate_titles(
            relevant
        )

        print(
            f"[Orchestrator] "
            f"{len(relevant)} after title merge"
        )

        return relevant