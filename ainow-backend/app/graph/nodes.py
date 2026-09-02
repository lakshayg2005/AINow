from app.db.database import SessionLocal
from app.research.orchestrator import ResearchOrchestrator
from app.research.planner import build_research_plan
from app.research.ranking import rank_candidates

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from langchain_core.output_parsers import (
    PydanticOutputParser,
)

from app.core.llm import get_editor_llm

from app.schemas.research import (
    EditorialSelection,
)

from app.schemas.newsletter import (
    NewsletterContent,
)
from app.services.newsletter_pipeline import (
    save_generated_newsletter,
)
from app.core.llm import (
    invoke_editor_llm,
)


# =========================================================
# RESEARCH PLANNER
# =========================================================

def plan_node(
    state,
):
    plan = build_research_plan(
        state["topic"]
    )

    print(
        f"[Research] Topic: {plan.topic}"
    )

    print(
        f"[Research] Queries: "
        f"{len(plan.queries)}"
    )

    return {
        "plan": plan
    }


# =========================================================
# RESEARCH COLLECTION
# =========================================================

async def collect_node(
    state,
):
    plan = state["plan"]

    orchestrator = ResearchOrchestrator()

    candidates = await orchestrator.research(
        plan=plan,
    )

    return {
        "candidates": candidates,
    }


# =========================================================
# EXACT URL DEDUPLICATION
# =========================================================

def deduplicate_candidates(
    candidates,
):
    unique = {}

    for candidate in candidates:

        key = (
            candidate.url
            .strip()
            .lower()
            .rstrip("/")
        )

        if key not in unique:
            unique[key] = candidate

    return list(
        unique.values()
    )


# =========================================================
# FRESHNESS / DUPLICATE CHECK
# =========================================================

def freshness_node(
    state,
):
    candidates = state.get(
        "candidates",
        [],
    )

    candidates = deduplicate_candidates(
        candidates
    )

    db = SessionLocal()

    try:

        from app.services.research import (
            check_paper_freshness,
            check_source_freshness,
        )

        results = []

        for candidate in candidates:

            if candidate.category == "research":

                result = check_paper_freshness(
                    candidate,
                    db,
                )

            else:

                result = check_source_freshness(
                    candidate,
                    db,
                )

            results.append(result)

        fresh = [
            result.candidate
            for result in results
            if result.is_fresh
        ]

        return {
            "freshness_results": results,
            "fresh_candidates": fresh,
        }

    finally:
        db.close()


# =========================================================
# DETERMINISTIC RANKING
# =========================================================

def ranking_node(
    state,
):
    candidates = state.get(
        "fresh_candidates",
        [],
    )

    candidates = deduplicate_candidates(
        candidates
    )

    plan = state["plan"]

    ranked = rank_candidates(
        candidates=candidates,
        queries=plan.queries,
        lookback_days=plan.lookback_days,
    )

    return {
        "ranked_candidates": ranked
    }


# =========================================================
# EDITORIAL SELECTION
# =========================================================

async def editorial_selection_node(
    state,
):
    ranked_candidates = state.get(
        "ranked_candidates",
        [],
    )

    # Only expose the strongest candidates
    # to the LLM.
    top_candidates = ranked_candidates[:20]

    if not top_candidates:
        return {
            "editorial_selection":
                EditorialSelection()
        }

    parser = PydanticOutputParser(
        pydantic_object=EditorialSelection
    )

    candidate_blocks = []

    for index, ranked in enumerate(
        top_candidates,
        start=1,
    ):
        candidate = ranked.candidate

        candidate_blocks.append(
            f"""
CANDIDATE {index}

Title:
{candidate.title}

Source:
{candidate.source_name}

Published:
{candidate.published_at}

Authors:
{", ".join(candidate.authors)}

Supporting Sources:
{", ".join(candidate.supporting_sources)}

Cross-source confirmations:
{candidate.cross_source_count}

Citation count:
{candidate.citation_count}

Research score:
{ranked.score}

Content:
{candidate.raw_content[:2500]}
""".strip()
        )

    candidates_text = "\n\n---\n\n".join(
        candidate_blocks
    )

    system_prompt = """
You are the senior research editor for AINow,
an AI newsletter.

Your job is to select the most valuable
research candidates.

You are NOT writing the newsletter yet.

Prioritize:

1. Importance to AI.
2. Scientific or technical significance.
3. Novelty.
4. Relevance to the requested topic.
5. Value to developers and researchers.
6. Strong evidence.
7. Cross-source confirmation.
8. Recency.

Avoid:

- superficial AI mentions
- narrow applications with little general AI value
- low-value incremental work
- duplicates
- weak research

Prefer diversity across:

- LLMs
- agents
- evaluation
- reasoning
- multimodal AI
- memory/context
- safety
- inference/systems

Select only from the numbered candidates.

Never invent candidate numbers.

Return ONLY valid JSON.
"""

    user_prompt = f"""
/no_think

Research topic:
{state["plan"].topic}

Available research candidates:

{candidates_text}

Choose:

- 5 to 8 candidates for further editorial consideration
- 2 to 4 Research Spotlight candidates
- exactly 1 Paper of the Week when justified
- exactly 1 Deep Dive candidate when justified
- 1 to 3 Trend candidates

{parser.get_format_instructions()}
"""


    response = await invoke_editor_llm(
        [
            SystemMessage(
                content=system_prompt
            ),
            HumanMessage(
                content=user_prompt
            ),
        ]
    )

    print(
        "\n[LLM] Raw editorial response:"
    )

    print(
        repr(response.content)
    )

    try:

        selection = parser.parse(
            response.content
        )

    except Exception as error:

        raise RuntimeError(
            "Failed to parse editorial "
            f"selection: {error}\n"
            f"Model output:\n"
            f"{response.content}"
        ) from error

    # =====================================================
    # VALIDATE LLM INDICES
    # =====================================================

    candidate_count = len(
        top_candidates
    )

    valid_range = set(
        range(
            1,
            candidate_count + 1,
        )
    )

    selection.selected_candidate_indices = [
        index
        for index in selection.selected_candidate_indices
        if index in valid_range
    ]

    selection.research_spotlight_indices = [
        index
        for index in selection.research_spotlight_indices
        if index in valid_range
    ]

    selection.trend_indices = [
        index
        for index in selection.trend_indices
        if index in valid_range
    ]

    if (
        selection.paper_of_week_index
        not in valid_range
    ):
        selection.paper_of_week_index = None

    if (
        selection.deep_dive_index
        not in valid_range
    ):
        selection.deep_dive_index = None

    return {
        "editorial_selection":
            selection
    }


# =========================================================
# NEWSLETTER CONTENT GENERATION
# =========================================================

async def content_generation_node(
    state,
):
    selection = state[
        "editorial_selection"
    ]

    ranked = state.get(
        "ranked_candidates",
        [],
    )

    if not ranked:
        return {
            "newsletter_content":
                NewsletterContent()
        }

    # ==================================================
    # BUILD THE EDITORIAL SET
    # ==================================================

    selected_indices = (
        selection.selected_candidate_indices
    )

    selected_candidates = []

    for index in selected_indices:

        if 1 <= index <= len(ranked):

            selected_candidates.append(
                {
                    "index": index,
                    "candidate": ranked[
                        index - 1
                    ].candidate,
                }
            )

    if not selected_candidates:
        return {
            "newsletter_content":
                NewsletterContent()
        }

    # ==================================================
    # BUILD ROLE INFORMATION
    # ==================================================

    spotlight_indices = set(
        selection.research_spotlight_indices
    )

    trend_indices = set(
        selection.trend_indices
    )

    paper_of_week = (
        selection.paper_of_week_index
    )

    deep_dive = (
        selection.deep_dive_index
    )

    candidate_blocks = []

    for item in selected_candidates:

        index = item["index"]
        candidate = item["candidate"]

        roles = []

        if index in spotlight_indices:
            roles.append(
                "RESEARCH_SPOTLIGHT"
            )

        if index in trend_indices:
            roles.append(
                "TREND"
            )

        if index == paper_of_week:
            roles.append(
                "PAPER_OF_THE_WEEK"
            )

        if index == deep_dive:
            roles.append(
                "DEEP_DIVE"
            )

        role_text = (
            ", ".join(roles)
            if roles
            else "GENERAL"
        )

        candidate_blocks.append(
            f"""
CANDIDATE {index}

Editorial roles:
{role_text}

Title:
{candidate.title}

Source:
{candidate.source_name}

Published:
{candidate.published_at}

Authors:
{", ".join(candidate.authors)}

URL:
{candidate.url}

Supporting sources:
{", ".join(candidate.supporting_sources)}

Content:
{candidate.raw_content[:2200]}
""".strip()
        )

    candidates_text = "\n\n---\n\n".join(
        candidate_blocks
    )

    # ==================================================
    # OUTPUT PARSER
    # ==================================================

    parser = PydanticOutputParser(
        pydantic_object=NewsletterContent
    )

    # ==================================================
    # SYSTEM PROMPT
    # ==================================================

    system_prompt = """
You are the senior content editor for AINow,
an AI newsletter.

Create a concise, technically accurate newsletter
from the supplied research candidates.

IMPORTANT:
The output MUST remain compact enough to fit in
a single response.

Use ONLY information contained in the candidates.

Do not invent facts, statistics, results, authors,
or URLs.

Do not generate HTML.

Return ONLY valid JSON matching the supplied schema.

NEWSLETTER STRUCTURE AND HARD LIMITS:

KNOW

Quick News:
EXACTLY 3 items.

Each Quick News item:
- headline: one sentence
- summary: 1-2 sentences
- why_it_matters: 1 sentence
- source_urls: 1-2 URLs

Research Spotlight:
EXACTLY 3 items.

Each Research Spotlight:
- title
- problem: <= 2 sentences
- core_idea: <= 2 sentences
- key_result: <= 2 sentences
- why_it_matters: <= 2 sentences
- source_urls: 1-2 URLs

Paper of the Week:
EXACTLY 1 item.

Deep Dive:
EXACTLY 1 item.

Keep each Deep Dive field to <= 3 sentences.

AI Trends:
EXACTLY 2 items.

Each Trend:
- title
- explanation: <= 2 sentences
- evidence: <= 2 sentences
- source_urls: 1-2 URLs

LEARN

AI Concept:
EXACTLY 1 concept.

Keep each concept field concise.

USE

AI Resources:
0 to 3 items.

OUR TAKE:
Maximum 120 words.

SOURCES:
Include the source URLs actually used.

Do not produce more items than these limits.

Do not repeat the same candidate as a Quick News item
and Research Spotlight item unless it is the Paper
of the Week.
"""

    # ==================================================
    # USER PROMPT
    # ==================================================

    user_prompt = f"""
/no_think

AINow research topic:
{state["plan"].topic}

Editorial selection:

Research Spotlight:
{selection.research_spotlight_indices}

Paper of the Week:
{selection.paper_of_week_index}

Deep Dive:
{selection.deep_dive_index}

Trends:
{selection.trend_indices}

Candidates:

{candidates_text}

Generate the complete AINow V1 newsletter.

Be concise.

IMPORTANT:
Do not add extra items beyond the exact limits
specified by the system instructions.

{parser.get_format_instructions()}
"""

    # ==================================================
    # CALL LLM
    # ==================================================


    response = await invoke_editor_llm(
        [
            SystemMessage(
                content=system_prompt
            ),
            HumanMessage(
                content=user_prompt
            ),
        ]
    )

    print(
        "\n[LLM] Raw newsletter response:"
    )

    print(
        repr(response.content)
    )

    # ==================================================
    # PARSE
    # ==================================================

    try:

        content = parser.parse(
            response.content
        )

    except Exception as error:

        raise RuntimeError(
            "Failed to parse newsletter "
            f"content: {error}\n"
            f"Model output:\n"
            f"{response.content}"
        ) from error

    return {
        "newsletter_content":
            content
    }

def persist_newsletter_node(
    state,
):
    content = state.get(
        "newsletter_content"
    )

    if not content:
        return {
            "newsletter_issue_id": None
        }

    db = SessionLocal()

    try:

        issue = save_generated_newsletter(
            db=db,
            content=content,
            title="AINow — AI Weekly",
        )

        print(
            "\n[Newsletter] Draft saved:"
            f" id={issue.id}"
        )

        return {
            "newsletter_issue_id": issue.id
        }

    finally:
        db.close()