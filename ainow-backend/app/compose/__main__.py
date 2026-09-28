"""
Compose this week's issue as a draft.

    python -m app.compose                      # compose + save draft
    python -m app.compose --refresh            # re-cluster/triage first
    python -m app.compose --dry-run --out preview.html

The draft appears in the admin newsroom (/admin), where it is
previewed, test-sent and published; publishing records its
stories in the freshness memory.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.compose.composer import compose_issue
from app.compose.persist import save_issue_draft
from app.core.config import settings
from app.db.database import SessionLocal, engine
from app.db.schema_patches import ensure_schema
from app.services.issue_email import render_issue_email
from app.stories.service import update_stories


def _print_summary(content) -> None:
    print(f"\n{content.title}")
    print(f"Headline: {content.headline}")
    print(f"Intro:    {content.intro}\n")

    for card in content.quick_news:
        print(f"  [news]     {card.headline}  refs={card.refs}")

    if content.paper_of_week:
        print(f"  [paper*]   {content.paper_of_week.title}")

    for card in content.research_spotlight:
        print(f"  [research] {card.title}")

    if content.deep_dive:
        print(f"  [deep]     {content.deep_dive.title} ({len(content.deep_dive.sections)} sections)")

    for card in content.trends:
        print(f"  [trend]    {card.title} stories={card.story_ids}")

    if content.concept:
        print(f"  [concept]  {content.concept.concept}")

    for card in content.resources:
        print(f"  [tool]     {card.name} ({card.resource_type})")

    images = sum(
        1
        for card in [*content.quick_news, *content.research_spotlight, *content.resources]
        if card.image_url
    )

    print(
        f"\n{len(content.sources)} sources cited, {images} card images, "
        f"{content.stats.numbers_removed} unsupported sentences removed, "
        f"models: {', '.join(content.stats.models) or 'none (extractive fallback)'}"
    )

    review = content.review

    if review:
        score = f"{review.score}/10" if review.score is not None else "checks only"
        fixes = sum(note.severity == "fix" for note in [*review.notes, *review.checks])
        print(f"Review: {score}, {fixes} to fix. {review.verdict}")

        for note in [*review.notes, *review.checks]:
            print(f"  [{note.severity}] {note.section}: {note.note}")


async def _main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.compose")
    parser.add_argument("--days", type=int, default=7, help="Story window.")
    parser.add_argument("--refresh", action="store_true", help="Cluster + triage before composing.")
    parser.add_argument("--dry-run", action="store_true", help="Don't save a draft.")
    parser.add_argument("--out", type=Path, help="Write the email HTML here.")
    parser.add_argument("--json", type=Path, help="Write the content JSON here.")
    args = parser.parse_args()

    ensure_schema(engine)
    db = SessionLocal()

    try:
        if args.refresh:
            await update_stories(db)

        content = await compose_issue(db, window_days=args.days)
        _print_summary(content)

        html = None

        if not args.dry_run:
            issue = save_issue_draft(db, content)
            html = issue.html_content
            print(f"\nDraft saved: newsletter_issues.id={issue.id}")

        if args.out:
            html = html or render_issue_email(content, web_url=f"{settings.frontend_url.rstrip('/')}/newsletters")
            args.out.write_text(html, encoding="utf-8")
            print(f"Email HTML written to {args.out}")

        if args.json:
            args.json.write_text(content.model_dump_json(indent=2), encoding="utf-8")
            print(f"Content JSON written to {args.json}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(_main())
