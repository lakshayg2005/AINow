"""
Offline tests for issue composition and rendering (no network, no DB).

    pytest tests/test_compose.py
"""

from datetime import datetime

from app.compose.composer import _renumber_sources
from app.compose.context import SourceRegistry, StoryContext, _outlet_name, _pick_sources
from app.compose.persist import load_issue_content
from app.compose.selection import Candidate, select_sections
from app.compose.verify import claim_numbers, strip_unsupported, unsupported_numbers
from app.compose.writer import _prose, _text, valid_refs
from app.db.models import NewsletterIssue, RawItem, Story
from app.ingest.utils import utcnow
from app.schemas.issue import (
    DeepDiveCard,
    DeepDiveSection,
    IssueContent,
    QuickNewsCard,
    ResourceCard,
    TrendCard,
)
from app.services.issue_email import render_issue_email
from app.stories.novelty import NoveltyResult
from app.stories.scoring import is_official_repo, looks_like_icon


_next_id = iter(range(1, 10_000))


def _raw(**overrides) -> RawItem:
    values = {
        "id": next(_next_id),
        "source_key": "techcrunch_ai",
        "source_name": "TechCrunch AI",
        "kind": "article",
        "category": "news",
        "trust_tier": 2,
        "url": f"https://example.com/{next(_next_id)}",
        "title": "Item",
        "content": "x" * 1000,
        "signals": {},
        "published_at": utcnow(),
        "fetched_at": utcnow(),
    }
    values.update(overrides)
    return RawItem(**values)


def _candidate(category="product", importance=7, kinds=("article",), sources=1, score=50.0, chars=5000, title=None):
    story_id = next(_next_id)
    story = Story(
        id=story_id,
        title=title or f"Story {story_id}",
        category=category,
        importance=importance,
        score=score,
        source_count=sources,
        signals={},
        entities=[],
        is_promotional=False,
    )
    items = [_raw(kind=kind, content="y" * (chars // len(kinds))) for kind in kinds]
    return Candidate(story=story, novelty=NoveltyResult(status="new"), items=items)


# ============================================================
# Number guard
# ============================================================

def test_claim_numbers_skips_single_digits():
    assert claim_numbers("GPT-6 scores 92.5% and is 3x faster, costing 1,200 dollars") == [
        "92.5",
        "3",
        "1200",
    ]


def test_unsupported_numbers():
    context = "The model scores 92.5% on MMLU and costs 40% less."
    assert unsupported_numbers("It scores 92.5% and costs 40% less.", context) == []
    assert unsupported_numbers("It is 3x faster.", context) == ["3"]


def test_strip_unsupported_removes_only_bad_sentences():
    context = "Opus 5.5 costs 40% less than Opus 5."
    text = "Opus 5.5 costs 40% less. It scores 97% on SWE-bench. It ships today."

    cleaned, removed = strip_unsupported(text, context)

    assert removed == 1
    assert cleaned == "Opus 5.5 costs 40% less. It ships today."


# ============================================================
# Writer helpers
# ============================================================

def test_text_strips_inline_citations_and_prose_ends_sentence():
    entry = {"body": "It costs 40% less [16]. It was tested by METR [16, 19]", "name": "magpie"}

    assert _text(entry, "body") == "It costs 40% less. It was tested by METR"
    assert _prose(entry, "body").endswith("METR.")
    assert _text(entry, "name") == "magpie"


def test_valid_refs_filters_to_story_sources():
    context = StoryContext(candidate=_candidate())
    context.refs = []
    registry = SourceRegistry()
    context.refs = [registry.ref(item) for item in context.candidate.items]

    allowed = context.ref_ids[0]

    assert valid_refs([allowed, 999, "S1", "x"], context) == [allowed]
    assert valid_refs([], context) == [allowed]


# ============================================================
# Sources
# ============================================================

def test_outlet_name_for_hn_links():
    hn = _raw(source_key="hackernews", source_name="Hacker News", url="https://www.cnbc.com/a")
    ask = _raw(source_key="hackernews", source_name="Hacker News", url="https://news.ycombinator.com/item?id=1")

    assert _outlet_name(hn) == "cnbc.com"
    assert _outlet_name(ask) == "Hacker News"


def test_pick_sources_prefers_official_and_one_per_outlet():
    items = [
        _raw(kind="model", title="abenzerps/Qwen-Image-2.1-Uncensored", url="https://huggingface.co/abenzerps/x", category="open-source", trust_tier=1, content="z" * 9000),
        _raw(kind="model", title="Qwen/Qwen-Image-2.1", url="https://huggingface.co/Qwen/Qwen-Image-2.1", category="open-source", trust_tier=1, content="z" * 800),
        _raw(url="https://github.com/a/b", title="a/b"),
    ]

    picked = _pick_sources(items, limit=4, story_title="Qwen Image 2.1")

    assert picked[0].title == "Qwen/Qwen-Image-2.1"
    assert len(picked) == 2  # one huggingface.co source only


def test_is_official_repo_and_icon_detection():
    assert is_official_repo(_raw(kind="model", title="Qwen/Qwen-Image-2.1"), "Qwen Image 2.1")
    assert not is_official_repo(_raw(kind="model", title="unsloth/Qwen-Image-2.1-GGUF"), "Qwen Image 2.1")

    assert looks_like_icon("https://img.alicdn.com/x/O1CN01-tps-80-80.png")
    assert looks_like_icon("https://site.com/static/favicon.png")
    assert not looks_like_icon("https://cdn.site.com/og/1200x630.jpg")


def _content(**overrides) -> IssueContent:
    values = {
        "title": "AINow Weekly — September 27, 2026",
        "headline": "Opus 5.5 & GPT-6 <start> a price war",
        "intro": "This week: two frontier launches.",
        "issue_date": datetime(2026, 9, 27),
    }
    values.update(overrides)
    return IssueContent(**values)


def test_renumber_sources_keeps_cited_in_citation_order():
    registry = SourceRegistry()
    items = [_raw(title=f"Source {i}") for i in range(4)]
    refs = [registry.ref(item).id for item in items]  # 1..4

    content = _content(
        quick_news=[QuickNewsCard(story_id=1, headline="h", summary="s", refs=[refs[2], refs[0]])],
        trends=[TrendCard(title="t", explanation="e", refs=[refs[0]])],
    )

    _renumber_sources(content, registry)

    assert content.quick_news[0].refs == [1, 2]
    assert content.trends[0].refs == [2]
    assert [source.title for source in content.sources] == ["Source 2", "Source 0"]


# ============================================================
# Selection
# ============================================================

def test_selection_fills_sections_without_duplicates():
    pool = [
        _candidate(category="product", importance=8, sources=3, chars=40000, score=90, title="Claude Opus 5.5"),
        _candidate(category="product", importance=8, sources=2, chars=6000, score=95),
        _candidate(category="product", importance=7, sources=4, chars=20000, score=85),
        _candidate(category="product", importance=7, score=80),
        _candidate(category="policy", importance=8, score=70),
        _candidate(category="research", importance=7, kinds=("paper",), score=60),
        _candidate(category="research", importance=6, kinds=("paper",), score=59),
        _candidate(category="open_source", importance=6, kinds=("repo",), score=58),
        _candidate(category="product", importance=3, score=99),  # below news bar
    ]

    selection = select_sections(pool)

    assert selection.deep_dive.story.title == "Claude Opus 5.5"
    assert selection.paper_of_week is not None
    assert len(selection.research) == 1
    assert [c.story.category for c in selection.resources] == ["open_source"]

    news_ids = [c.story.id for c in selection.quick_news]
    assert pool[8].story.id not in news_ids

    # Top stories are never dropped for category diversity:
    # three "product" stories make it in.
    assert sum(c.story.category == "product" for c in selection.quick_news) == 3

    chosen = [c.story.id for c in selection.chosen()]
    assert len(chosen) == len(set(chosen))


def test_repo_with_article_coverage_is_news_not_resource():
    launch = _candidate(category="model_release", kinds=("article", "model", "repo"))
    lone_repo = _candidate(category="open_source", kinds=("repo",))

    assert not launch.is_resource
    assert lone_repo.is_resource


# ============================================================
# Email + persistence helpers
# ============================================================

def test_email_renders_sections_escapes_and_links():
    registry = SourceRegistry()
    ref = registry.ref(_raw(title="Launch post", url="https://lab.example/post?a=1&b=2", source_name="Lab"))

    content = _content(
        quick_news=[
            QuickNewsCard(
                story_id=1,
                headline="Lab ships <Model X>",
                summary="It is fast.",
                why_it_matters="Cheaper agents.",
                category="model_release",
                image_url="https://img.example/x.png",
                is_update=True,
                refs=[ref.id],
            )
        ],
        deep_dive=DeepDiveCard(
            story_id=2,
            title="Deep",
            introduction="Intro.",
            sections=[DeepDiveSection(heading="How it works", body="Details.")],
        ),
        resources=[
            ResourceCard(story_id=3, name="magpie", resource_type="GitHub repo", description="d", url="https://github.com/a/b")
        ],
        our_take="Take.",
        sources=registry.all(),
    )

    html = render_issue_email(content, web_url="https://ainow.example/newsletters/9", manage_url="https://ainow.example/dashboard")

    assert "Lab ships &lt;Model X&gt;" in html
    assert "&lt;start&gt;" in html
    assert "https://lab.example/post?a=1&amp;b=2" in html
    assert "https://img.example/x.png" in html
    assert "Update" in html
    assert "How it works" in html
    assert "Open GitHub repo" in html
    assert "Read on the web" in html and "https://ainow.example/newsletters/9" in html
    assert "Manage subscription" in html
    assert "<script" not in html


def test_load_issue_content_detects_v2_only():
    v2 = NewsletterIssue(raw_content=_content().model_dump_json(indent=2))
    legacy = NewsletterIssue(raw_content='{\n  "quick_news": []\n}')

    assert load_issue_content(v2).headline.startswith("Opus 5.5")
    assert load_issue_content(legacy) is None
    assert load_issue_content(NewsletterIssue(raw_content=None)) is None


def test_story_ids_lists_every_story_card():
    content = _content(
        quick_news=[QuickNewsCard(story_id=1, headline="h", summary="s")],
        deep_dive=DeepDiveCard(story_id=2, title="d", introduction="i"),
        resources=[ResourceCard(story_id=3, name="n", resource_type="Model", description="d", url="u")],
    )

    assert [entry[0] for entry in content.story_ids()] == [1, 2, 3]
