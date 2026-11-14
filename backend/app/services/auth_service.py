"""
Authentication service: user registration, login, password reset, email verification.
"""

import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from backend.app.models.password_reset import PasswordResetToken
from backend.app.models.email_verification import EmailVerificationToken
from backend.app.core.security import (
    hash_password,
    verify_password,
    generate_secure_token,
    hash_token,
)
from backend.app.config import settings


async def register_user(
    db: AsyncSession, email: str, password: str, full_name: str
) -> User:
    """
    Register a new user with email and password.
    Raises HTTPException 409 if email already exists.
    """
    email_normalized = email.lower().strip()

    # Check for duplicate email
    stmt = select(User).where(User.email_normalized == email_normalized)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Validate password length
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters",
        )

    # Create user
    password_hash = hash_password(password)
    user = User(
        email=email,
        email_normalized=email_normalized,
        password_hash=password_hash,
        full_name=full_name,
        is_email_verified=False,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """
    Authenticate a user by email and password.
    Returns User if valid, None if invalid credentials or inactive account.
    """
    email_normalized = email.lower().strip()

    stmt = select(User).where(User.email_normalized == email_normalized)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    if not user.is_active:
        return None

    return user


async def create_password_reset_token(db: AsyncSession, email: str) -> str | None:
    """
    Create a password reset token for a user by email.
    Returns the plain token if user found, None otherwise (non-enumeration).
    """
    email_normalized = email.lower().strip()

    stmt = select(User).where(User.email_normalized == email_normalized)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return None

    # Generate token
    plain_token = generate_secure_token(32)
    token_hash_value = hash_token(plain_token)
    expires_at = datetime.utcnow() + timedelta(
        minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES
    )

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash_value,
        expires_at=expires_at,
        used=False,
    )
    db.add(reset_token)
    await db.flush()

    return plain_token


async def verify_reset_token(db: AsyncSession, token: str) -> User | None:
    """
    Verify a password reset token and return the associated user.
    Returns None if token is invalid, expired, or already used.
    """
    token_hash_value = hash_token(token)

    stmt = select(PasswordResetToken).where(
        PasswordResetToken.token_hash == token_hash_value
    )
    result = await db.execute(stmt)
    reset_token = result.scalar_one_or_none()

    if not reset_token:
        return None

    if reset_token.used:
        return None

    if reset_token.expires_at < datetime.utcnow():
        return None

    # Load user
    stmt = select(User).where(User.id == reset_token.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    return user


async def reset_password(db: AsyncSession, token: str, new_password: str) -> bool:
    """
    Reset a user's password using a valid reset token.
    Returns True on success, False if token is invalid.
    """
    user = await verify_reset_token(db, token)

    if not user:
        return False

    # Validate new password length
    if len(new_password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters",
        )

    # Update password
    user.password_hash = hash_password(new_password)

    # Mark token as used
    token_hash_value = hash_token(token)
    stmt = select(PasswordResetToken).where(
        PasswordResetToken.token_hash == token_hash_value
    )
    result = await db.execute(stmt)
    reset_token = result.scalar_one()
    reset_token.used = True

    await db.flush()

    return True


async def create_verification_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    """
    Create an email verification token for a user.
    Returns the plain token to be sent in the verification email.
    """
    plain_token = generate_secure_token(32)
    token_hash_value = hash_token(plain_token)
    expires_at = datetime.utcnow() + timedelta(
        hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS
    )

    verification_token = EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash_value,
        expires_at=expires_at,
        used=False,
    )
    db.add(verification_token)
    await db.flush()

    return plain_token


async def verify_email(db: AsyncSession, token: str) -> bool:
    """
    Verify a user's email using a verification token.
    Returns True on success, False if token is invalid, expired, or already used.
    """
    token_hash_value = hash_token(token)

    stmt = select(EmailVerificationToken).where(
        EmailVerificationToken.token_hash == token_hash_value
    )
    result = await db.execute(stmt)
    verification_token = result.scalar_one_or_none()

    if not verification_token:
        return False

    if verification_token.used:
        return False

    if verification_token.expires_at < datetime.utcnow():
        return False

    # Mark token as used and verify user email
    verification_token.used = True

    stmt = select(User).where(User.id == verification_token.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one()
    user.is_email_verified = True

    await db.flush()

    return True
