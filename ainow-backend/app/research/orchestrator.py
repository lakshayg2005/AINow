from app.research.deduplication import merge_candidates
from app.research.free_sources import (
    search_arxiv,
    search_crossref,
    search_openalex,
)
from app.research.relevance import is_relevant
from app.schemas.research import ResearchCandidate


class ResearchOrchestrator:

    async def research(
        self,
        queries: list[str],
        lookback_days: int,
    ) -> list[ResearchCandidate]:

        candidates: list[ResearchCandidate] = []

        for query in queries:

            print(
                f"\n[Research] Query: {query}"
            )

            # ==========================================
            # OPENALEX
            # ==========================================

            try:

                openalex_results = await search_openalex(
                    query=query,
                    lookback_days=lookback_days,
                    max_results=20,
                )

                relevant = [
                    candidate
                    for candidate in openalex_results
                    if is_relevant(
                        candidate,
                        query,
                    )
                ]

                candidates.extend(
                    relevant
                )

                print(
                    f"[Research] OpenAlex "
                    f"'{query}': "
                    f"{len(openalex_results)} raw → "
                    f"{len(relevant)} relevant"
                )

            except Exception as error:

                print(
                    f"[Research] OpenAlex failed "
                    f"for '{query}': {error}"
                )

            # ==========================================
            # CROSSREF
            # ==========================================

            try:

                crossref_results = await search_crossref(
                    query=query,
                    lookback_days=lookback_days,
                    max_results=20,
                )

                relevant = [
                    candidate
                    for candidate in crossref_results
                    if is_relevant(
                        candidate,
                        query,
                    )
                ]

                candidates.extend(
                    relevant
                )

                print(
                    f"[Research] Crossref "
                    f"'{query}': "
                    f"{len(crossref_results)} raw → "
                    f"{len(relevant)} relevant"
                )

            except Exception as error:

                print(
                    f"[Research] Crossref failed "
                    f"for '{query}': {error}"
                )

            # ==========================================
            # ARXIV
            # ==========================================

            try:

                arxiv_results = await search_arxiv(
                    query=query,
                    lookback_days=lookback_days,
                    max_results=20,
                )

                relevant = [
                    candidate
                    for candidate in arxiv_results
                    if is_relevant(
                        candidate,
                        query,
                    )
                ]

                candidates.extend(
                    relevant
                )

                print(
                    f"[Research] arXiv "
                    f"'{query}': "
                    f"{len(arxiv_results)} raw → "
                    f"{len(relevant)} relevant"
                )

            except Exception as error:

                print(
                    f"[Research] arXiv failed "
                    f"for '{query}': {error}"
                )

        # ==========================================
        # CROSS-SOURCE MERGING
        # ==========================================

        print(
            "\n[Research] Raw relevant candidates: "
            f"{len(candidates)}"
        )

        merged_candidates = merge_candidates(
            candidates
        )

        print(
            "[Research] After cross-source merging: "
            f"{len(merged_candidates)}"
        )

        return merged_candidates