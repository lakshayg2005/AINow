import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.services.email.provider import EmailProvider


class SMTPEmailProvider(EmailProvider):

    def send(
        self,
        recipient_email: str,
        subject: str,
        html_content: str,
        idempotency_key: str,
    ) -> str:

        message = EmailMessage()

        message["From"] = settings.email_from
        message["To"] = recipient_email
        message["Subject"] = subject

        message.set_content(
            "Please open this email in an HTML-capable email client."
        )

        message.add_alternative(
            html_content,
            subtype="html",
        )

        with smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
        ) as smtp:

            smtp.login(
                settings.smtp_username,
                settings.smtp_password,
            )

            smtp.send_message(
                message
            )

        return "smtp-sent"