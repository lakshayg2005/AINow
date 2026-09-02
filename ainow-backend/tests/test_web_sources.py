import asyncio

from app.research.web_sources import search_web_source


async def run_source(
    source_name: str,
    query: str,
):
    print("\n" + "=" * 80)
    print(source_name)
    print("=" * 80)

    candidates = await search_web_source(
        source_name=source_name,
        query=query,
        lookback_days=30,
        max_results=5,
    )

    print(
        f"\nCandidates: {len(candidates)}"
    )

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        print(
            f"\n{index}. {candidate.title}"
        )

        print(
            f"   URL: {candidate.url}"
        )

        print(
            f"   Published: "
            f"{candidate.published_at}"
        )

        print(
            f"   Source: "
            f"{candidate.source_name}"
        )

        print(
            f"   Preview:\n"
            f"{candidate.raw_content[:500]}"
        )


async def main():
    await run_source(
        "OpenAI",
        "latest artificial intelligence",
    )

    await run_source(
        "Google DeepMind",
        "latest AI research",
    )

    await run_source(
        "Anthropic",
        "latest AI models",
    )


if __name__ == "__main__":
    asyncio.run(main())