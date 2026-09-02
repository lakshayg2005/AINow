from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from app.schemas.research import (
    RankedCandidate,
    ResearchCandidate,
)


# ============================================================
# Scoring weights
# ============================================================

TRUST_WEIGHT = 20.0
RECENCY_WEIGHT = 30.0
CONTENT_WEIGHT = 25.0
SOURCE_DIVERSITY_WEIGHT = 10.0
EVIDENCE_WEIGHT = 15.0


# ============================================================
# Score helpers
# ============================================================

def _recency_score(
    published_at: datetime | None,
) -> float:
    if published_at is None:
        return 0.0

    now = datetime.now(timezone.utc)

    timestamp = published_at

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(
            tzinfo=timezone.utc
        )

    age_hours = max(
        0.0,
        (
            now - timestamp
        ).total_seconds() / 3600.0,
    )

    return 100.0 * (
        2.718281828459045
        ** (-age_hours / 24.0)
    )


def _trust_score(
    candidate: ResearchCandidate,
) -> float:
    tier = candidate.trust_tier

    if tier <= 1:
        return 100.0

    if tier == 2:
        return 75.0

    return 50.0


def _content_score(
    candidate: ResearchCandidate,
) -> float:
    text = candidate.raw_content or ""
    length = len(text)

    if length < 300:
        return 10.0

    if length < 1000:
        return 40.0

    if length < 3000:
        return 70.0

    if length < 8000:
        return 90.0

    return 100.0


def _source_diversity_score(
    candidate: ResearchCandidate,
) -> float:
    """
    Cross-source confirmation score.

    1 source  -> 0
    2 sources -> 50
    3+ sources -> 100
    """

    count = max(
        1,
        candidate.cross_source_count,
    )

    if count == 1:
        return 0.0

    if count == 2:
        return 50.0

    return 100.0


def _evidence_score(
    candidate: ResearchCandidate,
) -> float:
    text = (
        candidate.raw_content or ""
    ).lower()

    score = 0.0

    indicators = (
        ("benchmark", 15.0),
        ("evaluation", 15.0),
        ("research", 10.0),
        ("paper", 10.0),
        ("dataset", 10.0),
        ("model", 8.0),
        ("release", 8.0),
        ("results", 8.0),
        ("performance", 8.0),
        ("github", 5.0),
        ("source", 3.0),
    )

    for keyword, weight in indicators:
        if keyword in text:
            score += weight

    return min(
        100.0,
        score,
    )


def _base_score(
    candidate: ResearchCandidate,
) -> float:
    total_weight = (
        TRUST_WEIGHT
        + RECENCY_WEIGHT
        + CONTENT_WEIGHT
        + SOURCE_DIVERSITY_WEIGHT
        + EVIDENCE_WEIGHT
    )

    weighted_score = (
        (
            _trust_score(candidate)
            * TRUST_WEIGHT
        )
        + (
            _recency_score(
                candidate.published_at
            )
            * RECENCY_WEIGHT
        )
        + (
            _content_score(candidate)
            * CONTENT_WEIGHT
        )
        + (
            _source_diversity_score(candidate)
            * SOURCE_DIVERSITY_WEIGHT
        )
        + (
            _evidence_score(candidate)
            * EVIDENCE_WEIGHT
        )
    )

    return weighted_score / total_weight


# ============================================================
# Diversity-aware ranking
# ============================================================

def rank_candidates(
    candidates: Iterable[ResearchCandidate],
) -> list[RankedCandidate]:
    """
    Rank candidates and return RankedCandidate objects.

    Ranking position is represented by list order.
    RankedCandidate does not require a separate rank field.
    """

    candidate_list = list(candidates)

    if not candidate_list:
        return []

    scored = [
        (
            _base_score(candidate),
            index,
            candidate,
        )
        for index, candidate
        in enumerate(candidate_list)
    ]

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1],
        )
    )

    ranked: list[RankedCandidate] = []

    source_counts: dict[str, int] = {}

    deferred: list[
        tuple[
            float,
            int,
            ResearchCandidate,
        ]
    ] = []

    # --------------------------------------------------------
    # First page: diversity-aware selection
    # --------------------------------------------------------

    for score, index, candidate in scored:
        source = candidate.source_name

        count = source_counts.get(
            source,
            0,
        )

        if (
            count >= 4
            and len(ranked) < 12
        ):
            deferred.append(
                (
                    score,
                    index,
                    candidate,
                )
            )
            continue

        source_counts[source] = (
            count + 1
        )

        ranked.append(
            RankedCandidate(
                candidate=candidate,
                score=round(
                    score,
                    4,
                ),
                reasons=[],
            )
        )

    # --------------------------------------------------------
    # Append deferred candidates
    # --------------------------------------------------------

    for score, _, candidate in deferred:
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                score=round(
                    score,
                    4,
                ),
                reasons=[],
            )
        )

    return ranked