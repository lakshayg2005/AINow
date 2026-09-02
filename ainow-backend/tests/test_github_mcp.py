import asyncio

from app.research.github_sources import (
    search_github_repositories,
    search_github_source,
)


async def main():

    print("=" * 70)
    print("GITHUB MCP REPOSITORY SEARCH")
    print("=" * 70)

    candidates = await search_github_repositories(
        query=(
            "large language models "
            "stars:>100"
        ),
        lookback_days=3650,
        limit=10,
    )

    print(
        f"\nReturned candidates: "
        f"{len(candidates)}"
    )

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):

        print(
            f"\n{index}. {candidate.title}"
        )

        print(
            f"   Source: "
            f"{candidate.source_name}"
        )

        print(
            f"   URL: "
            f"{candidate.url}"
        )

        print(
            f"   Updated: "
            f"{candidate.published_at}"
        )

        print(
            f"   Stars: "
            f"{candidate.citation_count}"
        )

        print(
            f"   Topics: "
            f"{candidate.topics}"
        )

        print(
            f"   README included: "
            f"{'README:' in candidate.raw_content}"
        )

        print(
            "   Content preview:"
        )

        print(
            candidate.raw_content[:700]
        )

    print("\n")
    print("=" * 70)
    print("GITHUB MCP + README ENRICHMENT")
    print("=" * 70)

    enriched = await search_github_source(
        query=(
            "large language models "
            "stars:>100"
        ),
        lookback_days=3650,
        max_results=5,
    )

    print(
        f"\nEnriched candidates: "
        f"{len(enriched)}"
    )

    for index, candidate in enumerate(
        enriched,
        start=1,
    ):

        print(
            f"\n{index}. {candidate.title}"
        )

        print(
            f"   README included: "
            f"{'README:' in candidate.raw_content}"
        )

        print(
            candidate.raw_content[:1000]
        )


if __name__ == "__main__":
    asyncio.run(main())