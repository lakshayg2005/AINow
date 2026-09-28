from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Iterator


class EmailProvider(ABC):

    @abstractmethod
    def send(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        idempotency_key: str,
        text_content: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        """
        Send an email.

        Returns:
            Provider message ID.
        """
        raise NotImplementedError

    @contextmanager
    def batch(self) -> Iterator["EmailProvider"]:
        """
        Group many sends (e.g. one per subscriber). Providers
        that hold connections reuse one for the whole batch.
        """
        yield self


def get_email_provider() -> "EmailProvider":
    """
    Brevo when BREVO_API_KEY is set (more reliable at scale,
    doesn't touch a personal inbox); Gmail SMTP otherwise, so
    delivery works out of the box in local development.
    """

    from app.core.config import settings

    if settings.brevo_api_key:
        from app.services.email.brevo_provider import BrevoEmailProvider

        return BrevoEmailProvider()

    from app.services.email.smtp_provider import SMTPEmailProvider

    return SMTPEmailProvider()
