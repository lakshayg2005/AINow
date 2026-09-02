from app.schemas.research import ResearchSource


SOURCE_REGISTRY = [

    # =====================================================
    # ACADEMIC
    # =====================================================

    ResearchSource(
        name="arXiv",
        category="research",
        trust_tier=1,
        lookback_days=14,
        access_mode="api",
        topics=[
            "research",
            "llm",
            "agents",
            "multimodal",
            "reasoning",
        ],
    ),

    ResearchSource(
        name="Crossref",
        category="research",
        trust_tier=1,
        lookback_days=30,
        access_mode="api",
        topics=[
            "research",
            "papers",
        ],
    ),

    ResearchSource(
        name="Semantic Scholar",
        category="research",
        trust_tier=1,
        lookback_days=30,
        access_mode="api",
        topics=[
            "research",
            "papers",
            "citations",
        ],
    ),

    # Keep registered, but disabled because
    # you explicitly chose not to fix it now.
    ResearchSource(
        name="OpenAlex",
        category="research",
        trust_tier=1,
        lookback_days=14,
        access_mode="api",
        topics=[
            "research",
            "artificial-intelligence",
        ],
        enabled=False,
    ),

    # =====================================================
    # COMPANIES
    # =====================================================

    ResearchSource(
        name="OpenAI",
        category="company",
        trust_tier=1,
        lookback_days=7,
        access_mode="web",
        topics=[
            "models",
            "research",
            "product",
            "safety",
        ],
    ),

    ResearchSource(
        name="Google DeepMind",
        category="company",
        trust_tier=1,
        lookback_days=7,
        access_mode="web",
        topics=[
            "models",
            "research",
            "agents",
            "science",
        ],
    ),

    ResearchSource(
        name="Anthropic",
        category="company",
        trust_tier=1,
        lookback_days=7,
        access_mode="web",
        topics=[
            "models",
            "research",
            "safety",
            "agents",
        ],
    ),

    ResearchSource(
        name="NVIDIA",
        category="company",
        trust_tier=1,
        lookback_days=7,
        access_mode="web",
        topics=[
            "gpu",
            "inference",
            "models",
            "infrastructure",
        ],
    ),

    # =====================================================
    # LEADERBOARDS
    # =====================================================

    ResearchSource(
        name="Hugging Face Leaderboard",
        category="leaderboard",
        trust_tier=1,
        lookback_days=7,
        access_mode="mcp",
        topics=[
            "llm",
            "benchmarks",
            "open-source",
        ],
    ),

    ResearchSource(
        name="LMSYS Chatbot Arena",
        category="leaderboard",
        trust_tier=1,
        lookback_days=7,
        access_mode="web",
        topics=[
            "llm",
            "benchmarks",
            "models",
        ],
    ),

    ResearchSource(
        name="Artificial Analysis",
        category="leaderboard",
        trust_tier=1,
        lookback_days=7,
        access_mode="web",
        topics=[
            "models",
            "benchmarks",
            "inference",
        ],
    ),

    ResearchSource(
        name="LLM Stats",
        category="leaderboard",
        trust_tier=2,
        lookback_days=7,
        access_mode="web",
        topics=[
            "llm",
            "models",
            "benchmarks",
        ],
    ),

    # =====================================================
    # OPEN SOURCE
    # =====================================================

    ResearchSource(
        name="GitHub",
        category="open-source",
        trust_tier=1,
        lookback_days=7,
        access_mode="mcp",
        topics=[
            "github",
            "open-source",
            "developer-tools",
            "agents",
        ],
    ),

    ResearchSource(
        name="Hugging Face",
        category="open-source",
        trust_tier=1,
        lookback_days=7,
        access_mode="mcp",
        topics=[
            "models",
            "datasets",
            "spaces",
            "open-source",
        ],
    ),

    # =====================================================
    # NEWS
    # =====================================================

    ResearchSource(
        name="TechCrunch AI",
        category="news",
        trust_tier=2,
        lookback_days=7,
        access_mode="web",
        topics=[
            "industry",
            "funding",
            "products",
            "models",
        ],
    ),

    ResearchSource(
        name="MIT Technology Review AI",
        category="news",
        trust_tier=2,
        lookback_days=14,
        access_mode="web",
        topics=[
            "research",
            "industry",
            "trends",
        ],
    ),

    ResearchSource(
        name="Artificial Intelligence News",
        category="news",
        trust_tier=2,
        lookback_days=7,
        access_mode="web",
        topics=[
            "news",
            "industry",
            "tools",
        ],
    ),

    # =====================================================
    # TECHNICAL
    # =====================================================

    ResearchSource(
        name="IEEE Spectrum AI",
        category="technical",
        trust_tier=1,
        lookback_days=14,
        access_mode="web",
        topics=[
            "engineering",
            "robotics",
            "research",
            "hardware",
        ],
    ),

    # =====================================================
    # TOOLS
    # =====================================================

    ResearchSource(
        name="FutureTools",
        category="tools",
        trust_tier=2,
        lookback_days=14,
        access_mode="web",
        topics=[
            "tools",
            "products",
        ],
    ),
]


def get_enabled_sources() -> list[ResearchSource]:
    return [
        source
        for source in SOURCE_REGISTRY
        if source.enabled
    ]


def get_sources_by_categories(
    categories: list[str],
) -> list[ResearchSource]:

    return [
        source
        for source in get_enabled_sources()
        if source.category in categories
    ]