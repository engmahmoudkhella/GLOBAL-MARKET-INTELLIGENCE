"""Password hashing (Argon2id) and opaque session/CSRF tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2id with library-recommended parameters

MIN_PASSWORD_LENGTH = 12


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# A fixed dummy hash so that login for an unknown email costs the same as for a known one.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))


def burn_verify_time(password: str) -> None:
    verify_password(_DUMMY_HASH, password)


def new_token() -> str:
    """256-bit URL-safe random token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Session tokens are stored hashed so a DB leak does not leak live sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
