"""
Offline tests for delivery, unsubscribe tokens, admin access
and scheduling (no network, no DB).

    pytest tests/test_delivery.py
"""

from datetime import datetime

import pytest
from fastapi import HTTPException

from app.core.dependencies import get_current_admin
from app.core.security import (
    create_access_token,
    create_unsubscribe_token,
    decode_access_token,
    decode_unsubscribe_token,
)
from app.db.models import NewsletterIssue, User
from app.scheduler import compose_due, ingest_due, last_compose_slot
from app.schemas.issue import IssueContent, QuickNewsCard, SourceRef
from app.services.delivery import build_email, unsubscribe_urls
from app.services.email.provider import EmailProvider
from app.services.issue_email import render_issue_text


def _user(**overrides) -> User:
    values = {"id": 7, "email": "reader@example.com", "name": "Reader", "is_admin": False}
    values.update(overrides)
    return User(**values)


def _content() -> IssueContent:
    return IssueContent(
        title="AINow Weekly — September 27, 2026",
        headline="Opus 5.5 and GPT-6 open a price war",
        intro="Two frontier launches.",
        issue_date=datetime(2026, 9, 27),
        quick_news=[
            QuickNewsCard(
                story_id=1,
                headline="Lab ships Model X",
                summary="It is fast.",
                why_it_matters="Cheaper agents.",
                is_update=True,
                refs=[1],
            )
        ],
        sources=[SourceRef(id=1, title="Launch", url="https://lab.example/post", source_name="Lab")],
    )


# ============================================================
# Unsubscribe tokens
# ============================================================

def test_unsubscribe_token_roundtrip():
    token = create_unsubscribe_token(42)
    assert decode_unsubscribe_token(token) == 42


def test_access_token_is_not_an_unsubscribe_token():
    with pytest.raises(ValueError):
        decode_unsubscribe_token(create_access_token(42))


def test_unsubscribe_token_cannot_be_used_as_login():
    # get_current_user rejects purpose-scoped tokens; the
    # payload carries the marker it checks.
    payload = decode_access_token(create_unsubscribe_token(42))
    assert payload["purpose"] == "unsubscribe"
    assert "exp" not in payload  # links in old emails keep working


def test_tampered_token_rejected():
    token = create_unsubscribe_token(42)
    with pytest.raises(ValueError):
        decode_unsubscribe_token(token[:-2] + ("aa" if token[-2:] != "aa" else "bb"))


# ============================================================
# Admin access
# ============================================================

def test_admin_dependency():
    admin = _user(is_admin=True)
    assert get_current_admin(admin) is admin

    with pytest.raises(HTTPException) as error:
        get_current_admin(_user(is_admin=False))

    assert error.value.status_code == 403


# ============================================================
# Emails
# ============================================================

def test_unsubscribe_urls_point_to_page_and_api():
    page, one_click = unsubscribe_urls(_user())

    assert "/unsubscribe?token=" in page
    assert "/subscriptions/unsubscribe?token=" in one_click
    assert page.split("token=")[1] == one_click.split("token=")[1]


def test_build_email_v2_has_text_headers_and_personal_link():
    issue = NewsletterIssue(id=10, title="AINow Weekly", raw_content=_content().model_dump_json(indent=2))
    email = build_email(issue, _user())

    assert email.subject == "AINow — Opus 5.5 and GPT-6 open a price war"
    assert email.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert email.headers["List-Unsubscribe"].startswith("<http")
    assert "Unsubscribe</a>" in email.html
    assert "UPDATE: Lab ships Model X" in email.text
    assert "Unsubscribe: " in email.text


def test_build_email_legacy_appends_unsubscribe_footer():
    issue = NewsletterIssue(id=4, title="Old issue", raw_content='{"quick_news": []}', html_content="<html><body><p>Hi</p></body></html>")
    email = build_email(issue, _user())

    assert email.text is None
    assert email.html.index("Unsubscribe") < email.html.index("</body>")


def test_render_issue_text_sections():
    text = render_issue_text(_content(), "https://ainow.example/newsletters/10")

    assert text.startswith("AINow — September 27, 2026")
    assert "QUICK NEWS" in text
    assert "[1] Launch — https://lab.example/post" in text


def test_default_provider_batch_is_a_noop_context():
    class Recording(EmailProvider):
        def __init__(self):
            self.sent = []

        def send(self, recipient_email, subject, html_content, idempotency_key, text_content=None, headers=None):
            self.sent.append(recipient_email)
            return "id"

    provider = Recording()

    with provider.batch() as batch:
        batch.send("a@example.com", "s", "<p>h</p>", "k")

    assert provider.sent == ["a@example.com"]


# ============================================================
# Scheduler
# ============================================================

def test_last_compose_slot():
    # Sunday 06:00 UTC schedule (weekday 6).
    sunday_morning = datetime(2026, 9, 27, 7, 30)   # a Sunday
    saturday = datetime(2026, 9, 26, 12, 0)
    sunday_early = datetime(2026, 9, 27, 5, 0)

    assert last_compose_slot(sunday_morning, 6, 6) == datetime(2026, 9, 27, 6, 0)
    assert last_compose_slot(saturday, 6, 6) == datetime(2026, 9, 20, 6, 0)
    assert last_compose_slot(sunday_early, 6, 6) == datetime(2026, 9, 20, 6, 0)


def test_compose_due_once_per_week():
    now = datetime(2026, 9, 27, 7, 0)

    assert compose_due(now, None, 6, 6)
    assert compose_due(now, datetime(2026, 9, 21, 6, 5), 6, 6)      # last week's issue
    assert not compose_due(now, datetime(2026, 9, 27, 6, 1), 6, 6)  # already done today


def test_ingest_due():
    now = datetime(2026, 9, 27, 12, 0)

    assert ingest_due(now, None, 6)
    assert ingest_due(now, datetime(2026, 9, 27, 5, 59), 6)
    assert not ingest_due(now, datetime(2026, 9, 27, 7, 0), 6)
