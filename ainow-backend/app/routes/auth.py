from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.db.models import EmailVerification, User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    VerifyEmailResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
)
from app.core.dependencies import get_current_user
from app.services.email_verification import (
    create_verification_token,
    send_verification_email,
    hash_token,
    check_resend_cooldown,
    mark_resend_sent,    
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hash_password(
            user_data.password
        ),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # -----------------------------------------
    # Create ONE verification token
    # -----------------------------------------

    token = create_verification_token(
        db=db,
        user=new_user,
    )

    # -----------------------------------------
    # Send verification email
    # -----------------------------------------

    send_verification_email(
        user=new_user,
        token=token,
    )

    return {
        "message": (
            "Account created successfully. "
            "Please verify your email."
        ),
        "email": new_user.email,
    }

@router.get(
    "/verify-email",
    response_model=VerifyEmailResponse,
)
def verify_email(
    token: str,
    db: Session = Depends(get_db),
):
    print("\n========== EMAIL VERIFICATION ==========")
    print("Received token:", repr(token))

    token_hash = hash_token(token)

    print("Calculated hash:", token_hash)

    verification = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.token_hash == token_hash
        )
        .order_by(
            EmailVerification.id.desc()
        )
        .first()
    )

    if not verification:
        print("RESULT: TOKEN NOT FOUND")

        raise HTTPException(
            status_code=400,
            detail="Invalid verification token.",
        )

    print(
        "Verification ID:",
        verification.id,
    )

    print(
        "User ID:",
        verification.user_id,
    )

    print(
        "Expires:",
        verification.expires_at,
    )

    print(
        "Verified At:",
        verification.verified_at,
    )

    user = (
        db.query(User)
        .filter(
            User.id == verification.user_id
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        )

    print(
        "User email:",
        user.email,
    )

    print(
        "User verified:",
        user.is_email_verified,
    )

    if verification.verified_at:
        if user.is_email_verified:
            print(
                "RESULT: ALREADY VERIFIED"
            )

            return {
                "message": "Email is already verified.",
                "email": user.email,
            }

        raise HTTPException(
            status_code=400,
            detail="Verification token has already been used.",
        )

    now = datetime.utcnow()

    if verification.expires_at < now:
        print("RESULT: TOKEN EXPIRED")

        raise HTTPException(
            status_code=400,
            detail="Verification token has expired.",
        )

    user.is_email_verified = True
    verification.verified_at = now

    db.commit()

    print(
        "RESULT: VERIFICATION SUCCESS"
    )

    return {
        "message": "Email verified successfully.",
        "email": user.email,
    }

@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    user_data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == user_data.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in",
        )

    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": "Login successful",
    }

@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
)
def resend_verification(
    user_data: ResendVerificationRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(
            User.email == user_data.email
        )
        .first()
    )

    # Don't reveal whether the account exists.
    if not user:
        return {
            "message": (
                "If an account exists for this email, "
                "a verification email has been sent."
            )
        }

    if user.is_email_verified:
        return {
            "message": "Email is already verified."
        }

    # -----------------------------------------
    # Cooldown
    # -----------------------------------------

    remaining = check_resend_cooldown(
        user.email
    )

    if remaining > 0:
        return {
            "message": (
                "Please wait "
                f"{remaining} seconds before "
                "requesting another verification email."
            )
        }

    # -----------------------------------------
    # Generate new token
    # -----------------------------------------

    token = create_verification_token(
        db=db,
        user=user,
    )

    # -----------------------------------------
    # Send email
    # -----------------------------------------

    send_verification_email(
        user=user,
        token=token,
    )

    mark_resend_sent(
        user.email
    )

    return {
        "message": (
            "Email resent! Don't forget to "
            "check your Spam folder and verify "
            "that the correct email was entered."
        )
    }

# @router.get(
#     "/me",
#     response_model=CurrentUserResponse,
# )
# def get_me(
#     current_user: User = Depends(get_current_user),
# ):
#     return current_user

