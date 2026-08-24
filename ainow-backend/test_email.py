from app.services.email.smtp_provider import (
    SMTPEmailProvider,
)


provider = SMTPEmailProvider()

message_id = provider.send(
    recipient_email="lakshayg@iitbhilai.ac.in",
    subject="AINow Test Email",
    html_content="""
    <!DOCTYPE html>
    <html>
        <body>
            <h1>AINow</h1>
            <p>Real SMTP delivery is working.</p>
        </body>
    </html>
    """,
    idempotency_key="ainow-smtp-test-001",
)

print(
    "Message ID:",
    message_id,
)