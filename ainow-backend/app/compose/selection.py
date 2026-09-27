"""
Assign this week's ranked, fresh stories to newsletter
sections. Sections take fewer items rather than filler when a
week is thin.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RawItem, Story
from app.stories.novelty import NoveltyResult
from app.stories.service import top_stories


QUICK_NEWS_COUNT = 5
RESEARCH_COUNT = 3
RESOURCE_COUNT = 3

POOL_SIZE = 80

MIN_NEWS_IMPORTANCE = 5
MIN_RESEARCH_IMPORTANCE = 4
MAX_PER_CATEGORY = 2

NEWS_CATEGORIES = {
    "model_release",
    "product",
    "industry",
    "policy",
    "safety",
    "benchmark",
    "research",
    "other",
}

RESOURCE_CATEGORIES = {
    "open_source",
    "tool",
    "tutorial",
}

RESOURCE_KINDS = {
    "repo",
    "model",
    "space",
}


@dataclass
class Candidate:
    story: Story
    novelty: NoveltyResult
    items: list[RawItem]

    @property
    def kinds(self) -> set[str]:
        return {item.kind for item in self.items}

    @property
    def importance(self) -> int:
        return self.story.importance or 4

    @property
    def is_paper(self) -> bool:
        return "paper" in self.kinds and self.story.category == "research"

    @property
    def is_resource(self) -> bool:
        # A launch covered by articles is news, even if it
        # also has a model card; a lone repo/model is a resource.
        return (
            self.story.category in RESOURCE_CATEGORIES
            or bool(self.kinds & RESOURCE_KINDS)
        ) and not ({"article", "discussion"} & self.kinds)

    @property
    def text_chars(self) -> int:
        return sum(
            len(item.content or item.summary or "")
            for item in self.items
        )


@dataclass
class Selection:
    quick_news: list[Candidate] = field(default_factory=list)
    research: list[Candidate] = field(default_factory=list)
    paper_of_week: Candidate | None = None
    deep_dive: Candidate | None = None
    resources: list[Candidate] = field(default_factory=list)

    # Everything eligible, for trends / editor context.
    pool: list[Candidate] = field(default_factory=list)

    def chosen(self) -> list[Candidate]:
        chosen = list(self.quick_news) + list(self.research) + list(self.resources)

        for candidate in (self.paper_of_week, self.deep_dive):
            if candidate is not None:
                chosen.append(candidate)

        return chosen


def _take_diverse(
    candidates: list[Candidate],
    count: int,
    key=lambda candidate: candidate.story.category,
    per_key: int = MAX_PER_CATEGORY,
    always_take: int = 0,
) -> list[Candidate]:
    """
    Take `count` candidates, at most `per_key` per group. The
    first `always_take` are exempt: diversity must never cost
    the week's biggest stories.
    """

    taken: list[Candidate] = []
    seen: Counter = Counter()

    for index, candidate in enumerate(candidates):
        group = key(candidate)

        if index >= always_take and seen[group] >= per_key:
            continue

        taken.append(candidate)
        seen[group] += 1

        if len(taken) >= count:
            break

    return taken


DEEP_DIVE_MIN_SOURCES = 2
DEEP_DIVE_MIN_CHARS = 3000


def _deep_dive_key(
    candidate: Candidate,
) -> tuple:
    # A deep dive needs material: several sources and real
    # text. Among those, importance plus breadth of coverage.
    explainable = (
        candidate.story.source_count >= DEEP_DIVE_MIN_SOURCES
        and candidate.text_chars >= DEEP_DIVE_MIN_CHARS
    )

    return (
        explainable,
        candidate.importance + min(candidate.story.source_count, 4),
        min(candidate.text_chars, 30000) // 10000,
        candidate.story.score,
    )


def build_candidates(
    db: Session,
    window_days: int = 7,
    pool_size: int = POOL_SIZE,
) -> list[Candidate]:
    ranked: list[tuple[Story, NoveltyResult]] = top_stories(
        db,
        limit=pool_size,
        window_days=window_days,
    )

    story_ids = [story.id for story, _ in ranked]
    items_by_story: dict[int, list[RawItem]] = defaultdict(list)

    if story_ids:
        for item in db.scalars(
            select(RawItem).where(RawItem.story_id.in_(story_ids))
        ):
            items_by_story[item.story_id].append(item)

    return [
        Candidate(
            story=story,
            novelty=novelty,
            items=items_by_story.get(story.id, []),
        )
        for story, novelty in ranked
        if not story.is_promotional
    ]


def select_sections(
    candidates: list[Candidate],
) -> Selection:
    selection = Selection(pool=candidates)
    used: set[int] = set()

    def available(pool):
        return [c for c in pool if c.story.id not in used]

    # --------------------------------------------------------
    # Research: Paper of the Week + spotlight
    # --------------------------------------------------------

    papers = [
        candidate
        for candidate in candidates
        if candidate.is_paper and candidate.importance >= MIN_RESEARCH_IMPORTANCE
    ]

    if papers:
        selection.paper_of_week = max(
            papers[:6],
            key=lambda c: (
                c.importance,
                float((c.story.signals or {}).get("hf_upvotes") or 0),
            ),
        )
        used.add(selection.paper_of_week.story.id)

    selection.research = available(papers)[:RESEARCH_COUNT]
    used.update(c.story.id for c in selection.research)

    # --------------------------------------------------------
    # News: Deep Dive + Quick News
    # --------------------------------------------------------

    news = [
        candidate
        for candidate in available(candidates)
        if not candidate.is_paper
        and not candidate.is_resource
        and candidate.story.category in NEWS_CATEGORIES
        and candidate.importance >= MIN_NEWS_IMPORTANCE
    ]

    if news:
        selection.deep_dive = max(news[:8], key=_deep_dive_key)
        used.add(selection.deep_dive.story.id)

    selection.quick_news = _take_diverse(
        available(news),
        QUICK_NEWS_COUNT,
        always_take=3,
    )
    used.update(c.story.id for c in selection.quick_news)

    # --------------------------------------------------------
    # Resources
    # --------------------------------------------------------

    resources = [
        candidate
        for candidate in available(candidates)
        if candidate.is_resource
    ]

    selection.resources = _take_diverse(
        resources,
        RESOURCE_COUNT,
        key=lambda c: min(c.kinds) if c.kinds else "",
        per_key=2,
    )

    return selection
