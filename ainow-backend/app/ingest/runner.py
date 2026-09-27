from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import timedelta

from app.db.database import SessionLocal
from app.db.models import IngestRun
from app.ingest.enrich import enrich_items
from app.ingest.http import make_client
from app.ingest.registry import IngestSource, get_ingest_sources
from app.ingest.store import (
    find_existing_urls,
    index_items,
    upsert_items,
)
from app.ingest.utils import (
    is_ai_related,
    utcnow,
)
from app.schemas.ingest import IngestedItem


DEFAULT_LOOKBACK_DAYS = 7

# Items dated this far in the future are almost always
# parse errors; drop them rather than pin them to the top.
MAX_FUTURE_SKEW = timedelta(days=1)


# ============================================================
# Filtering
# ============================================================

def filter_items(
    source: IngestSource,
    items: list[IngestedItem],
    lookback_days: int,
) -> list[IngestedItem]:
    now = utcnow()

    since = now - timedelta(
        days=source.max_age_days or lookback_days
    )

    kept: list[IngestedItem] = []

    for item in items:
        published = item.published_at

        # Undated items are kept; enrichment may find a date.
        if published is not None and (
            published < since
            or published > now + MAX_FUTURE_SKEW
        ):
            continue

        if source.ai_filter and not is_ai_related(
            f"{item.title} {item.summary or ''} {' '.join(item.tags)}"
        ):
            continue

        kept.append(item)

    return kept


def dedupe_batch(
    items: list[IngestedItem],
) -> list[IngestedItem]:
    """
    Collapse items within one run that share a URL or
    external id, merging their signals.
    """

    by_key: dict[str, IngestedItem] = {}
    alias: dict[str, str] = {}

    for item in items:
        keys = [item.url]

        if item.external_id:
            keys.append(item.external_id)

        primary = next(
            (alias[key] for key in keys if key in alias),
            None,
        )

        if primary is None:
            by_key[item.url] = item

            for key in keys:
                alias[key] = item.url

            continue

        existing = by_key[primary]
        existing.signals = {
            **existing.signals,
            **item.signals,
        }
        existing.image_url = existing.image_url or item.image_url
        existing.summary = existing.summary or item.summary

        if len(item.content or "") > len(existing.content or ""):
            existing.content = item.content

        for key in keys:
            alias.setdefault(key, primary)

    return list(by_key.values())


# ============================================================
# Run
# ============================================================

async def _fetch_source(
    client,
    source: IngestSource,
    lookback_days: int,
) -> tuple[IngestSource, list[IngestedItem], str | None]:
    since = utcnow() - timedelta(
        days=source.max_age_days or lookback_days
    )

    try:
        items = await source.fetcher(
            client,
            source,
            since,
        )
        return source, items, None

    except Exception as error:
        return (
            source,
            [],
            f"{source.key}: {type(error).__name__}: {error}",
        )


async def run_ingestion(
    source_keys: list[str] | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    enrich: bool = True,
) -> dict:
    """
    Fetch every source, filter, enrich new items, upsert
    into `raw_items`, and chunk + embed new text.

    Returns the run stats (also stored in `ingest_runs`).
    """

    started = time.monotonic()
    sources = get_ingest_sources(source_keys)

    db = SessionLocal()

    run = IngestRun(
        status="running",
        stats={},
        errors=[],
        started_at=utcnow(),
    )
    db.add(run)
    db.commit()

    per_source: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    errors: list[str] = []

    try:
        async with make_client() as client:

            # ------------------------------------------------
            # 1. Fetch all sources concurrently
            # ------------------------------------------------

            results = await asyncio.gather(
                *(
                    _fetch_source(
                        client,
                        source,
                        lookback_days,
                    )
                    for source in sources
                )
            )

            candidates: list[IngestedItem] = []
            source_by_key = {
                source.key: source
                for source in sources
            }

            for source, items, error in results:
                stats = per_source[source.key]
                stats["fetched"] = len(items)

                if error:
                    errors.append(error)
                    stats["error"] = 1
                    print(f"[Ingest] {error}")
                    continue

                kept = filter_items(
                    source,
                    items,
                    lookback_days,
                )

                stats["kept"] = len(kept)
                candidates.extend(kept)

            candidates = dedupe_batch(candidates)

            # ------------------------------------------------
            # 2. Enrich only items we have never seen
            # ------------------------------------------------

            existing = find_existing_urls(
                db,
                candidates,
            )

            new_items = [
                item
                for item in candidates
                if item.url not in existing
                and source_by_key[item.source_key].enrich
            ]

            enrichment: dict[str, str] = {}

            if enrich and new_items:
                print(
                    f"[Ingest] Enriching {len(new_items)} new items..."
                )

                enrichment = await enrich_items(
                    client,
                    new_items,
                )

        # ----------------------------------------------------
        # 3. Re-apply the date window now that enrichment
        #    may have found dates for undated items.
        # ----------------------------------------------------

        final: list[IngestedItem] = []

        for item in candidates:
            source = source_by_key[item.source_key]

            if filter_items(
                source,
                [item],
                lookback_days,
            ):
                final.append(item)

        # ----------------------------------------------------
        # 4. Upsert + index
        # ----------------------------------------------------

        new_ids, updated_ids, reindex_ids = upsert_items(
            db,
            final,
            enrichment,
        )

        new_id_set = set(new_ids)

        for item in final:
            if item.url not in existing:
                per_source[item.source_key]["new"] += 1

        print(
            f"[Ingest] Indexing {len(reindex_ids)} items..."
        )

        chunk_count = index_items(
            db,
            reindex_ids,
        )

        stats = {
            "sources": {
                key: dict(value)
                for key, value in per_source.items()
            },
            "totals": {
                "fetched": sum(s.get("fetched", 0) for s in per_source.values()),
                "kept": len(final),
                "new": len(new_id_set),
                "updated": len(updated_ids),
                "indexed": len(reindex_ids),
                "chunks": chunk_count,
                "enriched": sum(1 for status in enrichment.values() if status == "done"),
                "enrich_failed": sum(1 for status in enrichment.values() if status == "failed"),
                "new_with_image": sum(
                    1
                    for item in final
                    if item.url not in existing and item.image_url
                ),
            },
            "lookback_days": lookback_days,
            "duration_seconds": round(time.monotonic() - started, 1),
        }

        run.status = "completed"
        run.stats = stats
        run.errors = errors
        run.finished_at = utcnow()
        db.commit()

        _print_summary(stats, errors)

        return stats

    except Exception as error:
        db.rollback()

        run.status = "failed"
        run.errors = errors + [f"run: {type(error).__name__}: {error}"]
        run.finished_at = utcnow()
        db.commit()
        raise

    finally:
        db.close()


def _print_summary(
    stats: dict,
    errors: list[str],
) -> None:
    print("\n[Ingest] Per source (fetched / kept / new):")

    for key, value in sorted(stats["sources"].items()):
        marker = "  ERROR" if value.get("error") else ""
        print(
            f"  {key:<22} "
            f"{value.get('fetched', 0):>4} / "
            f"{value.get('kept', 0):>4} / "
            f"{value.get('new', 0):>4}{marker}"
        )

    totals = stats["totals"]

    print(
        "\n[Ingest] Totals: "
        + ", ".join(f"{key}={value}" for key, value in totals.items())
        + f" in {stats['duration_seconds']}s"
    )

    for error in errors:
        print(f"[Ingest] error: {error}")
