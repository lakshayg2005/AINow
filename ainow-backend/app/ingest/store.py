from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.embeddings import generate_embeddings
from app.db.models import ItemChunk, RawItem
from app.ingest.chunking import chunk_text
from app.ingest.utils import utcnow
from app.schemas.ingest import IngestedItem


# ============================================================
# Lookup
# ============================================================

def find_existing_urls(
    db: Session,
    items: list[IngestedItem],
) -> set[str]:
    """
    Return the URLs (from `items`) that already have a row,
    matched by URL or by cross-source external id.
    """

    if not items:
        return set()

    urls = list({item.url for item in items})
    external_ids = list({
        item.external_id
        for item in items
        if item.external_id
    })

    rows = db.execute(
        select(
            RawItem.url,
            RawItem.external_id,
        ).where(
            or_(
                RawItem.url.in_(urls),
                RawItem.external_id.in_(external_ids),
            )
        )
    ).all()

    known_urls = {row.url for row in rows}
    known_ids = {
        row.external_id
        for row in rows
        if row.external_id
    }

    return {
        item.url
        for item in items
        if item.url in known_urls
        or (
            item.external_id
            and item.external_id in known_ids
        )
    }


def _find_row(
    db: Session,
    item: IngestedItem,
) -> RawItem | None:
    row = db.scalar(
        select(RawItem).where(
            RawItem.url == item.url
        )
    )

    if row is None and item.external_id:
        row = db.scalar(
            select(RawItem).where(
                RawItem.external_id == item.external_id
            )
        )

    return row


# ============================================================
# Upsert
# ============================================================

def _merge_into(
    row: RawItem,
    item: IngestedItem,
) -> bool:
    """
    Merge a re-fetched item into an existing row.

    Signals are overwritten with the newest values (points and
    stars grow over time). Missing fields are filled; existing
    ones are kept. Returns True if the text content changed.
    """

    signals = dict(row.signals or {})
    signals.update(item.signals)

    seen_in = set(signals.get("seen_in") or [row.source_key])
    seen_in.add(item.source_key)
    signals["seen_in"] = sorted(seen_in)

    row.signals = signals

    row.trust_tier = min(
        row.trust_tier,
        item.trust_tier,
    )

    row.image_url = row.image_url or item.image_url
    row.summary = row.summary or item.summary
    row.discussion_url = row.discussion_url or item.discussion_url
    row.published_at = row.published_at or item.published_at
    row.external_id = row.external_id or item.external_id

    if not row.authors and item.authors:
        row.authors = item.authors

    if item.tags:
        row.tags = sorted(
            set(row.tags or []) | set(item.tags)
        )[:20]

    content_changed = len(item.content or "") > len(row.content or "")

    if content_changed:
        row.content = item.content

    return content_changed


def upsert_items(
    db: Session,
    items: list[IngestedItem],
    enrichment: dict[str, str],
) -> tuple[list[int], list[int], list[int]]:
    """
    Insert new items and merge re-fetched ones.

    Returns (new_ids, updated_ids, reindex_ids), where
    reindex_ids are rows whose text changed and need
    re-chunking/embedding.
    """

    new_rows: list[RawItem] = []
    updated_rows: list[RawItem] = []
    reindex_rows: list[RawItem] = []

    for item in items:
        row = _find_row(db, item)

        if row is not None:
            if _merge_into(row, item):
                reindex_rows.append(row)

            updated_rows.append(row)
            continue

        row = RawItem(
            source_key=item.source_key,
            source_name=item.source_name,
            kind=item.kind,
            category=item.category,
            trust_tier=item.trust_tier,
            url=item.url,
            external_id=item.external_id,
            title=item.title[:1000],
            summary=item.summary,
            content=item.content,
            image_url=item.image_url,
            discussion_url=item.discussion_url,
            authors=item.authors,
            tags=item.tags,
            signals={
                **item.signals,
                "seen_in": [item.source_key],
            },
            published_at=item.published_at,
            fetched_at=utcnow(),
            enrichment_status=enrichment.get(
                item.url,
                "skipped",
            ),
        )

        db.add(row)

        # Flush so a later item in the same batch that shares
        # this URL/external id finds the row instead of
        # violating the unique constraint.
        db.flush()

        new_rows.append(row)
        reindex_rows.append(row)

    db.commit()

    return (
        [row.id for row in new_rows],
        [row.id for row in updated_rows],
        [row.id for row in reindex_rows],
    )


def find_unembedded_ids(
    db: Session,
    exclude: set[int],
    limit: int = 300,
) -> list[int]:
    """
    Rows with no embedding yet — a backlog from an ingest run
    that upserted them but crashed before indexing (e.g. the
    embedding step itself failing). Capped per call so a large
    backlog is worked off over a few runs instead of one huge one.
    """

    query = select(RawItem.id).where(RawItem.embedding.is_(None))

    if exclude:
        query = query.where(RawItem.id.notin_(exclude))

    return list(
        db.scalars(query.order_by(RawItem.id.desc()).limit(limit))
    )


# ============================================================
# Chunk + embed (RAG store)
# ============================================================

# Summaries shorter than this (a bare link, "See comments")
# say nothing about the item; embed the full text instead.
MIN_USEFUL_SUMMARY = 120


def _item_embedding_text(
    row: RawItem,
) -> str:
    summary = row.summary or ""

    if len(summary) >= MIN_USEFUL_SUMMARY or not row.content:
        body = summary
    else:
        body = row.content[:1000]

    return f"{row.title}\n\n{body}".strip()


def index_items(
    db: Session,
    item_ids: list[int],
    batch_size: int = 64,
) -> int:
    """
    (Re)build chunks and embeddings for the given rows.

    Returns the number of chunks written.
    """

    if not item_ids:
        return 0

    rows = db.scalars(
        select(RawItem).where(
            RawItem.id.in_(item_ids)
        )
    ).all()

    # Item-level embeddings: used for clustering and novelty.
    item_vectors = generate_embeddings(
        [_item_embedding_text(row) for row in rows]
    )

    for row, vector in zip(rows, item_vectors):
        row.embedding = vector

    # Chunk-level embeddings: used for grounded generation.
    db.execute(
        delete(ItemChunk).where(
            ItemChunk.raw_item_id.in_(item_ids)
        )
    )

    pending: list[tuple[RawItem, int, str]] = []

    for row in rows:
        text = row.content or row.summary

        for index, chunk in enumerate(chunk_text(text)):
            pending.append((row, index, chunk))

    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]

        # Prefix the title so a chunk like "It scores 92% on
        # MMLU" is still retrievable by the model's name.
        vectors = generate_embeddings(
            [
                f"{row.title}\n\n{chunk}"
                for row, _, chunk in batch
            ]
        )

        for (row, index, chunk), vector in zip(batch, vectors):
            db.add(
                ItemChunk(
                    raw_item_id=row.id,
                    chunk_index=index,
                    content=chunk,
                    embedding=vector,
                )
            )

    db.commit()

    return len(pending)
