"""
Review a draft before an editor reads it.

Two layers:

    structural checks - deterministic: missing or thin sections,
                        uncited cards, a story used twice, images
    model review      - one free-LLM call that grades the draft
                        against each story's own summary for
                        consistency, specificity, redundancy
                        and tone, and lists concrete fixes

The review is advisory. It is stored with the draft and shown
in the admin newsroom; publishing never depends on it.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.free_llm import LLMUnavailable, chat_json
from app.db.models import Story
from app.ingest.utils import truncate, utcnow
from app.schemas.issue import IssueContent, IssueReview, ReviewNote


SECTIONS = (
    "headline",
    "intro",
    "quick_news",
    "research_spotlight",
    "paper_of_week",
    "deep_dive",
    "trends",
    "concept",
    "resources",
    "our_take",
)

MIN_QUICK_NEWS = 4
MAX_HEADLINE_CHARS = 110
MAX_NOTES = 8


# ============================================================
# Structural checks
# ============================================================

def structural_checks(
    content: IssueContent,
) -> list[ReviewNote]:
    notes: list[ReviewNote] = []

    def add(section: str, note: str, severity: str = "fix", item: str = "") -> None:
        notes.append(ReviewNote(section=section, note=note, severity=severity, item=item))

    # --------------------------------------------------------
    # Headline and intro
    # --------------------------------------------------------

    if not content.headline:
        add("headline", "The issue has no headline.")
    elif len(content.headline) > MAX_HEADLINE_CHARS:
        add("headline", f"Headline is {len(content.headline)} characters; email clients cut it off.", "consider")

    if not content.intro:
        add("intro", "The issue has no intro.")

    # --------------------------------------------------------
    # Sections present
    # --------------------------------------------------------

    if len(content.quick_news) < MIN_QUICK_NEWS:
        add("quick_news", f"Only {len(content.quick_news)} Quick News items (aim for {MIN_QUICK_NEWS}+).")

    if not content.deep_dive:
        add("deep_dive", "No Deep Dive this week.")
    elif len(content.deep_dive.sections) < 2:
        add("deep_dive", "The Deep Dive has fewer than two sections.", item=content.deep_dive.title)

    if not content.paper_of_week:
        add("paper_of_week", "No Paper of the Week.", "consider")

    if not content.research_spotlight:
        add("research_spotlight", "Research Spotlight is empty.", "consider")

    if not content.trends:
        add("trends", "No trends were identified.", "consider")

    if not content.concept:
        add("concept", "No concept explainer.", "consider")

    if not content.resources:
        add("resources", "No resources this week.", "consider")

    if not content.our_take:
        add("our_take", "Our Take is empty.", "consider")

    # --------------------------------------------------------
    # Per-card checks
    # --------------------------------------------------------

    cards: list[tuple[str, Any, str]] = (
        [("quick_news", card, card.headline) for card in content.quick_news]
        + [("research_spotlight", card, card.title) for card in content.research_spotlight]
        + ([("paper_of_week", content.paper_of_week, content.paper_of_week.title)] if content.paper_of_week else [])
        + ([("deep_dive", content.deep_dive, content.deep_dive.title)] if content.deep_dive else [])
        + [("resources", card, card.name) for card in content.resources]
    )

    for section, card, label in cards:
        if not card.refs:
            add(section, "This card cites no source.", item=label)

    for card in content.quick_news:
        if len(card.summary) < 80:
            add("quick_news", "Summary is very short; readers get little beyond the headline.", "consider", card.headline)

    story_uses = Counter(card.story_id for _, card, _ in cards)

    for section, card, label in cards:
        if story_uses[card.story_id] > 1:
            add(section, "The same story appears in more than one section.", item=label)
            story_uses[card.story_id] = 0  # report each story once

    missing_images = [label for _, card, label in cards if not card.image_url]

    if len(missing_images) > len(cards) // 2:
        add(
            "images",
            f"{len(missing_images)} of {len(cards)} cards have no image and will show a placeholder.",
            "consider",
        )

    if content.stats.numbers_removed:
        add(
            "accuracy",
            f"{content.stats.numbers_removed} sentence(s) with numbers not found in the sources were removed; "
            "reread the affected cards for gaps.",
            "consider",
        )

    return notes


# ============================================================
# Model review
# ============================================================

REVIEW_SYSTEM = """You are the managing editor of AINow, a weekly AI newsletter
for developers and researchers. Review the draft below before it is sent.

Each card is followed by a SOURCE NOTE: our own summary of the story from
its sources. Use it to catch cards that contradict or overstate it.

Judge:
- Accuracy: claims that contradict or go beyond the source note.
- Specificity: vague lines that name no model, company, number or result.
- Redundancy: the same point or story repeated across cards.
- Tone: hype, marketing language, filler.
- Clarity: unexplained jargon, confusing sentences, weak headlines.

Score 1-10: 9-10 ready to send, 7-8 minor edits, 5-6 needs work, <5 rewrite.
List at most 8 concrete notes, most important first. Each note names the
section and the card it concerns and says exactly what to change, in at most
30 words. Do not praise. Do not invent problems; an empty list is fine.

Sections: headline, intro, quick_news, research_spotlight, paper_of_week,
deep_dive, trends, concept, resources, our_take.

Return ONLY JSON:
{"score": 7, "verdict": "one sentence overall assessment",
 "notes": [{"section": "quick_news", "item": "card headline or title",
            "severity": "fix" or "consider", "note": "what to change"}]}"""


def _source_notes(
    db: Session,
    content: IssueContent,
) -> dict[int, str]:
    ids = [story_id for story_id, *_ in content.story_ids()]

    if not ids:
        return {}

    stories = db.scalars(select(Story).where(Story.id.in_(ids))).all()

    return {
        story.id: truncate(story.summary or story.title, 300) or ""
        for story in stories
    }


def draft_text(
    content: IssueContent,
    source_notes: dict[int, str],
) -> str:
    """The draft as compact plain text for the reviewer."""

    lines = [
        f"HEADLINE: {content.headline}",
        f"INTRO: {content.intro}",
        "",
    ]

    def note(story_id: int) -> str:
        return f"   SOURCE NOTE: {source_notes[story_id]}" if story_id in source_notes else ""

    if content.quick_news:
        lines.append("QUICK NEWS")

        for card in content.quick_news:
            lines.append(f"- {card.headline}: {card.summary} Why it matters: {card.why_it_matters}")
            lines.append(note(card.story_id))

    research = list(content.research_spotlight)

    if research:
        lines.append("RESEARCH SPOTLIGHT")

    for card in research + ([content.paper_of_week] if content.paper_of_week else []):
        if card is content.paper_of_week:
            lines.append("PAPER OF THE WEEK")

        lines.append(
            f"- {card.title}: Problem: {card.problem} Idea: {card.core_idea} "
            f"Result: {card.key_result} Why it matters: {card.why_it_matters}"
        )
        lines.append(note(card.story_id))

    if content.deep_dive:
        dive = content.deep_dive
        lines.append(f"DEEP DIVE: {dive.title}")
        lines.append(dive.introduction)

        for section in dive.sections:
            lines.append(f"## {section.heading}: {section.body}")

        lines.append(note(dive.story_id))

    if content.trends:
        lines.append("TRENDS")
        lines += [f"- {trend.title}: {trend.explanation} Evidence: {trend.evidence}" for trend in content.trends]

    if content.concept:
        concept = content.concept
        lines.append(f"CONCEPT: {concept.concept}: {concept.simple_explanation} {concept.technical_explanation}")

    if content.resources:
        lines.append("RESOURCES")

        for card in content.resources:
            lines.append(f"- {card.name} ({card.resource_type}): {card.description} {card.why_useful}")
            lines.append(note(card.story_id))

    if content.our_take:
        lines.append(f"OUR TAKE: {content.our_take}")

    return "\n".join(line for line in lines if line is not None and line != "")


def parse_review(
    data: Any,
) -> tuple[int | None, str, list[ReviewNote]]:
    if not isinstance(data, dict):
        return None, "", []

    try:
        score = min(10, max(1, int(round(float(data.get("score"))))))
    except (TypeError, ValueError):
        score = None

    verdict = truncate(" ".join(str(data.get("verdict") or "").split()), 300) or ""

    notes: list[ReviewNote] = []

    for entry in data.get("notes") or []:
        if not isinstance(entry, dict):
            continue

        text = " ".join(str(entry.get("note") or "").split())

        if not text:
            continue

        section = str(entry.get("section") or "").strip().lower().replace(" ", "_")
        severity = str(entry.get("severity") or "").strip().lower()

        notes.append(
            ReviewNote(
                section=section if section in SECTIONS else "general",
                item=truncate(str(entry.get("item") or "").strip(), 160) or "",
                severity=severity if severity in ("fix", "consider") else "consider",
                note=truncate(text, 400) or "",
            )
        )

        if len(notes) == MAX_NOTES:
            break

    return score, verdict, notes


async def review_issue(
    db: Session,
    content: IssueContent,
) -> IssueReview:
    review = IssueReview(
        checks=structural_checks(content),
        reviewed_at=utcnow(),
    )

    try:
        data, model = await chat_json(
            [
                {"role": "system", "content": REVIEW_SYSTEM},
                {"role": "user", "content": draft_text(content, _source_notes(db, content))},
            ],
            tier="strong",
            max_tokens=1200,
            temperature=0.1,
        )

    except LLMUnavailable as error:
        print(f"[Review] No model available, structural checks only: {error}")
        review.verdict = "Model review unavailable; structural checks only."
        return review

    review.score, review.verdict, review.notes = parse_review(data)
    review.model = model

    return review
