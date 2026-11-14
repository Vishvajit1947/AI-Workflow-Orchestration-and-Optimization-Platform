"""
Authentication API endpoints.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    MessageResponse,
    AuthResponse,
)
from backend.app.services import auth_service, session_service, email_service
from backend.app.core.dependencies import get_current_user, get_current_active_user
from backend.app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit("10/minute")
async def register(
    request: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    try:
        # Create user
        user = await auth_service.register_user(
            db, request.email, request.password, request.full_name
        )

        # Create verification token and send email (non-blocking)
        verification_token = await auth_service.create_verification_token(db, user.id)
        await email_service.send_verification_email(
            user.email, user.full_name, verification_token
        )

        await db.commit()

        return AuthResponse(
            user=UserResponse.model_validate(user),
            message="Please check your email to verify your account",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=UserResponse)
@limiter.limit("10/minute")
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and create session."""
    user = await auth_service.authenticate_user(db, request.email, request.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create session
    expires_in_days = 30 if request.remember_me else 7
    _, plain_token = await session_service.create_session(
        db, user.id, expires_in_days=expires_in_days
    )

    await db.commit()

    # Set httponly cookie
    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="session_token",
        value=plain_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=expires_in_days * 86400,
        path="/",
    )

    return UserResponse.model_validate(user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    session_token: str = Cookie(None, alias="session_token"),
    db: AsyncSession = Depends(get_db),
):
    """Logout user by revoking session."""
    from fastapi import Cookie

    if session_token:
        await session_service.revoke_session(db, session_token)
        await db.commit()

    # Clear cookie
    response.delete_cookie(key="session_token", path="/")

    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    """Get current authenticated user information."""
    return UserResponse.model_validate(current_user)


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("10/minute")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset email (non-enumeration response)."""
    # Create reset token if user exists
    token = await auth_service.create_password_reset_token(db, request.email)

    if token:
        # Send reset email
        from sqlalchemy import select

        stmt = select(User).where(User.email_normalized == request.email.lower().strip())
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            await email_service.send_password_reset_email(
                user.email, user.full_name, token
            )

    await db.commit()

    # Always return same message (non-enumeration)
    return MessageResponse(
        message="If an account exists for this email, password reset instructions have been sent"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a valid reset token."""
    success = await auth_service.reset_password(db, request.token, request.new_password)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token",
        )

    await db.commit()

    return MessageResponse(message="Password reset successfully")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    request: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify user email using verification token."""
    success = await auth_service.verify_email(db, request.token)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token",
        )

    await db.commit()

    return MessageResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit("10/minute")
async def resend_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resend email verification link."""
    if current_user.is_email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    # Create new verification token
    token = await auth_service.create_verification_token(db, current_user.id)
    await email_service.send_verification_email(
        current_user.email, current_user.full_name, token
    )

    await db.commit()

    return MessageResponse(message="Verification email sent")
