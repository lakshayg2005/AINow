from app.schemas.research import (
    ResearchPlan,
    ResearchSectionPlan,
)


RESEARCH_TOPICS = {
    "llm": {
        "queries": [
            "large language models",
            "LLM",
            "reasoning models",
            "LLM agents",
            "multimodal language models",
            "long context models",
            "open source LLMs",
        ],
    },

    "ai_agents": {
        "queries": [
            "AI agents",
            "agentic AI",
            "LLM agents",
            "autonomous AI agents",
            "tool using language models",
        ],
    },

    "multimodal_ai": {
        "queries": [
            "multimodal AI",
            "multimodal language models",
            "vision language models",
            "multimodal reasoning",
        ],
    },

    "ai_coding": {
        "queries": [
            "AI coding agents",
            "AI software engineering",
            "code generation models",
            "coding language models",
        ],
    },

    "ai_safety": {
        "queries": [
            "AI safety",
            "AI alignment",
            "AI evaluation safety",
            "AI robustness",
        ],
    },
}


def build_research_plan(
    topic: str,
) -> ResearchPlan:

    config = RESEARCH_TOPICS.get(topic)

    if not config:
        raise ValueError(
            f"Unknown research topic: {topic}"
        )

    queries = config["queries"]

    sections = [

        ResearchSectionPlan(
            section="quick_news",
            source_categories=[
                "company",
                "news",
                "leaderboard",
            ],
            lookback_days=3,
            queries=queries,
            max_results_per_source=10,
        ),

        ResearchSectionPlan(
            section="research_spotlight",
            source_categories=[
                "research",
            ],
            lookback_days=14,
            queries=queries,
            max_results_per_source=15,
        ),

        ResearchSectionPlan(
            section="paper_of_week",
            source_categories=[
                "research",
            ],
            lookback_days=21,
            queries=queries,
            max_results_per_source=20,
        ),

        ResearchSectionPlan(
            section="deep_dive",
            source_categories=[
                "company",
                "news",
                "technical",
                "research",
            ],
            lookback_days=14,
            queries=queries,
            max_results_per_source=10,
        ),

        ResearchSectionPlan(
            section="ai_trends",
            source_categories=[
                "company",
                "news",
                "leaderboard",
                "technical",
            ],
            lookback_days=30,
            queries=queries,
            max_results_per_source=15,
        ),

        ResearchSectionPlan(
            section="ai_concept",
            source_categories=[
                "research",
                "technical",
            ],
            lookback_days=90,
            queries=queries,
            max_results_per_source=10,
        ),

        ResearchSectionPlan(
            section="ai_resources",
            source_categories=[
                "open-source",
                "tools",
                "company",
            ],
            lookback_days=7,
            queries=queries,
            max_results_per_source=10,
        ),
    ]

    return ResearchPlan(
        topic=topic,
        queries=queries,
        # Compatibility value for existing code.
        # Individual sections override this.
        lookback_days=14,
        sections=sections,
    )