"""
Live SMTP smoke test. Skipped by default (it sends a real
email and needs real credentials); run explicitly with:

    RUN_SMTP_LIVE_TEST=1 pytest tests/test_email.py -q
"""

import os

import pytest

from app.services.email.smtp_provider import SMTPEmailProvider


@pytest.mark.skipif(
    not os.environ.get("RUN_SMTP_LIVE_TEST"),
    reason="Sends a real email; set RUN_SMTP_LIVE_TEST=1 to run.",
)
def test_smtp_sends_real_email():
    provider = SMTPEmailProvider()

    message_id = provider.send(
        recipient_email=os.environ.get("SMTP_TEST_RECIPIENT", "lakshayg@iitbhilai.ac.in"),
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

    assert message_id
