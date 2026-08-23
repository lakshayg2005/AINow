from datetime import datetime

from pydantic import BaseModel,Field


class NewsletterCreateRequest(BaseModel):
    title: str


class NewsletterSectionCreateRequest(BaseModel):
    section_type: str
    title: str
    content: str
    display_order: int


class NewsletterCreateResponse(BaseModel):
    id: int
    title: str
    status: str
    created_at: datetime


class NewsletterSectionResponse(BaseModel):
    id: int
    newsletter_issue_id: int
    section_type: str
    title: str
    content: str
    display_order: int


class NewsletterSummaryResponse(BaseModel):
    id: int
    title: str
    status: str
    created_at: datetime
    published_at: datetime | None


class NewsletterDetailResponse(BaseModel):
    id: int
    title: str
    status: str
    created_at: datetime
    published_at: datetime | None
    html_content: str

class QuickNewsItem(BaseModel):
    headline: str
    summary: str
    why_it_matters: str
    source_urls: list[str] = Field(
        default_factory=list
    )


class ResearchSpotlightItem(BaseModel):
    title: str
    problem: str
    core_idea: str
    key_result: str
    why_it_matters: str
    source_urls: list[str] = Field(
        default_factory=list
    )


class DeepDive(BaseModel):
    title: str
    introduction: str
    background: str
    technical_explanation: str
    impact: str
    what_to_watch: str
    source_urls: list[str] = Field(
        default_factory=list
    )


class TrendItem(BaseModel):
    title: str
    explanation: str
    evidence: str
    source_urls: list[str] = Field(
        default_factory=list
    )


class AIConcept(BaseModel):
    concept: str
    simple_explanation: str
    technical_explanation: str
    example: str


class AIResource(BaseModel):
    name: str
    resource_type: str
    description: str
    why_useful: str
    url: str


class NewsletterContent(BaseModel):
    quick_news: list[QuickNewsItem] = Field(
        default_factory=list
    )

    research_spotlight: list[ResearchSpotlightItem] = Field(
        default_factory=list
    )

    paper_of_week: ResearchSpotlightItem | None = None

    deep_dive: DeepDive | None = None

    trends: list[TrendItem] = Field(
        default_factory=list
    )

    concept: AIConcept | None = None

    resources: list[AIResource] = Field(
        default_factory=list
    )

    our_take: str = ""

    source_urls: list[str] = Field(
        default_factory=list
    )