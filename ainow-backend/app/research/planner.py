from app.schemas.research import ResearchPlan


RESEARCH_TOPICS = {
    "llm": {
        "lookback_days": 14,
        "queries": [
            "large language models",
            "LLM",
            "reasoning language models",
            "foundation language models",
            "open source language models",
            "long context language models",
        ],
    },

    "ai_agents": {
        "lookback_days": 14,
        "queries": [
            "AI agents",
            "agentic AI",
            "LLM agents",
            "autonomous AI agents",
            "tool-using language models",
        ],
    },

    "multimodal_ai": {
        "lookback_days": 14,
        "queries": [
            "multimodal AI",
            "multimodal language models",
            "vision language models",
            "multimodal reasoning",
        ],
    },

    "ai_research": {
        "lookback_days": 30,
        "queries": [
            "artificial intelligence research",
            "machine learning research",
            "deep learning research",
            "AI model evaluation",
            "AI training methods",
            "AI inference research",
        ],
    },

    "ai_coding": {
        "lookback_days": 14,
        "queries": [
            "AI coding agents",
            "AI software engineering",
            "code generation models",
            "coding language models",
        ],
    },

    "ai_safety": {
        "lookback_days": 30,
        "queries": [
            "AI safety",
            "AI alignment",
            "AI evaluation safety",
            "AI robustness",
        ],
    },

    "ai_hardware": {
        "lookback_days": 14,
        "queries": [
            "AI accelerators",
            "AI chips",
            "GPU artificial intelligence",
            "AI inference hardware",
        ],
    },

    "robotics": {
        "lookback_days": 14,
        "queries": [
            "AI robotics",
            "robot learning",
            "vision language action models",
            "robot foundation models",
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

    return ResearchPlan(
        topic=topic,
        queries=config["queries"],
        lookback_days=config["lookback_days"],
    )