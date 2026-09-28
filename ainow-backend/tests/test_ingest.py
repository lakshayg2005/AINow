"""
Offline tests for the ingestion layer (no network, no DB).

    pytest tests/test_ingest.py
"""

from datetime import timedelta

from app.ingest.chunking import MAX_CHUNK_CHARS, chunk_text
from app.ingest.enrich import clean_readme, extract_page_metadata
from app.ingest.registry import IngestSource, get_ingest_sources
from app.ingest.runner import dedupe_batch, filter_items
from app.ingest.sources.feeds import fetch_rss, parse_feed
from app.ingest.sources.hackernews import hn_hit_to_item
from app.ingest.sources.huggingface import daily_paper_to_item
from app.ingest.utils import canonical_url, is_ai_related, utcnow
from app.schemas.ingest import IngestedItem


def _source(**overrides) -> IngestSource:
    values = {
        "key": "test",
        "name": "Test",
        "fetcher": fetch_rss,
        "kind": "article",
        "category": "news",
    }
    values.update(overrides)
    return IngestSource(**values)


def _item(**overrides) -> IngestedItem:
    values = {
        "source_key": "test",
        "source_name": "Test",
        "kind": "article",
        "category": "news",
        "url": "https://example.com/a",
        "title": "New LLM released",
        "published_at": utcnow(),
    }
    values.update(overrides)
    return IngestedItem(**values)


# ============================================================
# URLs / relevance
# ============================================================

def test_canonical_url_strips_tracking_and_fragment():
    assert canonical_url(
        "HTTPS://Example.com/Post/?utm_source=x&id=7&fbclid=y#top"
    ) == "https://example.com/Post?id=7"


def test_canonical_url_keeps_root_slash():
    assert canonical_url("https://example.com") == "https://example.com/"


def test_is_ai_related():
    assert is_ai_related("Qwen Image 2.1 released")
    assert is_ai_related("Why AI agents need memory")
    assert not is_ai_related("Show HN: A faster SQLite backup tool")


# ============================================================
# Feeds
# ============================================================

RSS = """<?xml version="1.0"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>T</title>
<item>
  <title>Model X launches</title>
  <link>https://example.com/x/?utm_source=rss</link>
  <pubDate>Fri, 25 Sep 2026 19:00:00 GMT</pubDate>
  <description>&lt;p&gt;Short teaser.&lt;/p&gt;&lt;img src="https://img.example.com/x.png"&gt;</description>
</item>
<item>
  <title>Second post</title>
  <link>https://example.com/y</link>
  <media:content url="https://img.example.com/y.jpg" medium="image"/>
</item>
</channel></rss>"""


def test_parse_feed_extracts_fields_and_images():
    items = parse_feed(_source(), RSS)

    assert [item.title for item in items] == ["Model X launches", "Second post"]

    first, second = items
    assert first.url == "https://example.com/x"
    assert first.summary == "Short teaser."
    assert first.image_url == "https://img.example.com/x.png"
    assert first.published_at.isoformat() == "2026-09-25T19:00:00"
    assert second.image_url == "https://img.example.com/y.jpg"
    assert second.published_at is None


# ============================================================
# Hugging Face / Hacker News
# ============================================================

def test_daily_paper_to_item():
    record = {
        "paper": {
            "id": "2609.28603",
            "title": "Learning to Discover Interesting Mathematics",
            "summary": "We define intrinsic interestingness...",
            "authors": [{"name": "Julia Kempe"}],
            "publishedAt": "2026-09-23T00:00:00.000Z",
            "upvotes": 8,
        },
        "thumbnail": "https://cdn.example/2609.28603.png",
        "numComments": 2,
    }

    item = daily_paper_to_item(_source(kind="paper", category="research"), record)

    assert item.url == "https://huggingface.co/papers/2609.28603"
    assert item.external_id == "arxiv:2609.28603"
    assert item.image_url == "https://cdn.example/2609.28603.png"
    assert item.signals == {"hf_upvotes": 8.0, "hf_comments": 2.0}
    assert "arxiv.org/abs/2609.28603" in item.content


def test_hn_hit_links_article_and_keeps_discussion():
    hit = {
        "objectID": "123",
        "title": "Claude Opus 5.5",
        "url": "https://www.anthropic.com/claude-opus-5-5",
        "points": 1801,
        "num_comments": 900,
        "created_at": "2026-09-24T10:00:00Z",
    }

    item = hn_hit_to_item(_source(), hit)

    assert item.kind == "article"
    assert item.url == "https://www.anthropic.com/claude-opus-5-5"
    assert item.discussion_url == "https://news.ycombinator.com/item?id=123"
    assert item.signals["hn_points"] == 1801.0


def test_hn_ask_post_without_url_is_discussion():
    item = hn_hit_to_item(
        _source(),
        {"objectID": "9", "title": "Ask HN: Best local LLM?", "points": 50},
    )

    assert item.kind == "discussion"
    assert item.url == "https://news.ycombinator.com/item?id=9"


# ============================================================
# Filtering / batch dedupe
# ============================================================

def test_filter_items_applies_window_and_ai_filter():
    now = utcnow()
    items = [
        _item(url="https://e.com/1", title="LLM news"),
        _item(url="https://e.com/2", title="LLM news", published_at=now - timedelta(days=30)),
        _item(url="https://e.com/3", title="Gardening tips"),
        _item(url="https://e.com/4", title="LLM undated", published_at=None),
        _item(url="https://e.com/5", title="LLM future", published_at=now + timedelta(days=5)),
    ]

    kept = filter_items(_source(ai_filter=True), items, lookback_days=7)

    assert [item.url for item in kept] == ["https://e.com/1", "https://e.com/4"]


def test_filter_items_respects_source_max_age():
    old = _item(published_at=utcnow() - timedelta(days=20))

    assert filter_items(_source(), [old], lookback_days=7) == []
    assert filter_items(_source(max_age_days=30), [old], lookback_days=7) == [old]


def test_dedupe_batch_merges_by_url_and_external_id():
    items = [
        _item(url="https://hf.co/papers/1", external_id="arxiv:1", signals={"hf_upvotes": 5}),
        _item(url="https://arxiv.org/abs/1", external_id="arxiv:1", content="full abstract"),
        _item(url="https://hf.co/papers/1", signals={"hn_points": 99}, image_url="https://i/1.png"),
        _item(url="https://other.com/2"),
    ]

    result = dedupe_batch(items)

    assert len(result) == 2
    merged = result[0]
    assert merged.signals == {"hf_upvotes": 5, "hn_points": 99}
    assert merged.content == "full abstract"
    assert merged.image_url == "https://i/1.png"


# ============================================================
# Enrichment helpers
# ============================================================

PAGE = """<html><head>
<meta property="og:image" content="/images/hero.png">
<meta property="og:description" content="A new open model.">
<meta property="article:published_time" content="2026-09-24T08:30:00+02:00">
</head><body><article>
<p>The team released an open-weights model that matches frontier systems on reasoning benchmarks.</p>
<p>It is available under Apache 2.0 and runs on a single GPU with quantization enabled.</p>
</article></body></html>"""


def test_extract_page_metadata():
    meta = extract_page_metadata(PAGE, "https://lab.example.com/blog/post")

    assert meta.image_url == "https://lab.example.com/images/hero.png"
    assert meta.description == "A new open model."
    assert meta.published_at.isoformat() == "2026-09-24T06:30:00"
    assert "open-weights model" in meta.text


def test_clean_readme_strips_front_matter_badges_and_html():
    readme = (
        "---\nlicense: apache-2.0\n---\n"
        "[![CI](https://badge)](https://ci)\n"
        "# Model <b>X</b>\n\n\n\nFast inference."
    )

    assert clean_readme(readme) == "# Model X\n\nFast inference."


# ============================================================
# Chunking
# ============================================================

def test_chunk_text_packs_paragraphs_with_overlap():
    paragraphs = [f"Paragraph {i} " + "word " * 60 for i in range(10)]
    chunks = chunk_text("\n\n".join(paragraphs))

    assert len(chunks) > 1
    assert all(len(chunk) <= MAX_CHUNK_CHARS + 200 for chunk in chunks)
    # Overlap: each later chunk starts with the tail of the previous one.
    assert chunks[1].split("\n\n")[0] in chunks[0]


def test_chunk_text_splits_giant_paragraph():
    chunks = chunk_text("Sentence number one is here. " * 300)

    assert len(chunks) > 1
    assert all(len(chunk) <= MAX_CHUNK_CHARS + 200 for chunk in chunks)


def test_chunk_text_empty():
    assert chunk_text(None) == []
    assert chunk_text("   ") == []


# ============================================================
# Registry
# ============================================================

def test_registry_keys_unique_and_arxiv_disabled_by_default():
    keys = [source.key for source in get_ingest_sources()]

    assert len(keys) == len(set(keys))
    assert "arxiv" not in keys
    assert [s.key for s in get_ingest_sources(["arxiv"])] == ["arxiv"]
