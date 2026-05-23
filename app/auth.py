import time
from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.config import settings

ph = PasswordHasher()

# In-memory rate limit store: {user_id: {"attempts": int, "locked_until": float}}
_rate_limit_store: dict = {}


def hash_pin(pin: str) -> str:
    """Hash a PIN using argon2."""
    return ph.hash(pin)


def verify_pin(pin_hash: str, pin: str) -> bool:
    """Verify a PIN against its hash. Returns True if valid."""
    try:
        return ph.verify(pin_hash, pin)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def check_rate_limit(user_id: int) -> tuple[bool, float]:
    """
    Check if a user is rate limited.
    Returns (is_limited, seconds_remaining).
    """
    record = _rate_limit_store.get(user_id)
    if record is None:
        return False, 0.0

    locked_until = record.get("locked_until", 0)
    if locked_until > time.time():
        return True, locked_until - time.time()

    return False, 0.0


def record_failed_attempt(user_id: int) -> bool:
    """
    Record a failed login attempt.
    Returns True if user is now locked out.
    """
    record = _rate_limit_store.setdefault(user_id, {"attempts": 0, "locked_until": 0})

    # If current lockout has expired, reset
    if record["locked_until"] <= time.time():
        record["attempts"] = 0
        record["locked_until"] = 0

    record["attempts"] += 1
    if record["attempts"] >= settings.RATE_LIMIT_MAX_ATTEMPTS:
        record["locked_until"] = time.time() + settings.RATE_LIMIT_LOCKOUT_SECONDS
        return True

    return False


def reset_rate_limit(user_id: int) -> None:
    """Reset rate limit record for a user after successful login."""
    _rate_limit_store.pop(user_id, None)
