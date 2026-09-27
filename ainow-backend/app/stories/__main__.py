"""
Build and inspect stories from ingested items.

    python -m app.stories                  # cluster + triage + show top 25
    python -m app.stories --no-llm         # rule-based triage only
    python -m app.stories --seed-covered   # load past issues into memory
    python -m app.stories --top 40 --show-repeats
"""

from __future__ import annotations

import argparse
import asyncio

from app.db.database import SessionLocal, engine
from app.db.schema_patches import ensure_schema
from app.stories.cluster import reset_stories
from app.stories.novelty import seed_from_published_issues
from app.stories.service import DEFAULT_TRIAGE_LIMIT, top_stories, update_stories


def print_top_stories(
    db,
    limit: int,
    include_repeats: bool = False,
) -> None:
    print(f"\n[Stories] Top {limit} (last 7 days):")

    for rank, (story, novelty) in enumerate(
        top_stories(db, limit=limit, include_repeats=include_repeats),
        start=1,
    ):
        sources = ", ".join((story.signals or {}).get("sources") or [])

        print(
            f"{rank:>3}. [{story.score:5.1f}] "
            f"{(story.category or '?'):<13} "
            f"imp={story.importance or '-':<2} "
            f"{novelty.status:<7} "
            f"{story.title[:70]}"
        )
        print(
            f"       {story.item_count} items from {sources[:90]}"
            f"{'  PROMO' if story.is_promotional else ''}"
            f"{'  IMG' if story.image_url else ''}"
        )


async def _main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.stories")
    parser.add_argument("--no-triage", action="store_true")
    parser.add_argument("--no-llm", action="store_true", help="Rule-based triage only.")
    parser.add_argument("--triage-limit", type=int, default=DEFAULT_TRIAGE_LIMIT)
    parser.add_argument("--seed-covered", action="store_true")
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--show-repeats", action="store_true")
    parser.add_argument(
        "--recluster",
        action="store_true",
        help="Drop all stories and cluster again (only before any issue uses them).",
    )
    args = parser.parse_args()

    ensure_schema(engine)

    db = SessionLocal()

    try:
        if args.recluster:
            print(f"[Stories] Reset {reset_stories(db)} stories")

        if args.seed_covered:
            created = seed_from_published_issues(db)
            print(f"[Stories] Seeded {created} covered entries from published issues")

        stats = await update_stories(
            db,
            triage=not args.no_triage,
            use_llm=not args.no_llm,
            triage_limit=args.triage_limit,
        )

        print("[Stories] " + ", ".join(f"{k}={v}" for k, v in stats.items()))

        print_top_stories(db, args.top, args.show_repeats)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(_main())
