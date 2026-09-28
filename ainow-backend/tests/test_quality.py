"""
Offline tests for draft quality: image checks, the editor
review, archive search helpers and the Anthropic scraper.

    pytest tests/test_quality.py
"""

import asyncio
import io
from datetime import datetime

import httpx
from PIL import Image

from app.compose import images
from app.compose.images import ImageChecker, acceptable_size, vet_images
from app.compose.review import draft_text, parse_review, structural_checks
from app.db.models import NewsletterIssue, RawItem
from app.ingest.sources.scraped import extract_anthropic_records, parse_page_date
from app.routes.newsletters import _detail
from app.schemas.issue import (
    DeepDiveCard,
    DeepDiveSection,
    IssueContent,
    IssueReview,
    QuickNewsCard,
)
from app.services.archive_search import _like_pattern
from app.stories.scoring import image_candidates


def _content(**overrides) -> IssueContent:
    values = {
        "title": "AINow Weekly — September 27, 2026",
        "headline": "GPT-6 arrives",
        "intro": "This week: a new frontier model.",
        "issue_date": datetime(2026, 9, 27),
    }
    values.update(overrides)
    return IssueContent(**values)


def _news(story_id: int, **overrides) -> QuickNewsCard:
    values = {
        "story_id": story_id,
        "headline": f"Story {story_id}",
        "summary": "A long enough summary that says what was announced, by whom, and what it changes for developers.",
        "refs": [1],
    }
    values.update(overrides)
    return QuickNewsCard(**values)


def _png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _image_server(sizes: dict[str, tuple[int, int]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if url.endswith(".svg"):
            return httpx.Response(200, content=b"<svg/>", headers={"content-type": "image/svg+xml"})

        if url not in sizes:
            return httpx.Response(404)

        return httpx.Response(200, content=_png(*sizes[url]), headers={"content-type": "image/png"})

    return httpx.MockTransport(handler)


# ============================================================
# Images
# ============================================================

def test_acceptable_size_rejects_headshots_and_icons():
    assert acceptable_size(1200, 630)          # og:image banner
    assert acceptable_size(1275, 1650)         # large portrait (paper page)
    assert not acceptable_size(300, 400)       # author headshot
    assert not acceptable_size(600, 800)       # small portrait
    assert not acceptable_size(128, 128)       # icon
    assert not acceptable_size(1200, 100)      # thin strip


def test_image_checker_measures_and_rejects():
    transport = _image_server({"https://a.test/banner.png": (1200, 630), "https://a.test/face.png": (300, 400)})

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            checker = ImageChecker(client)
            return [
                await checker.ok("https://a.test/banner.png"),
                await checker.ok("https://a.test/face.png"),
                await checker.ok("https://a.test/missing.png"),
                await checker.ok("https://a.test/logo.svg"),
            ]

    assert asyncio.run(run()) == [True, False, False, False]


def test_image_checker_keeps_unreachable_images():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        raise httpx.ConnectTimeout("slow host", request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ImageChecker(client).ok("https://slow.test/banner.png")

    # A timeout says nothing about the image: retried once, then kept.
    assert asyncio.run(run()) is True
    assert len(calls) == 2


def test_vet_images_restores_missing_image(monkeypatch):
    transport = _image_server({"https://a.test/banner.png": (1200, 630)})

    monkeypatch.setattr(images, "make_client", lambda: httpx.AsyncClient(transport=transport))
    monkeypatch.setattr(images, "_story_images", lambda db, story_id: ["https://a.test/banner.png"])

    content = _content(quick_news=[_news(1, image_url=None)])

    assert asyncio.run(vet_images(None, content)) == 1
    assert content.quick_news[0].image_url == "https://a.test/banner.png"


def test_vet_images_falls_back_and_never_repeats(monkeypatch):
    sizes = {
        "https://a.test/face.png": (300, 400),
        "https://a.test/banner.png": (1200, 630),
        "https://a.test/other.png": (1200, 630),
    }
    transport = _image_server(sizes)

    monkeypatch.setattr(images, "make_client", lambda: httpx.AsyncClient(transport=transport))
    monkeypatch.setattr(
        images,
        "_story_images",
        lambda db, story_id: {
            1: ["https://a.test/face.png", "https://a.test/banner.png"],
            2: ["https://a.test/banner.png"],
            3: ["https://a.test/other.png"],
        }[story_id],
    )

    content = _content(
        quick_news=[
            _news(1, image_url="https://a.test/face.png"),     # headshot -> next image
            _news(2, image_url="https://a.test/banner.png"),   # taken by story 1 -> dropped
            _news(3, image_url="https://a.test/other.png"),    # fine
        ]
    )

    changed = asyncio.run(vet_images(None, content))

    assert [card.image_url for card in content.quick_news] == [
        "https://a.test/banner.png",
        None,
        "https://a.test/other.png",
    ]
    assert changed == 2


def test_image_candidates_order_and_dedupe():
    def item(kind, url, tier=2, title="x"):
        return RawItem(kind=kind, image_url=url, trust_tier=tier, title=title)

    ranked = image_candidates(
        [
            item("repo", "https://r.test/repo.png"),
            item("article", "https://r.test/icon-64x64.png"),
            item("article", "https://r.test/story.jpg", tier=3),
            item("article", "https://r.test/official.jpg", tier=1),
            item("paper", "https://r.test/story.jpg"),
        ],
        "Some story",
    )

    assert ranked == ["https://r.test/official.jpg", "https://r.test/story.jpg", "https://r.test/repo.png"]


# ============================================================
# Review
# ============================================================

def test_structural_checks_flag_gaps_and_duplicates():
    content = _content(
        quick_news=[_news(1), _news(2, refs=[]), _news(1, headline="Same story again")],
        deep_dive=DeepDiveCard(
            story_id=9,
            title="Dive",
            introduction="Intro.",
            sections=[DeepDiveSection(heading="Only", body="One section.")],
            refs=[2],
        ),
    )

    notes = structural_checks(content)
    found = {(note.section, note.note.split(".")[0]) for note in notes}

    assert ("quick_news", "Only 3 Quick News items (aim for 4+)") in found
    assert ("quick_news", "This card cites no source") in found
    assert ("quick_news", "The same story appears in more than one section") in found
    assert ("deep_dive", "The Deep Dive has fewer than two sections") in found
    assert any(note.section == "paper_of_week" and note.severity == "consider" for note in notes)

    # Each duplicated story is reported once.
    assert sum(note.note.startswith("The same story") for note in notes) == 1


def test_structural_checks_quiet_for_complete_issue():
    content = _content(
        quick_news=[_news(i, image_url=f"https://i.test/{i}.png") for i in range(1, 6)],
        deep_dive=DeepDiveCard(
            story_id=9,
            title="Dive",
            introduction="Intro.",
            sections=[DeepDiveSection(heading="A", body="a"), DeepDiveSection(heading="B", body="b")],
            image_url="https://i.test/9.png",
            refs=[2],
        ),
    )

    fixes = [note for note in structural_checks(content) if note.severity == "fix"]

    assert fixes == []


def test_parse_review_clamps_and_normalises():
    score, verdict, notes = parse_review(
        {
            "score": "11",
            "verdict": "  Solid   issue. ",
            "notes": [
                {"section": "Quick News", "item": "GPT-6", "severity": "FIX", "note": "Name the benchmark."},
                {"section": "weather", "severity": "urgent", "note": "Odd section."},
                {"section": "intro", "note": ""},
                "not a dict",
            ]
            + [{"section": "trends", "note": f"n{i}"} for i in range(20)],
        }
    )

    assert score == 10
    assert verdict == "Solid issue."
    assert notes[0].section == "quick_news" and notes[0].severity == "fix" and notes[0].item == "GPT-6"
    assert notes[1].section == "general" and notes[1].severity == "consider"
    assert len(notes) == 8


def test_parse_review_handles_garbage():
    assert parse_review(None) == (None, "", [])
    assert parse_review({"score": "great"})[0] is None


def test_draft_text_includes_source_notes():
    content = _content(quick_news=[_news(1), _news(2)], our_take="Watch the pricing.")

    text = draft_text(content, {1: "OpenAI released GPT-6 via API only."})

    assert "SOURCE NOTE: OpenAI released GPT-6 via API only." in text
    assert text.count("SOURCE NOTE") == 1
    assert "OUR TAKE: Watch the pricing." in text
    assert "\n\n" not in text


def test_public_detail_hides_review():
    content = _content(review=IssueReview(score=7, verdict="Minor edits."))
    issue = NewsletterIssue(
        id=5,
        title=content.title,
        status="published",
        created_at=datetime(2026, 9, 27),
        published_at=datetime(2026, 9, 27),
        raw_content=content.model_dump_json(),
    )

    assert "review" not in _detail(issue).content
    assert _detail(issue, include_review=True).content["review"]["score"] == 7


# ============================================================
# Archive search / scraping helpers
# ============================================================

def test_like_pattern_escapes_wildcards():
    assert _like_pattern("GPT-6") == "%GPT-6%"
    assert _like_pattern("100%_off") == "%100\\%\\_off%"


def test_parse_page_date():
    assert parse_page_date("Sep 25, 2026") == datetime(2026, 9, 25)
    assert parse_page_date("Published Sept 3, 2026 by X") == datetime(2026, 9, 3)
    assert parse_page_date("2026-09-01T10:00:00Z") == datetime(2026, 9, 1, 10)
    assert parse_page_date("no date here") is None


ANTHROPIC_PAGE = """
<main>
  <ul>
    <li>
      <a href="/news/model-hardware-standard">
        <h3>Sep 18, 2026 Announcements Previewing the Model Hardware Standard</h3>
      </a>
      <p>A draft standard for how frontier models are served.</p>
    </li>
    <li>
      <a href="https://www.anthropic.com/news/enzyme"><h3>Science Claude discovers a novel enzyme system</h3></a>
      <time datetime="2026-09-23">Sep 23, 2026</time>
    </li>
    <li><a href="/news/enzyme">Claude discovers a novel enzyme system</a></li>
    <li><a href="/news/all">Read more</a></li>
    <li><a href="https://example.com/news/elsewhere"><h3>Somebody else's news story</h3></a></li>
    <li><a href="/careers"><h3>Join the team at Anthropic</h3></a></li>
  </ul>
</main>
"""


def test_extract_anthropic_records_cleans_titles():
    records = extract_anthropic_records(ANTHROPIC_PAGE)

    assert [record["url"] for record in records] == [
        "https://www.anthropic.com/news/model-hardware-standard",
        "https://www.anthropic.com/news/enzyme",
    ]
    assert records[0]["title"] == "Previewing the Model Hardware Standard"
    assert records[0]["published_at"] == datetime(2026, 9, 18)
    assert records[0]["description"] == "A draft standard for how frontier models are served."
    assert records[1]["title"] == "Claude discovers a novel enzyme system"
    assert records[1]["published_at"] == datetime(2026, 9, 23)
