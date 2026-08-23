from sqlalchemy.orm import Session

from app.db.models import (
    NewsletterIssue,
    NewsletterSection,
)

from app.schemas.newsletter import NewsletterContent

from app.services.newsletter_renderer import (
    render_newsletter_html,
)


def save_generated_newsletter(
    db: Session,
    content: NewsletterContent,
    title: str,
) -> NewsletterIssue:

    # -----------------------------------------
    # 1. Create draft issue
    # -----------------------------------------

    newsletter = NewsletterIssue(
        title=title,
        raw_content=content.model_dump_json(
            indent=2
        ),
        status="draft",
    )

    db.add(newsletter)
    db.flush()

    # -----------------------------------------
    # 2. Create sections
    # -----------------------------------------

    display_order = 1

    if content.quick_news:

        db.add(
            NewsletterSection(
                newsletter_issue_id=newsletter.id,
                section_type="quick_news",
                title="Quick News",
                content=content.model_dump_json(
                    include={
                        "quick_news"
                    }
                ),
                display_order=display_order,
            )
        )

        display_order += 1

    if content.research_spotlight:

        db.add(
            NewsletterSection(
                newsletter_issue_id=newsletter.id,
                section_type="research_spotlight",
                title="Research Spotlight",
                content=content.model_dump_json(
                    include={
                        "research_spotlight"
                    }
                ),
                display_order=display_order,
            )
        )

        display_order += 1

    if content.paper_of_week:

        db.add(
            NewsletterSection(
                newsletter_issue_id=newsletter.id,
                section_type="paper_of_week",
                title="Paper of the Week",
                content=content.model_dump_json(
                    include={
                        "paper_of_week"
                    }
                ),
                display_order=display_order,
            )
        )

        display_order += 1

    if content.deep_dive:

        db.add(
            NewsletterSection(
                newsletter_issue_id=newsletter.id,
                section_type="deep_dive",
                title="AI Deep Dive",
                content=content.model_dump_json(
                    include={
                        "deep_dive"
                    }
                ),
                display_order=display_order,
            )
        )

        display_order += 1

    if content.trends:

        db.add(
            NewsletterSection(
                newsletter_issue_id=newsletter.id,
                section_type="ai_trends",
                title="AI Trends",
                content=content.model_dump_json(
                    include={
                        "trends"
                    }
                ),
                display_order=display_order,
            )
        )

        display_order += 1

    if content.concept:

        db.add(
            NewsletterSection(
                newsletter_issue_id=newsletter.id,
                section_type="ai_concept",
                title="AI Concept",
                content=content.model_dump_json(
                    include={
                        "concept"
                    }
                ),
                display_order=display_order,
            )
        )

        display_order += 1

    if content.resources:

        db.add(
            NewsletterSection(
                newsletter_issue_id=newsletter.id,
                section_type="resources",
                title="AI Resources",
                content=content.model_dump_json(
                    include={
                        "resources"
                    }
                ),
                display_order=display_order,
            )
        )

        display_order += 1

    if content.our_take:

        db.add(
            NewsletterSection(
                newsletter_issue_id=newsletter.id,
                section_type="our_take",
                title="Our Take",
                content=content.our_take,
                display_order=display_order,
            )
        )

        display_order += 1

    if content.source_urls:

        db.add(
            NewsletterSection(
                newsletter_issue_id=newsletter.id,
                section_type="sources",
                title="Sources",
                content=content.model_dump_json(
                    include={
                        "source_urls"
                    }
                ),
                display_order=display_order,
            )
        )

    # -----------------------------------------
    # 3. Generate final HTML
    # -----------------------------------------

    newsletter.html_content = (
        render_newsletter_html(
            content,
            title=title,
        )
    )

    db.commit()
    db.refresh(newsletter)

    return newsletter 