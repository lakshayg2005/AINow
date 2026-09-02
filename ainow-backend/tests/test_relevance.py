from app.schemas.research import ResearchCandidate
from app.research.relevance import is_relevant


def make_candidate(
    title: str,
    content: str,
):
    return ResearchCandidate(
        title=title,
        url="https://example.com/test",
        source_name="Test Source",
        category="research",
        raw_content=content,
    )


def test_relevant_candidate_is_accepted():
    candidate = make_candidate(
        "New Large Language Model Architecture",
        (
            "Researchers introduce a new LLM architecture "
            "for efficient language modeling and reasoning."
        ),
    )

    assert is_relevant(candidate, "large language models") is True


def test_irrelevant_candidate_is_rejected():
    candidate = make_candidate(
        "New Battery Technology",
        (
            "Scientists developed a new battery chemistry "
            "for electric vehicles."
        ),
    )

    assert is_relevant(candidate, "large language models") is False