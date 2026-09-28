from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# def generate_verification_token() -> str:
#     return secrets.token_urlsafe(32)


# def hash_verification_token(token: str) -> str:
#     return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": str(user_id),
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_service_token(
    user_id: int,
    days: int = 400,
) -> str:
    """
    A long-lived token for server-to-server calls (e.g. a
    scheduled workflow triggering /admin/jobs/*), rather than a
    human session. Same shape as create_access_token — get_
    current_user accepts it and get_current_admin still checks
    is_admin on every request — just with a longer expiry.

    To revoke one, remove admin rights from the account or
    rotate JWT_SECRET_KEY (which invalidates every token).
    """

    expire = datetime.now(timezone.utc) + timedelta(days=days)

    payload = {
        "sub": str(user_id),
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise ValueError("Invalid or expired token")

# Unsubscribe links must work without logging in and never
# expire (people unsubscribe from old emails), so they carry
# a signed, purpose-scoped token instead of a session.
UNSUBSCRIBE_PURPOSE = "unsubscribe"


def create_unsubscribe_token(user_id: int) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "purpose": UNSUBSCRIBE_PURPOSE,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_unsubscribe_token(token: str) -> int:
    payload = decode_access_token(token)

    if payload.get("purpose") != UNSUBSCRIBE_PURPOSE:
        raise ValueError("Not an unsubscribe token")

    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid unsubscribe token")
