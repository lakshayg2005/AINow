"""
Run the ingestion loop.

    python -m app.ingest                     # one run, all enabled sources
    python -m app.ingest --sources openai hackernews
    python -m app.ingest --days 3 --no-enrich
    python -m app.ingest --every-hours 6     # keep running on a schedule
    python -m app.ingest --no-stories        # skip clustering/triage

Each run ends by clustering new items into stories and
triaging them (see app/stories).

For production, prefer a single run triggered by the OS
scheduler (Windows Task Scheduler / cron) over --every-hours.
"""

from __future__ import annotations

import argparse
import asyncio

from app.db.database import SessionLocal, engine
from app.db.schema_patches import ensure_schema
from app.ingest.registry import INGEST_SOURCES
from app.ingest.runner import DEFAULT_LOOKBACK_DAYS, run_ingestion
from app.stories.service import update_stories


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.ingest",
        description="Fetch AI news, papers, repos and models into raw_items.",
    )

    parser.add_argument(
        "--sources",
        nargs="+",
        choices=[source.key for source in INGEST_SOURCES],
        help="Only run these sources (disabled ones included).",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Lookback window for sources without their own max age.",
    )

    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip fetching full article text / READMEs.",
    )

    parser.add_argument(
        "--no-stories",
        action="store_true",
        help="Skip clustering/triage after ingestion.",
    )

    parser.add_argument(
        "--every-hours",
        type=float,
        help="Repeat the run every N hours until interrupted.",
    )

    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()

    ensure_schema(engine)

    while True:
        try:
            await run_ingestion(
                source_keys=args.sources,
                lookback_days=args.days,
                enrich=not args.no_enrich,
            )

            if not args.no_stories:
                db = SessionLocal()

                try:
                    stats = await update_stories(db)
                    print("[Stories] " + ", ".join(f"{k}={v}" for k, v in stats.items()))
                finally:
                    db.close()

        except Exception as error:
            if not args.every_hours:
                raise

            print(f"[Ingest] run failed: {type(error).__name__}: {error}")

        if not args.every_hours:
            return

        print(f"[Ingest] Next run in {args.every_hours}h")
        await asyncio.sleep(args.every_hours * 3600)


if __name__ == "__main__":
    asyncio.run(_main())
