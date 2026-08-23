import re

from app.schemas.research import ResearchCandidate


AI_TERMS = {
    "artificial intelligence",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural network",
    "neural networks",
    "large language model",
    "large language models",
    "llm",
    "llms",
    "generative ai",
    "foundation model",
    "foundation models",
    "transformer",
    "transformers",
    "natural language processing",
    "nlp",
    "computer vision",
    "multimodal",
    "multimodal model",
    "reinforcement learning",
    "robotics",
    "agentic ai",
    "ai agent",
    "ai agents",
    "diffusion model",
    "diffusion models",
    "retrieval augmented generation",
    "retrieval-augmented generation",
}


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return " ".join(text.split())


def query_term_overlap(
    title: str,
    query: str,
) -> float:
    title_words = set(
        normalize_text(title).split()
    )

    query_words = set(
        normalize_text(query).split()
    )

    if not query_words:
        return 0.0

    return len(
        query_words & title_words
    ) / len(query_words)


def has_ai_term_in_title(
    title: str,
) -> bool:
    normalized_title = normalize_text(title)

    return any(
        term in normalized_title
        for term in AI_TERMS
    )


def relevance_score(
    candidate: ResearchCandidate,
    query: str,
) -> float:

    title = normalize_text(
        candidate.title
    )

    query = normalize_text(
        query
    )

    score = 0.0

    # Strongest signal:
    # exact query phrase in title.
    if query in title:
        score += 0.70

    # Query word overlap.
    overlap = query_term_overlap(
        title,
        query,
    )

    score += overlap * 0.20

    # AI terminology in title.
    if has_ai_term_in_title(
        candidate.title
    ):
        score += 0.20

    return min(score, 1.0)


def is_relevant(
    candidate: ResearchCandidate,
    query: str,
) -> bool:

    title = normalize_text(
        candidate.title
    )

    query = normalize_text(
        query
    )

    # Exact phrase is the strongest signal.
    if query in title:
        return True

    overlap = query_term_overlap(
        title,
        query,
    )

    ai_in_title = has_ai_term_in_title(
        candidate.title
    )

    query_words = set(
        query.split()
    )

    # For a 3-word query such as
    # "large language models", require
    # at least 2 matching query terms.
    required_overlap = 0.66

    return (
        ai_in_title
        and overlap >= required_overlap
    )