"""
Structured newsletter content (format version 2).

Stored as JSON in newsletter_issues.raw_content. The web page
renders it interactively; the email is rendered from it too.
Every factual card carries `refs` into `sources`, its story id
(for the freshness memory) and an image when one exists.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    id: int
    title: str
    url: str
    source_name: str


class Engagement(BaseModel):
    hn_points: int | None = None
    hf_upvotes: int | None = None
    stars: int | None = None
    likes: int | None = None
    source_count: int = 1


class QuickNewsCard(BaseModel):
    story_id: int
    headline: str
    summary: str
    why_it_matters: str = ""
    category: str = "other"
    image_url: str | None = None
    is_update: bool = False
    engagement: Engagement = Field(default_factory=Engagement)
    refs: list[int] = Field(default_factory=list)


class ResearchCard(BaseModel):
    story_id: int
    title: str
    problem: str = ""
    core_idea: str = ""
    key_result: str = ""
    why_it_matters: str = ""
    authors: list[str] = Field(default_factory=list)
    paper_url: str | None = None
    image_url: str | None = None
    engagement: Engagement = Field(default_factory=Engagement)
    refs: list[int] = Field(default_factory=list)


class DeepDiveSection(BaseModel):
    heading: str
    body: str


class DeepDiveCard(BaseModel):
    story_id: int
    title: str
    introduction: str
    sections: list[DeepDiveSection] = Field(default_factory=list)
    image_url: str | None = None
    refs: list[int] = Field(default_factory=list)


class TrendCard(BaseModel):
    title: str
    explanation: str
    evidence: str = ""
    story_ids: list[int] = Field(default_factory=list)
    refs: list[int] = Field(default_factory=list)


class ConceptCard(BaseModel):
    concept: str
    simple_explanation: str
    technical_explanation: str
    example: str = ""
    related_story_id: int | None = None


class ResourceCard(BaseModel):
    story_id: int
    name: str
    resource_type: str
    description: str
    why_useful: str = ""
    url: str
    image_url: str | None = None
    engagement: Engagement = Field(default_factory=Engagement)
    refs: list[int] = Field(default_factory=list)


class IssueStats(BaseModel):
    items_scanned: int = 0
    stories_considered: int = 0
    sources_used: int = 0
    window_days: int = 7
    models: list[str] = Field(default_factory=list)
    numbers_removed: int = 0
    images_replaced: int = 0


class ReviewNote(BaseModel):
    section: str
    note: str
    # "fix": should change before publishing; "consider": optional.
    severity: str = "consider"
    item: str = ""


class IssueReview(BaseModel):
    """
    Editor-facing quality review of a draft. Shown in the admin
    newsroom only; never rendered on the site or in email.
    """

    # 1-10 from the reviewing model; None if no model answered.
    score: int | None = None
    verdict: str = ""
    notes: list[ReviewNote] = Field(default_factory=list)
    # Deterministic checks (missing sections, uncited cards...).
    checks: list[ReviewNote] = Field(default_factory=list)
    model: str = ""
    reviewed_at: datetime | None = None


class IssueContent(BaseModel):
    version: int = 2

    title: str
    headline: str = ""
    intro: str = ""
    issue_date: datetime

    quick_news: list[QuickNewsCard] = Field(default_factory=list)
    research_spotlight: list[ResearchCard] = Field(default_factory=list)
    paper_of_week: ResearchCard | None = None
    deep_dive: DeepDiveCard | None = None
    trends: list[TrendCard] = Field(default_factory=list)
    concept: ConceptCard | None = None
    resources: list[ResourceCard] = Field(default_factory=list)
    our_take: str = ""

    sources: list[SourceRef] = Field(default_factory=list)
    stats: IssueStats = Field(default_factory=IssueStats)
    review: IssueReview | None = None

    def story_ids(self) -> list[tuple[int, str, str, str]]:
        """(story_id, section, headline, summary) for every story used."""

        entries = [
            (card.story_id, "quick_news", card.headline, card.summary)
            for card in self.quick_news
        ]
        entries += [
            (card.story_id, "research_spotlight", card.title, card.core_idea)
            for card in self.research_spotlight
        ]

        if self.paper_of_week:
            paper = self.paper_of_week
            entries.append((paper.story_id, "paper_of_week", paper.title, paper.core_idea))

        if self.deep_dive:
            dive = self.deep_dive
            entries.append((dive.story_id, "deep_dive", dive.title, dive.introduction))

        entries += [
            (card.story_id, "resources", card.name, card.description)
            for card in self.resources
        ]

        return entries
