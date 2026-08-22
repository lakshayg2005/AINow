from datetime import datetime

from pydantic import BaseModel


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