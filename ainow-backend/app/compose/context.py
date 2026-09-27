"""
Build grounded context for the writer (the "R" in RAG).

For each story, pick up to MAX_SOURCES member items from
distinct outlets, then pull the chunks of those items most
relevant to what the section needs, via pgvector.

Sources are numbered across the whole issue ([1], [2], ...);
the writer cites those numbers and never produces URLs.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.embeddings import generate_embedding
from app.db.models import ItemChunk, RawItem
from app.compose.selection import Candidate
from app.schemas.issue import SourceRef
from app.stories.scoring import is_official_repo


MAX_SOURCES = 4
CHUNKS_PER_SOURCE = 3


# ============================================================
# Issue-wide source numbering
# ============================================================

def _outlet_name(
    item: RawItem,
) -> str:
    """
    Name the outlet readers will land on. An HN item linking
    to cnbc.com is a CNBC source, not a Hacker News one.
    """

    host = _host(item.url)

    if item.source_key == "hackernews" and host != "news.ycombinator.com":
        return host

    return item.source_name

class SourceRegistry:
    def __init__(self) -> None:
        self._by_url: dict[str, SourceRef] = {}

    def ref(
        self,
        item: RawItem,
    ) -> SourceRef:
        existing = self._by_url.get(item.url)

        if existing:
            return existing

        ref = SourceRef(
            id=len(self._by_url) + 1,
            title=item.title[:300],
            url=item.url,
            source_name=_outlet_name(item),
        )
        self._by_url[item.url] = ref

        return ref

    def all(self) -> list[SourceRef]:
        return sorted(self._by_url.values(), key=lambda ref: ref.id)

    def ids(self) -> set[int]:
        return {ref.id for ref in self._by_url.values()}


# ============================================================
# Story context
# ============================================================

@dataclass
class StoryContext:
    candidate: Candidate
    refs: list[SourceRef] = field(default_factory=list)
    text: str = ""

    @property
    def story(self):
        return self.candidate.story

    @property
    def ref_ids(self) -> list[int]:
        return [ref.id for ref in self.refs]


def _host(url: str) -> str:
    return urlparse(url).netloc.removeprefix("www.")


def _signal_strength(
    item: RawItem,
) -> float:
    signals = item.signals or {}

    return max(
        float(signals.get(key) or 0)
        for key in ("hn_points", "hf_upvotes", "stars", "likes")
    )


def _pick_sources(
    items: list[RawItem],
    limit: int,
    story_title: str = "",
) -> list[RawItem]:
    """
    Prefer primary sources (the lab's post, the official
    model/repo), then well-discussed and text-rich items, one
    per outlet, so the writer sees several perspectives.
    """

    ranked = sorted(
        items,
        key=lambda item: (
            0 if item.category == "company" else 1,
            0 if is_official_repo(item, story_title) else 1,
            item.trust_tier,
            0 if len(item.content or "") >= 500 else 1,
            -_signal_strength(item),
            -len(item.content or item.summary or ""),
        ),
    )

    picked: list[RawItem] = []
    hosts: set[str] = set()

    for item in ranked:
        host = _host(item.url)

        if host in hosts:
            continue

        picked.append(item)
        hosts.add(host)

        if len(picked) >= limit:
            break

    return picked


def _relevant_chunks(
    db: Session,
    items: list[RawItem],
    query: str,
) -> dict[int, list[str]]:
    if not items:
        return {}

    query_vector = generate_embedding(query)

    rows = db.execute(
        select(
            ItemChunk.raw_item_id,
            ItemChunk.chunk_index,
            ItemChunk.content,
        )
        .where(ItemChunk.raw_item_id.in_([item.id for item in items]))
        .order_by(ItemChunk.embedding.cosine_distance(query_vector))
        .limit(CHUNKS_PER_SOURCE * len(items) * 2)
    ).all()

    chunks: dict[int, list[tuple[int, str]]] = defaultdict(list)

    for item_id, index, content in rows:
        if len(chunks[item_id]) < CHUNKS_PER_SOURCE:
            chunks[item_id].append((index, content))

    # Keep document order inside each source for readability.
    return {
        item_id: [content for _, content in sorted(pairs)]
        for item_id, pairs in chunks.items()
    }


def build_story_context(
    db: Session,
    candidate: Candidate,
    registry: SourceRegistry,
    need: str,
    max_chars: int = 4000,
    max_sources: int = MAX_SOURCES,
) -> StoryContext:
    """
    `need` describes what the section wants (e.g. "key
    technical details and results") and steers retrieval.
    """

    story = candidate.story
    sources = _pick_sources(candidate.items, max_sources, story.title)

    chunks = _relevant_chunks(
        db,
        sources,
        f"{story.title}. {need}",
    )

    per_source = max(600, max_chars // max(1, len(sources)))
    blocks: list[str] = []
    refs: list[SourceRef] = []

    for item in sources:
        ref = registry.ref(item)
        refs.append(ref)

        date = (
            item.published_at.strftime("%Y-%m-%d")
            if item.published_at
            else "undated"
        )

        body = "\n".join(chunks.get(item.id) or [])

        if not body:
            body = item.summary or item.content or ""

        # Always include the summary: it is often the densest
        # statement of what happened.
        if item.summary and item.summary[:80] not in body:
            body = f"{item.summary}\n{body}"

        blocks.append(
            f"[{ref.id}] {item.source_name} — {item.title} ({date})\n"
            f"{body[:per_source].strip()}"
        )

    header = f"STORY {story.id}: {story.title}"

    if candidate.novelty.status == "update" and candidate.novelty.covered:
        header += (
            "\nPREVIOUSLY COVERED — we already told readers: "
            f"\"{candidate.novelty.covered.headline}: "
            f"{candidate.novelty.covered.summary or ''}\". "
            "Write ONLY what is new since then."
        )

    return StoryContext(
        candidate=candidate,
        refs=refs,
        text=header + "\n\n" + "\n\n".join(blocks),
    )
