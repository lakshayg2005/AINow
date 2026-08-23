from datetime import datetime, timezone

from app.research.relevance import relevance_score
from app.schemas.research import (
    RankedCandidate,
    ResearchCandidate,
)


def freshness_score(
    published_at: datetime | None,
    lookback_days: int,
) -> float:

    if published_at is None:
        return 0.4

    if published_at.tzinfo is None:
        published_at = published_at.replace(
            tzinfo=timezone.utc
        )

    age_days = (
        datetime.now(timezone.utc)
        - published_at
    ).total_seconds() / 86400

    score = (
        1.0
        - age_days / max(
            lookback_days,
            1,
        )
    )

    return max(
        0.0,
        min(1.0, score),
    )


def trust_score(
    trust_tier: int,
) -> float:

    return {
        1: 1.0,
        2: 0.7,
        3: 0.4,
    }.get(
        trust_tier,
        0.4,
    )


def content_score(
    candidate: ResearchCandidate,
) -> float:

    text_length = len(
        candidate.raw_content.strip()
    )

    if text_length >= 1000:
        return 1.0

    if text_length >= 500:
        return 0.8

    if text_length >= 200:
        return 0.6

    if text_length >= 80:
        return 0.4

    return 0.2


def impact_score(
    candidate: ResearchCandidate,
) -> float:

    citations = candidate.citation_count

    if citations >= 100:
        return 1.0

    if citations >= 50:
        return 0.9

    if citations >= 20:
        return 0.75

    if citations >= 10:
        return 0.6

    if citations >= 5:
        return 0.45

    if citations >= 1:
        return 0.3

    return 0.2


def novelty_score(
    candidate: ResearchCandidate,
) -> float:

    # Temporary neutral score.
    #
    # We will replace this with actual
    # semantic novelty using the
    # research_papers pgvector corpus.

    return 0.5


def cross_source_score(
    candidate: ResearchCandidate,
) -> float:

    count = candidate.cross_source_count

    if count >= 3:
        return 1.0

    if count == 2:
        return 0.75

    return 0.4


def rank_candidates(
    candidates: list[ResearchCandidate],
    queries: list[str],
    lookback_days: int = 7,
) -> list[RankedCandidate]:

    ranked: list[RankedCandidate] = []

    for candidate in candidates:

        # -----------------------------------------
        # Relevance
        # -----------------------------------------

        relevance = max(
            relevance_score(
                candidate,
                query,
            )
            for query in queries
        )

        # -----------------------------------------
        # Freshness
        # -----------------------------------------

        freshness = freshness_score(
            candidate.published_at,
            lookback_days,
        )

        # -----------------------------------------
        # Trust
        # -----------------------------------------

        trust = trust_score(
            candidate.trust_tier
        )

        # -----------------------------------------
        # Content quality
        # -----------------------------------------

        content = content_score(
            candidate
        )

        # -----------------------------------------
        # Research impact
        # -----------------------------------------

        impact = impact_score(
            candidate
        )

        # -----------------------------------------
        # Cross-source confirmation
        # -----------------------------------------

        confirmation = cross_source_score(
            candidate
        )

        # -----------------------------------------
        # Novelty
        # -----------------------------------------

        novelty = novelty_score(
            candidate
        )

        # -----------------------------------------
        # Final score
        # -----------------------------------------

        score = (
            relevance * 0.25
            + freshness * 0.20
            + trust * 0.20
            + impact * 0.15
            + confirmation * 0.10
            + content * 0.05
            + novelty * 0.05
        )

        reasons: list[str] = []

        if relevance >= 0.7:
            reasons.append(
                "high-query-relevance"
            )

        if freshness >= 0.7:
            reasons.append(
                "recent"
            )

        if trust >= 0.9:
            reasons.append(
                "high-trust-source"
            )

        if impact >= 0.6:
            reasons.append(
                "research-impact"
            )

        if confirmation >= 0.75:
            reasons.append(
                "cross-source-confirmed"
            )

        if content >= 0.8:
            reasons.append(
                "content-rich"
            )

        ranked.append(
            RankedCandidate(
                candidate=candidate,
                score=round(
                    score,
                    4,
                ),
                reasons=reasons,
            )
        )

    ranked.sort(
        key=lambda item: item.score,
        reverse=True,
    )

    return ranked