"""
Compose one newsletter issue from the week's stories, as a
LangGraph state graph:

    select stories per section
        -> retrieve grounded context per story (RAG)
        -> write each section (free LLM, cited)
        -> verify numbers against the context
        -> editorial pass (headline, intro, trends, concept, take)
        -> assemble, renumber sources to the ones actually cited
        -> check images, then review the draft for the editor

Each step above is one graph node operating on a shared
`ComposeState`; `compose_issue` just builds the initial state,
runs the compiled graph, and returns the finished `IssueContent`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.compose.composer import _history_lines, _pool_line, _renumber_sources, _verify_fields
from app.compose.context import SourceRegistry, StoryContext, build_story_context
from app.compose.images import vet_images
from app.compose.review import review_issue
from app.compose.selection import Candidate, Selection, build_candidates, select_sections
from app.compose.verify import strip_unsupported
from app.compose.writer import (
    editor_prompt,
    write_deep_dive,
    write_editorial,
    write_quick_news,
    write_research,
    write_resources,
)
from app.db.models import RawItem
from app.ingest.utils import utcnow
from app.schemas.issue import IssueContent, IssueStats


# ============================================================
# State
# ============================================================

class ComposeState(TypedDict, total=False):
    db: Session
    window_days: int
    now: datetime

    candidates: list[Candidate]
    selection: Selection
    registry: SourceRegistry
    models: set[str]

    news_ctx: list[StoryContext]
    research_ctx: list[StoryContext]
    paper_ctx: list[StoryContext]
    dive_ctx: list[StoryContext]
    resource_ctx: list[StoryContext]
    context_text: dict[int, str]

    quick_news: list
    research_cards: list
    paper_of_week: object | None
    deep_dive: object | None
    resources: list
    removed: int

    story_refs: dict[int, list[int]]
    editorial: dict
    intro: str
    our_take: str

    content: IssueContent


# ============================================================
# Nodes
# ============================================================

def _select_node(state: ComposeState) -> dict:
    db = state["db"]
    candidates = build_candidates(db, window_days=state["window_days"])

    if not candidates:
        raise RuntimeError(
            "No eligible stories in the window. Run `python -m app.ingest` first."
        )

    selection = select_sections(candidates)

    print(
        f"[Compose] {len(candidates)} candidates -> "
        f"{len(selection.quick_news)} news, {len(selection.research)} research, "
        f"paper={'yes' if selection.paper_of_week else 'no'}, "
        f"deep dive={'yes' if selection.deep_dive else 'no'}, "
        f"{len(selection.resources)} resources"
    )

    return {
        "candidates": candidates,
        "selection": selection,
        "registry": SourceRegistry(),
        "models": set(),
    }


def _retrieve_node(state: ComposeState) -> dict:
    db = state["db"]
    selection = state["selection"]
    registry = state["registry"]

    def contexts(pool, need, max_chars=3500, max_sources=4) -> list[StoryContext]:
        return [
            build_story_context(db, c, registry, need, max_chars, max_sources)
            for c in pool
        ]

    return {
        "news_ctx": contexts(
            selection.quick_news,
            "what was announced or happened, key facts, who is affected",
            max_chars=2800,
        ),
        "research_ctx": contexts(
            selection.research,
            "problem, method, main results and numbers",
            max_chars=2500,
            max_sources=2,
        ),
        "paper_ctx": contexts(
            [selection.paper_of_week] if selection.paper_of_week else [],
            "problem, method, main results and numbers",
            max_chars=3500,
            max_sources=3,
        ),
        "dive_ctx": contexts(
            [selection.deep_dive] if selection.deep_dive else [],
            "technical details, how it works, results, implications, open questions",
            max_chars=9000,
            max_sources=5,
        ),
        "resource_ctx": contexts(
            selection.resources,
            "what it does, key features, how to use it",
            max_chars=2000,
            max_sources=2,
        ),
    }


# Writes run as separate sequential nodes (not fanned out in
# parallel): free-tier providers rate-limit bursts of calls.

async def _write_news_node(state: ComposeState) -> dict:
    print("[Compose] Writing Quick News...")
    quick_news = await write_quick_news(state["news_ctx"], state["models"])
    return {"quick_news": quick_news, "models": state["models"]}


async def _write_research_node(state: ComposeState) -> dict:
    print("[Compose] Writing Research...")
    paper_ctx = state["paper_ctx"]
    research_cards = await write_research(
        state["research_ctx"] + paper_ctx, state["models"]
    )
    paper_of_week = research_cards.pop() if paper_ctx and research_cards else None

    return {
        "research_cards": research_cards,
        "paper_of_week": paper_of_week,
        "models": state["models"],
    }


async def _write_deep_dive_node(state: ComposeState) -> dict:
    print("[Compose] Writing Deep Dive...")
    dive_ctx = state["dive_ctx"]
    deep_dive = await write_deep_dive(dive_ctx[0] if dive_ctx else None, state["models"])
    return {"deep_dive": deep_dive, "models": state["models"]}


async def _write_resources_node(state: ComposeState) -> dict:
    print("[Compose] Writing Resources...")
    resources = await write_resources(state["resource_ctx"], state["models"])
    return {"resources": resources, "models": state["models"]}


def _verify_node(state: ComposeState) -> dict:
    context_text = {
        ctx.story.id: ctx.text
        for ctx in (
            state["news_ctx"]
            + state["research_ctx"]
            + state["paper_ctx"]
            + state["dive_ctx"]
            + state["resource_ctx"]
        )
    }

    paper_of_week = state.get("paper_of_week")
    deep_dive = state.get("deep_dive")
    removed = 0

    for card in state["quick_news"]:
        removed += _verify_fields(
            card, ("headline", "summary", "why_it_matters"), context_text[card.story_id]
        )

    for card in state["research_cards"] + ([paper_of_week] if paper_of_week else []):
        removed += _verify_fields(
            card,
            ("problem", "core_idea", "key_result", "why_it_matters"),
            context_text[card.story_id],
        )

    if deep_dive:
        dive_context = context_text[deep_dive.story_id]
        removed += _verify_fields(deep_dive, ("introduction",), dive_context)

        for section in deep_dive.sections:
            removed += _verify_fields(section, ("body",), dive_context)

        deep_dive.sections = [s for s in deep_dive.sections if s.body]

    for card in state["resources"]:
        removed += _verify_fields(
            card, ("description", "why_useful"), context_text[card.story_id]
        )

    return {"context_text": context_text, "deep_dive": deep_dive, "removed": removed}


async def _editorial_node(state: ComposeState) -> dict:
    db = state["db"]
    selection = state["selection"]
    registry = state["registry"]
    quick_news = state["quick_news"]
    research_cards = state["research_cards"]
    paper_of_week = state.get("paper_of_week")
    deep_dive = state.get("deep_dive")
    resources = state["resources"]

    issue_lines = [
        f"[{card.story_id}] {card.headline} — {card.summary}" for card in quick_news
    ]
    issue_lines += [
        f"[{card.story_id}] (paper) {card.title} — {card.core_idea}"
        for card in research_cards + ([paper_of_week] if paper_of_week else [])
    ]

    if deep_dive:
        issue_lines.append(
            f"[{deep_dive.story_id}] (deep dive) {deep_dive.title} — {deep_dive.introduction}"
        )

    issue_lines += [
        f"[{card.story_id}] (resource) {card.name} — {card.description}" for card in resources
    ]

    chosen_ids = {c.story.id for c in selection.chosen()}
    pool_lines = [
        _pool_line(c) for c in selection.pool if c.story.id not in chosen_ids
    ][:30]

    # Trends may cite pool stories; register their primary
    # source so the trend can link to it.
    story_refs: dict[int, list[int]] = {
        ctx.story.id: ctx.ref_ids
        for ctx in (
            state["news_ctx"]
            + state["research_ctx"]
            + state["paper_ctx"]
            + state["dive_ctx"]
            + state["resource_ctx"]
        )
    }

    for candidate in selection.pool[:40]:
        if candidate.story.id not in story_refs and candidate.items:
            story_refs[candidate.story.id] = [registry.ref(candidate.items[0]).id]

    editor_context = "\n".join(issue_lines + pool_lines)

    print("[Compose] Editorial pass...")
    editorial = await write_editorial(
        editor_prompt(issue_lines, pool_lines, _history_lines(db)),
        valid_story_ids=set(story_refs),
        story_refs=story_refs,
        models=state["models"],
    )

    removed = state["removed"]

    for trend in editorial["trends"]:
        removed += _verify_fields(trend, ("explanation", "evidence"), editor_context)

    intro, removed_intro = strip_unsupported(editorial["intro"], editor_context)

    # Editorial call failed: a plain but accurate intro beats none.
    if not intro and quick_news:
        highlights = [card.headline.rstrip(".") for card in quick_news[:3]]

        if deep_dive:
            highlights.insert(0, deep_dive.title.rstrip("."))

        intro = "This week: " + "; ".join(highlights[:3]) + "."

    our_take, removed_take = strip_unsupported(editorial["our_take"], editor_context)
    removed += removed_intro + removed_take

    return {
        "editorial": editorial,
        "story_refs": story_refs,
        "intro": intro,
        "our_take": our_take,
        "removed": removed,
        "models": state["models"],
    }


def _assemble_node(state: ComposeState) -> dict:
    db = state["db"]
    now = state["now"]
    window_days = state["window_days"]
    editorial = state["editorial"]
    quick_news = state["quick_news"]
    deep_dive = state.get("deep_dive")

    items_scanned = db.scalar(
        select(func.count()).select_from(RawItem).where(
            RawItem.fetched_at >= now - timedelta(days=window_days)
        )
    )

    content = IssueContent(
        title=f"AINow Weekly — {now:%B} {now.day}, {now.year}",
        headline=(
            editorial["headline"]
            or (deep_dive.title if deep_dive else "")
            or (quick_news[0].headline if quick_news else "")
        ),
        intro=state["intro"],
        issue_date=now,
        quick_news=quick_news,
        research_spotlight=state["research_cards"],
        paper_of_week=state.get("paper_of_week"),
        deep_dive=deep_dive,
        trends=editorial["trends"],
        concept=editorial["concept"],
        resources=state["resources"],
        our_take=state["our_take"],
        stats=IssueStats(
            items_scanned=items_scanned or 0,
            stories_considered=len(state["candidates"]),
            window_days=window_days,
            models=sorted(state["models"]),
            numbers_removed=state["removed"],
        ),
    )

    return {"content": content}


def _renumber_node(state: ComposeState) -> dict:
    content = state["content"]
    _renumber_sources(content, state["registry"])
    content.stats.sources_used = len(content.sources)
    return {"content": content}


async def _images_node(state: ComposeState) -> dict:
    print("[Compose] Checking images...")
    content = state["content"]
    content.stats.images_replaced = await vet_images(state["db"], content)
    return {"content": content}


async def _review_node(state: ComposeState) -> dict:
    print("[Compose] Reviewing draft...")
    content = state["content"]
    content.review = await review_issue(state["db"], content)
    return {"content": content}


# ============================================================
# Graph
# ============================================================

def _build_graph():
    builder = StateGraph(ComposeState)

    builder.add_node("select", _select_node)
    builder.add_node("retrieve", _retrieve_node)
    builder.add_node("write_news", _write_news_node)
    builder.add_node("write_research", _write_research_node)
    builder.add_node("write_deep_dive", _write_deep_dive_node)
    builder.add_node("write_resources", _write_resources_node)
    builder.add_node("verify", _verify_node)
    builder.add_node("editorial", _editorial_node)
    builder.add_node("assemble", _assemble_node)
    builder.add_node("renumber", _renumber_node)
    builder.add_node("images", _images_node)
    builder.add_node("review", _review_node)

    builder.add_edge(START, "select")
    builder.add_edge("select", "retrieve")
    builder.add_edge("retrieve", "write_news")
    builder.add_edge("write_news", "write_research")
    builder.add_edge("write_research", "write_deep_dive")
    builder.add_edge("write_deep_dive", "write_resources")
    builder.add_edge("write_resources", "verify")
    builder.add_edge("verify", "editorial")
    builder.add_edge("editorial", "assemble")
    builder.add_edge("assemble", "renumber")
    builder.add_edge("renumber", "images")
    builder.add_edge("images", "review")
    builder.add_edge("review", END)

    return builder.compile()


_graph = _build_graph()


async def compose_issue(
    db: Session,
    window_days: int = 7,
) -> IssueContent:
    final_state = await _graph.ainvoke(
        {
            "db": db,
            "window_days": window_days,
            "now": utcnow(),
        },
        config={"recursion_limit": 30},
    )

    return final_state["content"]
