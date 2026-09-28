"""
Sends via Brevo's transactional email API instead of SMTP.

Used automatically when BREVO_API_KEY is set (see
get_email_provider in provider.py); Gmail SMTP remains the
fallback for anyone who hasn't set it up. Brevo's free tier
(300 emails/day) is more reliable at scale than personal SMTP
and doesn't risk that Gmail account being flagged.

The sender address must be a verified sender in Brevo (Senders,
Domains & Dedicated IPs -> Senders) before it can send mail.
"""

from __future__ import annotations

from contextlib import contextmanager
from email.utils import parseaddr
from typing import Iterator

import httpx

from app.core.config import settings
from app.services.email.provider import EmailProvider


API_URL = "https://api.brevo.com/v3/smtp/email"


def _error_detail(
    response: httpx.Response,
) -> str:
    try:
        return response.json().get("message") or response.text
    except ValueError:
        return response.text[:500]


class BrevoEmailProvider(EmailProvider):

    def __init__(self) -> None:
        self._client: httpx.Client | None = None

        name, email = parseaddr(settings.email_from)
        self._sender: dict[str, str] = {"email": email}

        if name:
            self._sender["name"] = name

    def _headers(self) -> dict[str, str]:
        return {
            "api-key": settings.brevo_api_key or "",
            "accept": "application/json",
        }

    @contextmanager
    def batch(self) -> Iterator["BrevoEmailProvider"]:
        """One keep-alive HTTP connection for the whole batch."""

        self._client = httpx.Client(headers=self._headers(), timeout=20.0)

        try:
            yield self
        finally:
            self._client.close()
            self._client = None

    def send(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        idempotency_key: str,
        text_content: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        payload: dict = {
            "sender": self._sender,
            "to": [{"email": recipient_email}],
            "subject": subject,
            "htmlContent": html_content,
        }

        if text_content:
            payload["textContent"] = text_content

        if headers:
            # List-Unsubscribe etc; passed through as-is.
            payload["headers"] = headers

        owned_client = self._client is None
        client = self._client or httpx.Client(headers=self._headers(), timeout=20.0)

        try:
            response = client.post(API_URL, json=payload)
        finally:
            if owned_client:
                client.close()

        if response.is_error:
            raise RuntimeError(
                f"Brevo error {response.status_code}: {_error_detail(response)}"
            )

        return response.json().get("messageId") or idempotency_key
