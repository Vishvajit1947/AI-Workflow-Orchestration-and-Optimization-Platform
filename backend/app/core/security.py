"""
Security utilities: password hashing, token generation, and secure comparison.
"""

import hashlib
import hmac
import secrets

from passlib.context import CryptContext


# Argon2 password hashing context
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its Argon2 hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a URL-safe random token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256 for database storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(token: str, token_hash: str) -> bool:
    """Timing-safe comparison of token against its hash."""
    computed_hash = hash_token(token)
    return hmac.compare_digest(computed_hash, token_hash)
