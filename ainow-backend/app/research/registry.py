from app.schemas.research import ResearchSource


SOURCES = [
    ResearchSource(
        name="OpenAI News",
        category="company",
        trust_tier=1,
        lookback_days=7,
        topics=["models", "research", "product", "safety"],
    ),
    ResearchSource(
        name="Google DeepMind",
        category="company",
        trust_tier=1,
        lookback_days=7,
        topics=["models", "research", "science", "agents"],
    ),
    ResearchSource(
        name="Anthropic News",
        category="company",
        trust_tier=1,
        lookback_days=7,
        topics=["models", "research", "safety", "agents"],
    ),
    ResearchSource(
        name="NVIDIA AI",
        category="company",
        trust_tier=1,
        lookback_days=7,
        topics=["gpu", "inference", "models", "infrastructure"],
    ),
    ResearchSource(
        name="arXiv",
        category="research",
        trust_tier=1,
        lookback_days=14,
        topics=["research", "machine-learning", "llm"],
    ),
    ResearchSource(
        name="IEEE Xplore",
        category="research",
        trust_tier=1,
        lookback_days=30,
        topics=["machine-learning", "computer-vision", "robotics"],
    ),
    ResearchSource(
        name="OpenAlex",
        category="research",
        trust_tier=1,
        lookback_days=14,
        topics=["research", "artificial-intelligence"],
    ),
    ResearchSource(
        name="Crossref",
        category="research",
        trust_tier=1,
        lookback_days=30,
        topics=["research", "papers"],
    ),
    ResearchSource(
        name="Semantic Scholar",
        category="research",
        trust_tier=1,
        lookback_days=14,
        topics=["research", "papers", "citations"],
    ),
    ResearchSource(
        name="Hugging Face Leaderboard",
        category="leaderboard",
        trust_tier=1,
        lookback_days=7,
        topics=["llm", "benchmarks", "open-source"],
    ),
    ResearchSource(
        name="LMSYS Chatbot Arena",
        category="leaderboard",
        trust_tier=1,
        lookback_days=7,
        topics=["llm", "benchmarks", "models"],
    ),
    ResearchSource(
        name="Artificial Analysis",
        category="leaderboard",
        trust_tier=1,
        lookback_days=7,
        topics=["models", "benchmarks", "inference"],
    ),
    ResearchSource(
        name="LLM Stats",
        category="leaderboard",
        trust_tier=2,
        lookback_days=7,
        topics=["llm", "models", "benchmarks"],
    ),
    ResearchSource(
        name="TechCrunch AI",
        category="news",
        trust_tier=2,
        lookback_days=7,
        topics=["industry", "funding", "products", "models"],
    ),
    ResearchSource(
        name="MIT Technology Review AI",
        category="news",
        trust_tier=2,
        lookback_days=14,
        topics=["research", "industry", "trends"],
    ),
    ResearchSource(
        name="IEEE Spectrum AI",
        category="technical",
        trust_tier=1,
        lookback_days=14,
        topics=["engineering", "robotics", "research"],
    ),
    ResearchSource(
        name="Artificial Intelligence News",
        category="news",
        trust_tier=2,
        lookback_days=7,
        topics=["news", "industry", "tools"],
    ),
    ResearchSource(
        name="FutureTools",
        category="tools",
        trust_tier=2,
        lookback_days=14,
        topics=["tools", "products"],
    ),
    ResearchSource(
        name="GitHub Trending",
        category="open-source",
        trust_tier=2,
        lookback_days=7,
        topics=["github", "open-source", "developer-tools"],
    ),
]


def get_enabled_sources() -> list[ResearchSource]:
    return [
        source
        for source in SOURCES
        if source.enabled
    ]