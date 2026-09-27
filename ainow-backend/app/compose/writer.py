"""
Section writers. One LLM call per section, grounded in the
retrieved context, citing numbered sources.

Each writer falls back to an extractive version (titles,
triage summaries, abstracts) if no LLM is reachable, so an
issue can always be produced.
"""

from __future__ import annotations

import re
from typing import Any

from app.compose.context import StoryContext
from app.core.free_llm import LLMUnavailable, chat_json
from app.ingest.utils import truncate
from app.schemas.issue import (
    ConceptCard,
    DeepDiveCard,
    DeepDiveSection,
    Engagement,
    QuickNewsCard,
    ResearchCard,
    ResourceCard,
    TrendCard,
)


STYLE_RULES = """Rules:
- Use ONLY facts stated in the provided sources. If a detail is not in the
  sources, leave it out. Never invent numbers, benchmarks, names or dates.
- Cite the sources you used by their numbers in the "refs" list, e.g. [3, 5].
  Never put citation numbers or brackets inside the text itself.
- Write for developers and researchers: concrete and specific. Name the
  model, company, benchmark or number. Say what it is, what it does, and
  what changed.
- Banned phrases: revolutionary, game-changing, groundbreaking, unleash,
  pushing the boundaries, rapid progress, significant advancements,
  in the ever-evolving, landscape.
- Plain text only: no markdown, no URLs.
- Return ONLY valid JSON."""

_INLINE_CITATION = re.compile(
    r"\s*\[(?:S?\d+)(?:\s*,\s*S?\d+)*\]"
)


# ============================================================
# Helpers
# ============================================================

def engagement_for(
    context: StoryContext,
) -> Engagement:
    signals = context.story.signals or {}

    def as_int(key: str) -> int | None:
        value = signals.get(key)
        return int(value) if value else None

    return Engagement(
        hn_points=as_int("hn_points"),
        hf_upvotes=as_int("hf_upvotes"),
        stars=as_int("stars"),
        likes=as_int("likes"),
        source_count=context.story.source_count,
    )


def valid_refs(
    refs: Any,
    context: StoryContext,
) -> list[int]:
    allowed = set(context.ref_ids)

    cleaned = []

    for ref in refs if isinstance(refs, list) else []:
        try:
            value = int(str(ref).strip("[]S "))
        except ValueError:
            continue

        if value in allowed and value not in cleaned:
            cleaned.append(value)

    # A card must always point somewhere.
    return cleaned or context.ref_ids[:1]


def _entries_by_story(
    data: Any,
) -> dict[int, dict]:
    entries = data.get("items", []) if isinstance(data, dict) else data or []
    by_story: dict[int, dict] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        try:
            by_story.setdefault(int(entry.get("story_id")), entry)
        except (TypeError, ValueError):
            continue

    return by_story


def _text(
    entry: dict,
    key: str,
    limit: int = 700,
) -> str:
    # Inline "[16]" citations use pre-renumbering ids; refs
    # carry citations instead.
    value = _INLINE_CITATION.sub("", str(entry.get(key) or ""))
    return truncate(" ".join(value.split()), limit) or ""


def _prose(
    entry: dict,
    key: str,
    limit: int = 700,
) -> str:
    """Sentence text: like _text, but always ends with punctuation."""

    value = _text(entry, key, limit)

    if value and value[-1].isalnum():
        value += "."

    return value


def _fallback_summary(
    context: StoryContext,
) -> str:
    story = context.story

    if story.summary:
        return story.summary

    for item in context.candidate.items:
        if item.summary:
            return truncate(item.summary, 300)

    return ""


def _primary_item(
    context: StoryContext,
):
    items = context.candidate.items

    for kind in ("repo", "model", "space", "paper", "article", "discussion"):
        for item in items:
            if item.kind == kind:
                return item

    return items[0] if items else None


async def _call(
    system: str,
    user: str,
    max_tokens: int,
    models: set[str],
) -> Any | None:
    try:
        data, model = await chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tier="strong",
            max_tokens=max_tokens,
            temperature=0.3,
        )
        models.add(model)
        return data

    except LLMUnavailable as error:
        print(f"[Writer] LLM unavailable, using extractive fallback: {error}")
        return None


def _join_contexts(
    contexts: list[StoryContext],
) -> str:
    return "\n\n==========\n\n".join(context.text for context in contexts)


# ============================================================
# Quick News
# ============================================================

QUICK_NEWS_SYSTEM = f"""You are the news editor of AINow, a weekly AI newsletter.
Write one Quick News card per story.

For each story:
- headline: 7-12 words, a complete news headline with a verb that names who
  did what. Good: "OpenAI ships GPT-6 Sol and Luna, now on Amazon Bedrock".
  Bad: "GPT-6 Sol and Luna", "Pentagon blames AI".
- summary: 2 sentences on what happened.
- why_it_matters: 1 sentence on the consequence for people building with AI.
- If a story says PREVIOUSLY COVERED, write only what is new, and start the
  headline with "Update:".

{STYLE_RULES}

JSON format:
{{"items": [{{"story_id": <id>, "headline": "...", "summary": "...",
"why_it_matters": "...", "refs": [<source numbers>]}}]}}"""


async def write_quick_news(
    contexts: list[StoryContext],
    models: set[str],
) -> list[QuickNewsCard]:
    if not contexts:
        return []

    data = await _call(
        QUICK_NEWS_SYSTEM,
        f"Write Quick News cards for these {len(contexts)} stories.\n\n"
        + _join_contexts(contexts),
        max_tokens=2500,
        models=models,
    )

    entries = _entries_by_story(data) if data is not None else {}
    cards = []

    for context in contexts:
        story = context.story
        entry = entries.get(story.id)

        if entry and _text(entry, "headline") and _prose(entry, "summary"):
            headline = _text(entry, "headline", 160)
            summary = _prose(entry, "summary")
            why = _prose(entry, "why_it_matters", 400)
            refs = valid_refs(entry.get("refs"), context)
        else:
            headline = story.title
            summary = _fallback_summary(context)
            why = ""
            refs = context.ref_ids[:2]

        cards.append(
            QuickNewsCard(
                story_id=story.id,
                headline=headline,
                summary=summary,
                why_it_matters=why,
                category=story.category or "other",
                image_url=story.image_url,
                is_update=context.candidate.novelty.status == "update",
                engagement=engagement_for(context),
                refs=refs,
            )
        )

    return cards


# ============================================================
# Research (spotlight + paper of the week)
# ============================================================

RESEARCH_SYSTEM = f"""You are the research editor of AINow, a weekly AI newsletter.
Explain each paper for engineers who did not read it.

For each paper:
- problem: 1-2 sentences on the problem it tackles.
- core_idea: 1-2 sentences on the method.
- key_result: 1-2 sentences on the main result, only as stated in the source.
- why_it_matters: 1 sentence.

{STYLE_RULES}

JSON format:
{{"items": [{{"story_id": <id>, "problem": "...",
"core_idea": "...", "key_result": "...", "why_it_matters": "...",
"refs": [<source numbers>]}}]}}"""


def _paper_meta(
    context: StoryContext,
) -> tuple[list[str], str | None]:
    for item in context.candidate.items:
        if item.kind == "paper":
            url = item.url

            if item.external_id and item.external_id.startswith("arxiv:"):
                url = f"https://arxiv.org/abs/{item.external_id.split(':', 1)[1]}"

            return list(item.authors or [])[:6], url

    return [], None


async def write_research(
    contexts: list[StoryContext],
    models: set[str],
) -> list[ResearchCard]:
    if not contexts:
        return []

    data = await _call(
        RESEARCH_SYSTEM,
        f"Explain these {len(contexts)} papers.\n\n" + _join_contexts(contexts),
        max_tokens=2500,
        models=models,
    )

    entries = _entries_by_story(data) if data is not None else {}
    cards = []

    for context in contexts:
        story = context.story
        entry = entries.get(story.id) or {}
        authors, paper_url = _paper_meta(context)

        cards.append(
            ResearchCard(
                story_id=story.id,
                # The real paper title; models abbreviate ("RRSI").
                title=story.title,
                problem=_prose(entry, "problem"),
                core_idea=_prose(entry, "core_idea") or _fallback_summary(context),
                key_result=_prose(entry, "key_result"),
                why_it_matters=_prose(entry, "why_it_matters", 400),
                authors=authors,
                paper_url=paper_url,
                image_url=story.image_url,
                engagement=engagement_for(context),
                refs=valid_refs(entry.get("refs"), context),
            )
        )

    return cards


# ============================================================
# Deep Dive
# ============================================================

DEEP_DIVE_SYSTEM = f"""You are the features editor of AINow, a weekly AI newsletter.
Write this week's Deep Dive: a clear, technical explainer of one story,
drawing on all the sources provided.

Every field except title must be a full paragraph of 3-5 sentences
(60-120 words). Use the specific facts, names and numbers in the sources.

Fields:
- title: an informative title, at most 12 words.
- introduction: what happened and why it is the story of the week.
- background: the context a reader needs.
- how_it_works: the technical substance, as far as the sources explain it.
- impact: who is affected and how.
- what_to_watch: open questions and what to look for next.

{STYLE_RULES}

JSON format:
{{"title": "...", "introduction": "...", "background": "...",
"how_it_works": "...", "impact": "...", "what_to_watch": "...",
"refs": [<source numbers>]}}"""

DEEP_DIVE_HEADINGS = (
    ("background", "Background"),
    ("how_it_works", "How it works"),
    ("impact", "Impact"),
    ("what_to_watch", "What to watch"),
)


async def write_deep_dive(
    context: StoryContext | None,
    models: set[str],
) -> DeepDiveCard | None:
    if context is None:
        return None

    data = await _call(
        DEEP_DIVE_SYSTEM,
        "Write the Deep Dive for this story.\n\n" + context.text,
        max_tokens=2500,
        models=models,
    )

    entry = data if isinstance(data, dict) else {}

    if not _prose(entry, "introduction"):
        # Without an LLM a deep dive would just repeat the
        # sources; better to omit the section.
        return None

    return DeepDiveCard(
        story_id=context.story.id,
        title=_text(entry, "title", 200) or context.story.title,
        introduction=_prose(entry, "introduction", 1500),
        sections=[
            DeepDiveSection(heading=heading, body=_prose(entry, key, 1500))
            for key, heading in DEEP_DIVE_HEADINGS
            if _text(entry, key)
        ],
        image_url=context.story.image_url,
        refs=valid_refs(entry.get("refs"), context),
    )


# ============================================================
# Resources
# ============================================================

RESOURCES_SYSTEM = f"""You are the tools editor of AINow, a weekly AI newsletter.
Write one card per resource (open-source repo, model or demo).

For each:
- name: the project name as it appears in the sources.
- description: 1-2 sentences on what it is and does.
- why_useful: 1 sentence on who should try it and for what.

{STYLE_RULES}

JSON format:
{{"items": [{{"story_id": <id>, "name": "...", "description": "...",
"why_useful": "...", "refs": [<source numbers>]}}]}}"""

RESOURCE_TYPES = {
    "repo": "GitHub repo",
    "model": "Model",
    "space": "Demo",
}


async def write_resources(
    contexts: list[StoryContext],
    models: set[str],
) -> list[ResourceCard]:
    if not contexts:
        return []

    data = await _call(
        RESOURCES_SYSTEM,
        f"Write cards for these {len(contexts)} resources.\n\n"
        + _join_contexts(contexts),
        max_tokens=1500,
        models=models,
    )

    entries = _entries_by_story(data) if data is not None else {}
    cards = []

    for context in contexts:
        story = context.story
        entry = entries.get(story.id) or {}
        primary = _primary_item(context)

        if primary is None:
            continue

        cards.append(
            ResourceCard(
                story_id=story.id,
                name=_text(entry, "name", 120) or story.title,
                resource_type=RESOURCE_TYPES.get(primary.kind, "Tool"),
                description=_prose(entry, "description") or _fallback_summary(context),
                why_useful=_prose(entry, "why_useful", 400),
                url=primary.url,
                image_url=story.image_url,
                engagement=engagement_for(context),
                refs=valid_refs(entry.get("refs"), context),
            )
        )

    return cards


# ============================================================
# Editor: headline, intro, trends, concept, our take
# ============================================================

EDITOR_SYSTEM = """You are the editor-in-chief of AINow, a weekly AI newsletter for
developers and researchers. You receive this issue's stories plus other
notable stories of the week.

Produce:
- headline: at most 10 words naming the week's biggest specific story or
  tension. Good: "Opus 5.5 and GPT-6 Sol open an AI price war".
  Bad: "AI Models Advance", "A Big Week in AI".
- intro: 2-3 sentences that tell readers the 2-3 most important things that
  happened this week, by name. No throat-clearing ("Welcome to...").
- trends: exactly 2 specific, non-obvious patterns, each supported by at
  least 2 listed stories. Good: "Frontier labs are competing on price, not
  just capability". Bad: "Advancements in AI Models", "AI Safety and Risk".
  Each: title, explanation (2 sentences), evidence (1 sentence that names
  the stories in words; never mention ids), story_ids (at least 2 ids).
- concept: one AI concept a reader needs to understand one of this issue's
  top stories (prefer the deep dive or a quick news story). Fields: concept,
  simple_explanation (2 sentences, no jargon), technical_explanation (2-3
  sentences), example (1 sentence tied to the story), related_story_id.
  General background knowledge is allowed here.
- our_take: an opinionated but fair editorial, 80-120 words, with a clear
  point of view about what this week means for people building with AI.
  Reference specific stories. You may connect to earlier issues listed below.

Only use facts from the story list for anything about this week's events.
Banned phrases: pushing the boundaries, rapid progress, significant
advancements, it is essential, landscape, game-changing.
Plain text only. Return ONLY valid JSON:
{"headline": "...", "intro": "...",
 "trends": [{"title": "...", "explanation": "...", "evidence": "...",
             "story_ids": [<ids>]}],
 "concept": {"concept": "...", "simple_explanation": "...",
             "technical_explanation": "...", "example": "...",
             "related_story_id": <id>},
 "our_take": "..."}"""


def editor_prompt(
    issue_lines: list[str],
    pool_lines: list[str],
    history_lines: list[str],
) -> str:
    parts = [
        "THIS ISSUE'S STORIES:\n" + "\n".join(issue_lines),
        "OTHER NOTABLE STORIES THIS WEEK:\n" + "\n".join(pool_lines),
    ]

    if history_lines:
        parts.append(
            "RECENT EARLIER ISSUES COVERED:\n" + "\n".join(history_lines)
        )

    return "\n\n".join(parts)


async def write_editorial(
    prompt: str,
    valid_story_ids: set[int],
    story_refs: dict[int, list[int]],
    models: set[str],
) -> dict:
    data = await _call(
        EDITOR_SYSTEM,
        prompt,
        max_tokens=2000,
        models=models,
    )

    entry = data if isinstance(data, dict) else {}

    trends = []

    for trend in entry.get("trends") or []:
        if not isinstance(trend, dict):
            continue

        ids = []

        for value in trend.get("story_ids") or []:
            try:
                story_id = int(value)
            except (TypeError, ValueError):
                continue

            if story_id in valid_story_ids and story_id not in ids:
                ids.append(story_id)

        # A trend needs at least two stories behind it.
        if len(ids) < 2 or not _text(trend, "title"):
            continue

        refs = []

        for story_id in ids:
            refs.extend(
                ref for ref in story_refs.get(story_id, [])[:1] if ref not in refs
            )

        trends.append(
            TrendCard(
                title=_text(trend, "title", 120),
                explanation=_prose(trend, "explanation"),
                evidence=_prose(trend, "evidence", 500),
                story_ids=ids,
                refs=refs,
            )
        )

    concept = None
    raw_concept = entry.get("concept")

    if isinstance(raw_concept, dict) and _text(raw_concept, "concept"):
        related = raw_concept.get("related_story_id")

        try:
            related = int(related) if int(related) in valid_story_ids else None
        except (TypeError, ValueError):
            related = None

        concept = ConceptCard(
            concept=_text(raw_concept, "concept", 120),
            simple_explanation=_prose(raw_concept, "simple_explanation"),
            technical_explanation=_prose(raw_concept, "technical_explanation", 900),
            example=_prose(raw_concept, "example", 500),
            related_story_id=related,
        )

    return {
        "headline": _text(entry, "headline", 120),
        "intro": _prose(entry, "intro", 600),
        "trends": trends[:2],
        "concept": concept,
        "our_take": _prose(entry, "our_take", 1000),
    }
