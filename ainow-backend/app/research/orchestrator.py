from __future__ import annotations

from app.research.academic_sources import (
    search_arxiv,
    search_crossref,
    search_semantic_scholar,
)
from app.research.deduplication import merge_candidates
from app.research.mcp_sources import search_mcp_source
from app.research.relevance import is_relevant
from app.research.source_router import (
    get_effective_lookback,
    route_sources,
)
from app.schemas.research import ResearchCandidate


class ResearchOrchestrator:
    async def research(
        self,
        plan,
    ) -> list[ResearchCandidate]:

        candidates: list[
            ResearchCandidate
        ] = []

        # ========================================================
        # SECTION LOOP
        # ========================================================

        for section in plan.sections:

            print(
                "\n"
                + "=" * 60
            )

            print(
                "[Research] SECTION: "
                f"{section.section}"
            )

            print(
                "[Research] Lookback: "
                f"{section.lookback_days} days"
            )

            sources = route_sources(
                section
            )

            print(
                "[Research] Sources: "
                + (
                    ", ".join(
                        source.name
                        for source in sources
                    )
                    if sources
                    else "none"
                )
            )

            # ====================================================
            # SOURCE LOOP
            # ====================================================

            for source in sources:

                effective_lookback = (
                    get_effective_lookback(
                        section,
                        source,
                    )
                )

                print(
                    f"\n[Research] "
                    f"{source.name} "
                    f"(mode={source.access_mode}, "
                    f"lookback="
                    f"{effective_lookback}d)"
                )

                # =================================================
                # QUERY LOOP
                # =================================================

                for query in section.queries:

                    try:

                        results = (
                            await self._fetch_source_results(
                                source=source,
                                query=query,
                                effective_lookback=(
                                    effective_lookback
                                ),
                                max_results=(
                                    section
                                    .max_results_per_source
                                ),
                            )
                        )

                        # =========================================
                        # RELEVANCE FILTER
                        # =========================================

                        relevant = [
                            candidate
                            for candidate in results
                            if is_relevant(
                                candidate,
                                query,
                            )
                        ]

                        candidates.extend(
                            relevant
                        )

                        print(
                            f"[Research] "
                            f"{source.name} "
                            f"'{query}': "
                            f"{len(results)} raw "
                            f"→ "
                            f"{len(relevant)} relevant"
                        )

                    except Exception as error:

                        print(
                            f"[Research] "
                            f"{source.name} "
                            f"failed for "
                            f"'{query}': "
                            f"{error}"
                        )

        # ========================================================
        # GLOBAL MERGING
        # ========================================================

        print(
            "\n[Research] Raw relevant "
            f"candidates: {len(candidates)}"
        )

        merged_candidates = merge_candidates(
            candidates
        )

        print(
            "[Research] After cross-source "
            f"merging: "
            f"{len(merged_candidates)}"
        )

        return merged_candidates

    async def _fetch_source_results(
        self,
        source,
        query: str,
        effective_lookback: int,
        max_results: int,
    ) -> list[ResearchCandidate]:

        # ========================================================
        # API SOURCES
        # ========================================================

        if source.access_mode == "api":

            if source.name == "arXiv":

                return await search_arxiv(
                    query=query,
                    lookback_days=effective_lookback,
                    max_results=max_results,
                )

            if source.name == "Crossref":

                return await search_crossref(
                    query=query,
                    lookback_days=effective_lookback,
                    max_results=max_results,
                )

            if source.name == "Semantic Scholar":

                return await search_semantic_scholar(
                    query=query,
                    lookback_days=effective_lookback,
                    max_results=max_results,
                )

            print(
                "[Research] "
                f"API adapter not implemented "
                f"for {source.name}"
            )

            return []

        # ========================================================
        # MCP SOURCES
        # ========================================================

        if source.access_mode == "mcp":

            return await search_mcp_source(
                source_name=source.name,
                query=query,
                lookback_days=effective_lookback,
                max_results=max_results,
            )

        # ========================================================
        # WEB SOURCES
        # ========================================================

        if source.access_mode == "web":

            print(
                "[Research] "
                f"{source.name}: "
                "web adapter not implemented yet"
            )

            return []

        # ========================================================
        # UNKNOWN ACCESS MODE
        # ========================================================

        print(
            "[Research] "
            f"{source.name}: "
            f"unsupported access mode "
            f"'{source.access_mode}'"
        )

        return []