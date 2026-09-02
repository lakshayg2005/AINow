from typing import TypedDict

from app.schemas.research import (
    RankedCandidate,
    ResearchCandidate,
    ResearchPlan,
    ResearchResult,
    EditorialSelection,
)

from app.schemas.newsletter import (
    NewsletterContent,
)


class ResearchState(
    TypedDict,
    total=False,
):
    topic: str

    plan: ResearchPlan

    candidates: list[
        ResearchCandidate
    ]

    freshness_results: list[
        ResearchResult
    ]

    fresh_candidates: list[
        ResearchCandidate
    ]

    ranked_candidates: list[
        RankedCandidate
    ]

    editorial_selection: EditorialSelection

    newsletter_content: NewsletterContent

    newsletter_issue_id: int | None

    errors: list[str]