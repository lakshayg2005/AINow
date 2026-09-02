import asyncio

from app.research.mcp_sources import (
    search_huggingface_repositories,
    search_huggingface_papers,
    get_huggingface_trending_models,
)


async def main():

    # ============================================================
    # Repository Search
    # ============================================================

    print("\n" + "=" * 70)
    print("HUGGING FACE REPOSITORIES")
    print("=" * 70)

    repos = await search_huggingface_repositories(
        query="transformers",
        lookback_days=3650,
        limit=10,
    )

    print(
        f"\nReturned candidates: {len(repos)}"
    )

    for index, candidate in enumerate(
        repos,
        start=1,
    ):
        print(
            f"\n{index}. {candidate.title}"
        )
        print(
            f"   Source: {candidate.source_name}"
        )
        print(
            f"   URL: {candidate.url}"
        )
        print(
            f"   Published: {candidate.published_at}"
        )
        print(
            f"   Topics: {candidate.topics}"
        )
        print(
            f"   Likes: {candidate.citation_count}"
        )

    # ============================================================
    # Papers
    # ============================================================

    print("\n" + "=" * 70)
    print("HUGGING FACE PAPERS")
    print("=" * 70)

    papers = await search_huggingface_papers(
        query="large language models",
        lookback_days=3650,
        limit=10,
    )

    print(
        f"\nReturned candidates: {len(papers)}"
    )

    for index, candidate in enumerate(
        papers,
        start=1,
    ):
        print(
            f"\n{index}. {candidate.title}"
        )
        print(
            f"   Source: {candidate.source_name}"
        )
        print(
            f"   URL: {candidate.url}"
        )
        print(
            f"   Published: {candidate.published_at}"
        )
        print(
            f"   Content: "
            f"{candidate.raw_content[:250]}"
        )
        print(
            f"   Upvotes: "
            f"{candidate.citation_count}"
        )

    # ============================================================
    # Trending Models
    # ============================================================

    print("\n" + "=" * 70)
    print("HUGGING FACE TRENDING MODELS")
    print("=" * 70)

    trending = await get_huggingface_trending_models(
        lookback_days=30,
        limit=10,
    )

    print(
        f"\nReturned candidates: {len(trending)}"
    )

    for index, candidate in enumerate(
        trending,
        start=1,
    ):
        print(
            f"\n{index}. {candidate.title}"
        )
        print(
            f"   Source: {candidate.source_name}"
        )
        print(
            f"   URL: {candidate.url}"
        )
        print(
            f"   Updated: {candidate.published_at}"
        )
        print(
            f"   Score/Likes: "
            f"{candidate.citation_count}"
        )


if __name__ == "__main__":
    asyncio.run(main())