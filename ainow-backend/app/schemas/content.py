from datetime import datetime

from pydantic import BaseModel


# -------------------------
# AI CONCEPTS
# -------------------------

class AIConceptCreateRequest(BaseModel):
    name: str
    slug: str
    description: str | None = None


class AIConceptResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None
    created_at: datetime


# -------------------------
# RESEARCH PAPERS
# -------------------------

class ResearchPaperCreateRequest(BaseModel):
    title: str
    authors: str | None = None
    url: str
    abstract: str | None = None
    published_at: datetime | None = None


class ResearchPaperResponse(BaseModel):
    id: int
    title: str
    authors: str | None
    url: str
    abstract: str | None
    published_at: datetime | None
    created_at: datetime


# -------------------------
# AI RESOURCES
# -------------------------

class AIResourceCreateRequest(BaseModel):
    name: str
    resource_type: str
    url: str
    description: str | None = None


class AIResourceResponse(BaseModel):
    id: int
    name: str
    resource_type: str
    url: str
    description: str | None
    created_at: datetime


# -------------------------
# SOURCES
# -------------------------

class SourceCreateRequest(BaseModel):
    url: str
    source_name: str
    title: str
    raw_content: str
    published_at: datetime | None = None


class SourceResponse(BaseModel):
    id: int
    url: str
    source_name: str
    title: str
    raw_content: str | None
    published_at: datetime | None
    retrieved_at: datetime