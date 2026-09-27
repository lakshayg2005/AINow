"""
Offline tests for story clustering helpers, scoring, triage
parsing and the free-LLM JSON extraction (no network, no DB).

    pytest tests/test_stories.py
"""

from datetime import timedelta

import pytest

from app.core.free_llm import extract_json
from app.db.models import RawItem, Story
from app.ingest.sources.feeds import fetch_rss
from app.ingest.sources.hackernews import hn_hit_to_item
from app.ingest.registry import IngestSource
from app.ingest.store import _item_embedding_text
from app.ingest.utils import external_id_for_url, is_ai_related, utcnow
from app.stories.entities import entity_keys, is_strong_key
from app.stories.scoring import (
    aggregate_story,
    buzz_score,
    coverage_score,
    recency_score,
    score_story,
)
from app.stories.triage import TriageDecision, heuristic_decision


def _raw(**overrides) -> RawItem:
    values = {
        "source_key": "hackernews",
        "source_name": "Hacker News",
        "kind": "article",
        "category": "news",
        "trust_tier": 2,
        "url": "https://example.com/a",
        "title": "Item",
        "signals": {},
        "published_at": utcnow(),
        "fetched_at": utcnow(),
    }
    values.update(overrides)
    return RawItem(**values)


def _story(**overrides) -> Story:
    values = {
        "id": 1,
        "title": "Story",
        "item_count": 1,
        "source_count": 1,
        "signals": {},
        "entities": [],
        "is_promotional": False,
        "importance": None,
        "last_seen_at": utcnow(),
    }
    values.update(overrides)
    return Story(**values)


# ============================================================
# Entity keys
# ============================================================

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Introducing Gemini 3.8 Live", {"gemini 3.8"}),
        ("Claude Opus 5.5", {"opus 5.5", "claude opus 5.5"}),
        ("unsloth/Qwen-Image-2.1-GGUF", {"image 2.1", "qwen image 2.1"}),
        ("XiaomiMiMo/MiMo-V2.6-Pro-RL", {"mimo v2.6", "xiaomimimo mimo v2.6"}),
        ("Qwen3.8-27B-GSQ", {"qwen3.8"}),
        ("Proaction boosts sales 60% in 2026", set()),
    ],
)
def test_entity_keys(text, expected):
    assert entity_keys(text) == expected


def test_same_release_shares_keys_across_sources():
    hn = entity_keys("Qwen Image 2.1")
    model = entity_keys("Qwen/Qwen-Image-2.1")
    assert "qwen image 2.1" in hn & model


def test_strong_keys():
    assert is_strong_key("claude opus 5.5")
    assert is_strong_key("gemini 3.8")
    assert is_strong_key("qwen3.8")
    assert not is_strong_key("gpt 6")


# ============================================================
# URLs / relevance / HN parsing
# ============================================================

@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://arxiv.org/abs/2609.28603", "arxiv:2609.28603"),
        ("https://arxiv.org/pdf/2609.28603v2", "arxiv:2609.28603"),
        ("https://huggingface.co/papers/2609.28603", "arxiv:2609.28603"),
        ("https://github.com/Owner/Repo", "github:owner/repo"),
        ("https://github.com/owner/repo/issues/1", None),
        ("https://huggingface.co/Qwen/Qwen-Image-2.1", "hf-model:Qwen/Qwen-Image-2.1"),
        ("https://huggingface.co/spaces/Qwen/Qwen-Image-2.1", "hf-space:Qwen/Qwen-Image-2.1"),
        ("https://huggingface.co/blog/some-post", None),
        ("https://www.anthropic.com/claude-opus-5-5", None),
    ],
)
def test_external_id_for_url(url, expected):
    assert external_id_for_url(url) == expected


def test_ai_filter_rejects_generic_agent_posts():
    assert not is_ai_related("VSCode's SSH Agent Is Bananas")
    assert is_ai_related("Cloud AI agents are inevitable")


def test_hn_story_text_html_is_cleaned():
    source = IngestSource(
        key="hackernews",
        name="Hacker News",
        fetcher=fetch_rss,
        kind="article",
        category="news",
    )

    item = hn_hit_to_item(
        source,
        {
            "objectID": "1",
            "title": "Show HN: Thing",
            "story_text": "<p>I built <a href=\"https:&#x2F;&#x2F;x.dev\">this</a>.</p>",
        },
    )

    assert item.summary == "I built this ."


def test_thin_summary_embeds_content_instead():
    row = _raw(title="Claude Opus 5.5", summary="link", content="Anthropic's most capable model " * 50)
    assert "most capable" in _item_embedding_text(row)

    row = _raw(title="T", summary="A long useful summary " * 10, content="other text")
    assert "other text" not in _item_embedding_text(row)


# ============================================================
# Scoring
# ============================================================

def test_buzz_score_bounds_and_order():
    assert buzz_score({}) == 0
    assert buzz_score({"hn_points": 50}) < buzz_score({"hn_points": 800})
    assert buzz_score({"hn_points": 5000, "stars": 9000}) == 1.0


def test_coverage_and_recency():
    assert coverage_score(1, 0) == 0
    assert coverage_score(4, 0) == 1.0
    assert coverage_score(2, 1) > coverage_score(2, 0)

    now = utcnow()
    assert recency_score(now, now) == 1.0
    assert recency_score(now - timedelta(days=4), now) == pytest.approx(0.5)


def test_promotional_story_is_halved():
    base = _story(importance=6, signals={"hn_points": 200})
    promo = _story(importance=6, signals={"hn_points": 200}, is_promotional=True)

    assert score_story(promo) == pytest.approx(score_story(base) / 2, abs=0.02)


def test_aggregate_prefers_lab_post_then_most_discussed_title():
    story = _story()

    items = [
        _raw(source_key="aws_ml", category="technical", title="Claude Opus 5.5 is now available on AWS"),
        _raw(title="Claude Opus 5.5", signals={"hn_points": 1801, "seen_in": ["hackernews"]}, image_url="https://i/og.png"),
        _raw(title="Opus 5.5 benchmarks", signals={"hn_points": 50}),
    ]

    aggregate_story(story, items)

    assert story.title == "Claude Opus 5.5"
    assert story.item_count == 3
    assert story.source_count == 2
    assert story.signals["hn_points"] == 1801
    assert story.image_url == "https://i/og.png"

    items.append(_raw(source_key="anthropic", category="company", title="Introducing Claude Opus 5.5"))
    aggregate_story(story, items)

    assert story.title == "Introducing Claude Opus 5.5"


def test_like_farmed_model_is_discounted():
    story = _story()
    aggregate_story(
        story,
        [_raw(kind="model", signals={"likes": 4000, "downloads": 0})],
    )

    assert story.signals["likes"] == pytest.approx(400)


# ============================================================
# Triage parsing
# ============================================================

def test_triage_decision_normalizes_model_output():
    decision = TriageDecision.model_validate(
        {"id": 3, "category": "Model Release", "importance": "12", "summary": "x"}
    )

    assert decision.category == "model_release"
    assert decision.importance == 10

    assert TriageDecision.model_validate(
        {"id": 3, "category": "gossip", "importance": 0}
    ).category == "other"


def test_heuristic_decision():
    paper = _story(signals={"kinds": ["paper"]})
    assert heuristic_decision(paper).category == "research"

    court = _story(title="Appeals court upholds ruling against AI lab", signals={"kinds": ["article"]})
    assert heuristic_decision(court).category == "policy"

    awesome = _story(title="someone/awesome-agents", signals={"kinds": ["repo"]})
    assert heuristic_decision(awesome).promotional


# ============================================================
# LLM JSON extraction
# ============================================================

@pytest.mark.parametrize(
    "text",
    [
        '{"stories": []}',
        '<think>\nhmm\n</think>\n\n{"stories": []}',
        '```json\n{"stories": []}\n```',
        'Here you go:\n{"stories": []}\nHope that helps!',
    ],
)
def test_extract_json(text):
    assert extract_json(text) == {"stories": []}


def test_extract_json_raises_without_json():
    with pytest.raises(ValueError):
        extract_json("no json here")
