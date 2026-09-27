import smtplib
from contextlib import contextmanager
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Iterator

from app.core.config import settings
from app.services.email.provider import EmailProvider


class SMTPEmailProvider(EmailProvider):

    def __init__(self) -> None:
        self._connection: smtplib.SMTP_SSL | None = None

    def _connect(self) -> smtplib.SMTP_SSL:
        smtp = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
        )

        smtp.login(
            settings.smtp_username,
            settings.smtp_password,
        )

        return smtp

    @contextmanager
    def batch(self) -> Iterator["SMTPEmailProvider"]:
        """
        Keep one logged-in connection for many sends instead of
        a new TLS handshake + login per subscriber.
        """

        self._connection = self._connect()

        try:
            yield self
        finally:
            try:
                self._connection.quit()
            except smtplib.SMTPException:
                pass

            self._connection = None

    def send(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        idempotency_key: str,
        text_content: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:

        message = EmailMessage()

        message["From"] = settings.email_from
        message["To"] = recipient_email
        message["Subject"] = subject
        message["Message-ID"] = make_msgid(domain="ainow.local")

        for name, value in (headers or {}).items():
            message[name] = value

        message.set_content(
            text_content
            or "Please open this email in an HTML-capable email client."
        )

        message.add_alternative(
            html_content,
            subtype="html",
        )

        if self._connection is not None:
            try:
                self._connection.send_message(message)
                return message["Message-ID"]

            except smtplib.SMTPServerDisconnected:
                # Long batches can outlive the server's idle
                # timeout; reconnect once and carry on.
                self._connection = self._connect()
                self._connection.send_message(message)
                return message["Message-ID"]

        with self._connect() as smtp:
            smtp.send_message(message)

        return message["Message-ID"]
