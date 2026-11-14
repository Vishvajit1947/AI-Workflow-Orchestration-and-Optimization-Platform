"""
Pydantic schemas for authentication requests and responses.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.app.config import settings


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=settings.PASSWORD_MIN_LENGTH)
    full_name: str = Field(..., min_length=1, max_length=255)
    terms_accepted: bool

    @field_validator("terms_accepted")
    @classmethod
    def validate_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the terms and conditions")
        return v


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str
    remember_me: bool = False


class UserResponse(BaseModel):
    """User response schema."""

    id: uuid.UUID
    email: str
    full_name: str
    is_email_verified: bool
    is_active: bool
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request."""

    token: str
    new_password: str = Field(..., min_length=settings.PASSWORD_MIN_LENGTH)


class VerifyEmailRequest(BaseModel):
    """Verify email request."""

    token: str


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class AuthResponse(BaseModel):
    """Authentication response with user and optional message."""

    user: Optional[UserResponse] = None
    message: Optional[str] = None
