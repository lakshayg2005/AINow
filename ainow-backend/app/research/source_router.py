from __future__ import annotations

from app.research.source_registry import (
    get_sources_by_categories,
)
from app.schemas.research import (
    ResearchSectionPlan,
    ResearchSource,
)


def route_sources(
    section: ResearchSectionPlan,
) -> list[ResearchSource]:
    return get_sources_by_categories(
        section.source_categories
    )


def get_effective_lookback(
    section: ResearchSectionPlan,
    source: ResearchSource,
) -> int:
    return min(
        section.lookback_days,
        source.lookback_days,
    )