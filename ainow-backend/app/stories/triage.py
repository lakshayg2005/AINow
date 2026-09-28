"""
Story triage: category, importance (1-10), promotional flag
and a one-line factual summary.

Uses the free "fast" LLM chain in batches. If no provider is
available, falls back to rules so the pipeline never blocks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.free_llm import LLMUnavailable, chat_json
from app.db.models import RawItem, Story
from app.ingest.utils import truncate, utcnow
from app.stories.scoring import buzz_score, coverage_score


TRIAGE_BATCH_SIZE = 12

StoryCategory = Literal[
    "model_release",
    "research",
    "product",
    "open_source",
    "tool",
    "industry",
    "policy",
    "safety",
    "benchmark",
    "tutorial",
    "opinion",
    "other",
]

CATEGORIES = StoryCategory.__args__


class TriageDecision(BaseModel):
    id: int
    category: StoryCategory = "other"
    importance: int = Field(ge=1, le=10)
    promotional: bool = False
    summary: str = ""

    @field_validator("category", mode="before")
    @classmethod
    def _known_category(cls, value):
        value = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
        return value if value in CATEGORIES else "other"

    @field_validator("importance", mode="before")
    @classmethod
    def _clamp_importance(cls, value):
        return min(10, max(1, int(float(value))))


@dataclass
class TriageStats:
    llm: int = 0
    heuristic: int = 0
    failed_batches: int = 0
    models: set[str] = field(default_factory=set)


# ============================================================
# Prompt
# ============================================================

SYSTEM_PROMPT = f"""You are the news triage editor for AINow, a weekly AI newsletter
for developers and researchers. For each story, decide how much it matters
to people who build with and study AI.

importance (1-10):
 10    landmark: new frontier model from a top lab, major breakthrough
 8-9   major release or result from a leading lab/company; major policy or
       legal decision affecting AI; widely discussed incident
 6-7   notable open model, significant paper, genuinely useful new tool,
       meaningful funding or acquisition
 4-5   incremental paper, minor product update, niche tool
 1-3   marketing, customer case study, listicle, low-effort or spam repo,
       tangential to AI

promotional: true for marketing, customer/partner case studies, sponsored
posts, self-promotion and "awesome-*" link lists.

category: one of {", ".join(CATEGORIES)}.

summary: ONE factual sentence (max 30 words) using only the supplied text.
Never invent numbers or names.

Engagement numbers are hints, not proof of importance.

Return ONLY JSON:
{{"stories": [{{"id": <id>, "category": "...", "importance": <1-10>,
"promotional": <bool>, "summary": "..."}}]}}"""


def _signal_text(
    story: Story,
) -> str:
    signals = story.signals or {}
    parts = []

    labels = (
        ("hn_points", "HN points"),
        ("hf_upvotes", "HF upvotes"),
        ("stars", "GitHub stars"),
        ("likes", "HF likes"),
    )

    for key, label in labels:
        if signals.get(key):
            parts.append(f"{label}: {int(signals[key])}")

    parts.append(f"sources: {story.source_count}")

    return ", ".join(parts)


def _snippet(
    items: list[RawItem],
) -> str:
    ordered = sorted(
        items,
        key=lambda item: (
            item.trust_tier,
            -len(item.summary or item.content or ""),
        ),
    )

    for item in ordered:
        text = item.summary or item.content

        if text and len(text) > 40:
            return truncate(" ".join(text.split()), 450)

    return ""


def _story_block(
    story: Story,
    items: list[RawItem],
) -> str:
    source_names = sorted({item.source_name for item in items})

    return (
        f"ID: {story.id}\n"
        f"Title: {story.title}\n"
        f"Reported by: {', '.join(source_names[:6])}\n"
        f"Kinds: {', '.join((story.signals or {}).get('kinds') or [])}\n"
        f"Engagement: {_signal_text(story)}\n"
        f"Text: {_snippet(items)}"
    )


# ============================================================
# Heuristic fallback
# ============================================================

_POLICY = re.compile(
    r"\b(court|lawsuit|sue[sd]?|regulat\w*|law|bill|senate|congress|"
    r"government|pentagon|ftc|eu|ban|antitrust|copyright)\b",
    re.IGNORECASE,
)
_SAFETY = re.compile(
    r"\b(safety|alignment|jailbreak|misuse|hack\w*|attack\w*|security|risk)\b",
    re.IGNORECASE,
)
_RELEASE = re.compile(
    r"\b(introduc\w*|launch\w*|releas\w*|unveil\w*|announc\w*|now available|debuts?)\b",
    re.IGNORECASE,
)
_INDUSTRY = re.compile(
    r"\b(raises|funding|acqui\w*|valuation|ipo|revenue|layoffs?|deal)\b",
    re.IGNORECASE,
)
_BENCHMARK = re.compile(
    r"\b(benchmark|leaderboard|arena|eval\w*)\b",
    re.IGNORECASE,
)


def heuristic_decision(
    story: Story,
) -> TriageDecision:
    kinds = set((story.signals or {}).get("kinds") or [])
    title = story.title

    if "paper" in kinds:
        category = "research"
    elif _POLICY.search(title):
        category = "policy"
    elif _SAFETY.search(title):
        category = "safety"
    elif _BENCHMARK.search(title):
        category = "benchmark"
    elif _INDUSTRY.search(title):
        category = "industry"
    elif "model" in kinds or (_RELEASE.search(title) and story.entities):
        category = "model_release"
    elif "repo" in kinds:
        category = "open_source"
    elif "space" in kinds:
        category = "tool"
    else:
        category = "industry"

    signals = story.signals or {}

    importance = round(
        2
        + 5 * buzz_score(signals)
        + 2 * coverage_score(
            story.source_count,
            int(signals.get("tier1_count") or 0),
        )
    )

    return TriageDecision(
        id=story.id,
        category=category,
        importance=min(9, importance),
        promotional=title.lower().startswith("awesome") or "/awesome" in title.lower(),
        summary="",
    )


# ============================================================
# Apply
# ============================================================

def _apply(
    story: Story,
    decision: TriageDecision,
    method: str,
) -> None:
    story.category = decision.category
    story.importance = decision.importance
    story.is_promotional = decision.promotional
    story.summary = decision.summary or story.summary
    story.triage_method = method[:100]
    story.triaged_at = utcnow()
    story.triaged_item_count = story.item_count


async def triage_stories(
    stories: list[Story],
    items_by_story: dict[int, list[RawItem]],
    use_llm: bool = True,
) -> TriageStats:
    stats = TriageStats()
    llm_available = use_llm

    for start in range(0, len(stories), TRIAGE_BATCH_SIZE):
        batch = stories[start:start + TRIAGE_BATCH_SIZE]
        decided: set[int] = set()

        if llm_available:
            blocks = "\n\n---\n\n".join(
                _story_block(story, items_by_story.get(story.id, []))
                for story in batch
            )

            try:
                data, model = await chat_json(
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"Triage these {len(batch)} stories:\n\n{blocks}",
                        },
                    ],
                    tier="fast",
                    max_tokens=2500,
                )

                entries = data.get("stories", []) if isinstance(data, dict) else data
                by_id = {story.id: story for story in batch}

                for entry in entries or []:
                    try:
                        decision = TriageDecision.model_validate(entry)
                    except (ValidationError, TypeError, ValueError):
                        continue

                    story = by_id.get(decision.id)

                    if story is None or story.id in decided:
                        continue

                    _apply(story, decision, f"llm:{model}")
                    decided.add(story.id)
                    stats.llm += 1

                stats.models.add(model)

            except LLMUnavailable as error:
                print(f"[Triage] LLM unavailable, using rules: {error}")
                llm_available = False
                stats.failed_batches += 1

        # Anything the LLM skipped or couldn't handle.
        for story in batch:
            if story.id not in decided:
                _apply(story, heuristic_decision(story), "heuristic")
                stats.heuristic += 1

        print(
            f"[Triage] {min(start + TRIAGE_BATCH_SIZE, len(stories))}/{len(stories)} stories"
        )

    return stats
