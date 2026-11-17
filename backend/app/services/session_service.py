"""
Session service: manage user authentication sessions.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.session import Session
from backend.app.models.user import User
from backend.app.core.security import generate_secure_token, hash_token, verify_token_hash


async def create_session(
    db: AsyncSession, user_id: uuid.UUID, expires_in_days: int = 7
) -> tuple[Session, str]:
    """
    Create a new session for the user.
    Returns (Session, plain_token) where plain_token should be set in the cookie.
    """
    plain_token = generate_secure_token(32)
    token_hash = hash_token(plain_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

    session = Session(
        user_id=user_id,
        session_token=token_hash,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    return session, plain_token


async def validate_session(db: AsyncSession, session_token: str) -> User | None:
    """
    Validate a session token and return the associated active user.
    Updates last_used_at timestamp.
    Returns None if session is invalid, expired, or user is inactive.
    """
    token_hash = hash_token(session_token)

    stmt = select(Session).where(Session.session_token == token_hash)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        return None

    # Check expiration
    if session.expires_at < datetime.now(timezone.utc):
        return None

    # Update last_used_at
    session.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    # Load user
    stmt = select(User).where(User.id == session.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        return None

    return user


async def refresh_session(
    db: AsyncSession, session_token: str, expires_in_days: int = 7
) -> Session | None:
    """
    Extend the expiration of an existing session.
    Returns the updated Session or None if invalid.
    """
    token_hash = hash_token(session_token)

    stmt = select(Session).where(Session.session_token == token_hash)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        return None

    session.expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    await db.flush()
    await db.refresh(session)

    return session


async def revoke_session(db: AsyncSession, session_token: str) -> bool:
    """
    Revoke (delete) a session by token.
    Returns True if a session was deleted, False otherwise.
    """
    token_hash = hash_token(session_token)

    stmt = delete(Session).where(Session.session_token == token_hash)
    result = await db.execute(stmt)
    await db.flush()

    return result.rowcount > 0


async def revoke_all_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
    """
    Revoke (delete) all sessions for a user.
    Returns the number of sessions deleted.
    """
    stmt = delete(Session).where(Session.user_id == user_id)
    result = await db.execute(stmt)
    await db.flush()

    return result.rowcount
