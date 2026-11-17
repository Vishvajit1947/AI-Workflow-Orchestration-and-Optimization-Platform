"""
FastAPI dependencies for authentication.
"""

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.services import session_service


async def get_current_user(
    session: str = Cookie(None, alias="session_token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from session cookie.
    Raises 401 if not authenticated.
    """
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await session_service.validate_session(db, session)

    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current authenticated and active user.
    Raises 403 if user is inactive.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")

    return current_user

