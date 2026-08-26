from datetime import datetime, timedelta, timezone
import time
import hashlib
import secrets

from sqlalchemy.orm import Session

from app.db.models import EmailVerification, User
from app.services.email.smtp_provider import SMTPEmailProvider


VERIFICATION_EXPIRE_MINUTES = 30
RESEND_COOLDOWN_SECONDS = 60

_resend_cooldowns: dict[str, float] = {}


def hash_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def create_verification_token(
    db: Session,
    user: User,
) -> str:

    # Invalidate any previous unused tokens.
    existing_tokens = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.user_id == user.id,
            EmailVerification.verified_at.is_(None),
        )
        .all()
    )

    for verification in existing_tokens:
        verification.verified_at = datetime.utcnow()

    raw_token = secrets.token_urlsafe(32)

    verification = EmailVerification(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=(
            datetime.utcnow()
            + timedelta(
                minutes=VERIFICATION_EXPIRE_MINUTES
            )
        ),
    )

    db.add(verification)
    db.commit()

    return raw_token


def send_verification_email(
    user: User,
    token: str,
):
    provider = SMTPEmailProvider()

    # React frontend route we'll create later.
    verification_url = (
        "http://localhost:5173/verify-email"
        f"?token={token}"
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <body>
        <div style="
            max-width:600px;
            margin:40px auto;
            font-family:Arial,Helvetica,sans-serif;
            line-height:1.6;
            color:#111;
        ">

            <h1>AINow</h1>

            <h2>Verify your email</h2>

            <p>
                Hi {user.name},
            </p>

            <p>
                Thanks for creating your AINow account.
                Please verify your email address to
                activate your account.
            </p>

            <p>
                <a
                    href="{verification_url}"
                    style="
                        display:inline-block;
                        padding:12px 20px;
                        background:#000;
                        color:#fff;
                        text-decoration:none;
                        border-radius:8px;
                    "
                >
                    Verify Email
                </a>
            </p>

            <p>
                This link expires in
                {VERIFICATION_EXPIRE_MINUTES} minutes.
            </p>

            <p>
                If you did not create this account,
                you can ignore this email.
            </p>

            <p>
                — AINow
            </p>

        </div>
    </body>
    </html>
    """

    provider.send(
        recipient_email=user.email,
        subject="Verify your AINow email",
        html_content=html,
        idempotency_key=(
            f"email-verification-{user.id}-{token}"
        ),
    )

# Below 2 functions ensures the /resend-verification link is not clicked many times (one after another continously by using Cool down time).
# Importanat :Altough we are cureently implementing In-memory Cool-down ,later when we deploy,all server instances will ahve thier own dictionary so that time coll-down time will be implemented on Redis.

def check_resend_cooldown(
    email: str,
) -> int:
    key = email.strip().lower()

    now = time.time()

    last_sent = _resend_cooldowns.get(key)

    if last_sent is None:
        return 0

    elapsed = now - last_sent

    remaining = (
        RESEND_COOLDOWN_SECONDS
        - int(elapsed)
    )

    return max(
        remaining,
        0,
    )


def mark_resend_sent(
    email: str,
):
    _resend_cooldowns[
        email.strip().lower()
    ] = time.time()