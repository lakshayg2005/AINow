from app.schemas.research import ResearchCandidate
from app.research.deduplication import (
    merge_candidates,
    normalize_title,
)


def make_candidate(
    title: str,
    url: str,
    source_name: str = "Test Source",
    content: str = (
        "Researchers present a new artificial intelligence "
        "method for improving machine learning systems."
    ),
):
    return ResearchCandidate(
        title=title,
        url=url,
        source_name=source_name,
        category="research",
        raw_content=content,
    )


def test_normalize_title():
    assert normalize_title(
        "New AI: Research! Results?"
    ) == "new ai research results"


def test_duplicate_urls_are_merged():
    candidates = [
        make_candidate(
            "New AI Research",
            "https://example.com/article",
            "Source A",
        ),
        make_candidate(
            "New AI Research",
            "https://example.com/article/",
            "Source B",
        ),
    ]

    result = merge_candidates(candidates)

    assert len(result) == 1
    assert result[0].cross_source_count == 2
    assert set(result[0].supporting_sources) == {
        "Source A",
        "Source B",
    }


def test_duplicate_titles_are_merged():
    candidates = [
        make_candidate(
            "New AI Research",
            "https://example.com/one",
            "Source A",
        ),
        make_candidate(
            "New AI: Research!",
            "https://example.com/two",
            "Source B",
        ),
    ]

    result = merge_candidates(candidates)

    assert len(result) == 1
    assert result[0].cross_source_count == 2


def test_different_candidates_are_preserved():
    candidates = [
        make_candidate(
            "New Language Model",
            "https://example.com/one",
            "Source A",
            "A language model improves reasoning performance.",
        ),
        make_candidate(
            "New Computer Vision System",
            "https://example.com/two",
            "Source B",
            "A computer vision system detects objects in images.",
        ),
    ]

    result = merge_candidates(candidates)

    assert len(result) == 2