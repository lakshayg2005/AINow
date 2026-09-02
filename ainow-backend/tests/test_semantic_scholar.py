import asyncio

from app.research.academic_sources import (
    search_semantic_scholar,
)


async def main():

    results = await search_semantic_scholar(
        query="large language models",
        lookback_days=30,
        max_results=10,
    )

    print(
        "\nSemantic Scholar results:",
        len(results),
    )

    for index, candidate in enumerate(
        results,
        start=1,
    ):

        print(
            f"\n{index}. "
            f"{candidate.title}"
        )

        print(
            "URL:",
            candidate.url,
        )

        print(
            "Published:",
            candidate.published_at,
        )

        print(
            "Citations:",
            candidate.citation_count,
        )

        print(
            "Authors:",
            ", ".join(
                candidate.authors
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())