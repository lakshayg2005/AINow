from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.research.ranking import (
    rank_candidates,
)

from app.schemas.research import (
    RankedCandidate,
    ResearchCandidate,
)


def make_candidate(
    title: str,
    url: str,
    source_name: str,
    *,
    trust_tier: int = 1,
    content_length: int = 4000,
    cross_source_count: int = 1,
    published_at=None,
):
    return ResearchCandidate(
        title=title,
        url=url,
        source_name=source_name,
        category="research",
        trust_tier=trust_tier,
        cross_source_count=cross_source_count,
        supporting_sources=[],
        published_at=published_at,
        raw_content=(
            "benchmark evaluation research "
            "paper model performance results "
            + ("x" * content_length)
        ),
    )


def test_ranking_returns_ranked_candidates():
    now = datetime.now(
        timezone.utc
    )

    strong = make_candidate(
        "Strong Candidate",
        "https://example.com/strong",
        "Trusted Source",
        trust_tier=1,
        cross_source_count=3,
        published_at=now,
    )

    weak = make_candidate(
        "Weak Candidate",
        "https://example.com/weak",
        "Less Trusted Source",
        trust_tier=3,
        cross_source_count=1,
        published_at=(
            now - timedelta(days=10)
        ),
        content_length=100,
    )

    result = rank_candidates(
        [weak, strong]
    )

    assert all(
        isinstance(
            item,
            RankedCandidate,
        )
        for item in result
    )

    assert (
        result[0].candidate.title
        == "Strong Candidate"
    )

    assert result[0].score > 0


def test_cross_source_support_improves_ranking():
    now = datetime.now(
        timezone.utc
    )

    single_source = make_candidate(
        "Single Source Story",
        "https://example.com/one",
        "Source A",
        cross_source_count=1,
        published_at=now,
    )

    confirmed = make_candidate(
        "Confirmed Story",
        "https://example.com/two",
        "Source B",
        cross_source_count=3,
        published_at=now,
    )

    result = rank_candidates(
        [
            single_source,
            confirmed,
        ]
    )

    assert (
        result[0].candidate.title
        == "Confirmed Story"
    )


def test_source_diversity_limit_applies_to_top_twelve():
    candidates = []

    for index in range(6):
        candidates.append(
            make_candidate(
                f"Source A {index}",
                f"https://example.com/a-{index}",
                "Source A",
            )
        )

    for index in range(6):
        candidates.append(
            make_candidate(
                f"Source B {index}",
                f"https://example.com/b-{index}",
                "Source B",
            )
        )

    for index in range(6):
        candidates.append(
            make_candidate(
                f"Source C {index}",
                f"https://example.com/c-{index}",
                "Source C",
            )
        )

    result = rank_candidates(
        candidates
    )

    top_twelve = result[:12]

    source_counts = {}

    for ranked in top_twelve:
        source = (
            ranked.candidate.source_name
        )

        source_counts[source] = (
            source_counts.get(
                source,
                0,
            )
            + 1
        )

    assert all(
        count <= 4
        for count in source_counts.values()
    )


def test_ranking_order_is_deterministic():
    now = datetime.now(
        timezone.utc
    )

    first = make_candidate(
        "First",
        "https://example.com/first",
        "Source",
        published_at=now,
    )

    second = make_candidate(
        "Second",
        "https://example.com/second",
        "Source",
        published_at=(
            now - timedelta(days=2)
        ),
    )

    result = rank_candidates(
        [second, first]
    )

    assert [
        item.candidate.title
        for item in result
    ] == [
        "First",
        "Second",
    ]