from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    collect_node,
    editorial_selection_node,
    freshness_node,
    plan_node,
    ranking_node,
    content_generation_node,
    persist_newsletter_node,
)
from app.graph.state import ResearchState


builder = StateGraph(
    ResearchState
)


builder.add_node(
    "plan",
    plan_node,
)

builder.add_node(
    "collect",
    collect_node,
)

builder.add_node(
    "freshness",
    freshness_node,
)

builder.add_node(
    "ranking",
    ranking_node,
)
builder.add_node(
    "editorial_selection",
    editorial_selection_node,
)
builder.add_node(
    "content_generation",
    content_generation_node,
)
builder.add_node(
    "persist_newsletter",
    persist_newsletter_node,
)

builder.add_edge(
    START,
    "plan",
)

builder.add_edge(
    "plan",
    "collect",
)

builder.add_edge(
    "collect",
    "freshness",
)

builder.add_edge(
    "freshness",
    "ranking",
)

builder.add_edge(
    "ranking",
    "editorial_selection",
)

builder.add_edge(
    "editorial_selection",
    "content_generation",
)

builder.add_edge(
    "content_generation",
    "persist_newsletter",
)

builder.add_edge(
    "persist_newsletter",
    END,
)


research_graph = builder.compile()