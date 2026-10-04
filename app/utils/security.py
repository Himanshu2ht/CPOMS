"""Password policy + login rate limiting helpers."""
import re
import time
from collections import defaultdict

_attempts: dict[str, list[float]] = defaultdict(list)


def password_errors(password: str) -> list[str]:
    """Return human-readable policy violations (empty = strong enough)."""
    errs = []
    if len(password or "") < 8:
        errs.append("at least 8 characters")
    if not re.search(r"[A-Z]", password or ""):
        errs.append("one UPPERCASE letter")
    if not re.search(r"[a-z]", password or ""):
        errs.append("one lowercase letter")
    if not re.search(r"\d", password or ""):
        errs.append("one digit")
    if not re.search(r"[^A-Za-z0-9]", password or ""):
        errs.append("one special character (e.g. @#!)")
    return errs


def is_rate_limited(key: str, max_attempts: int, window_seconds: int) -> bool:
    now = time.time()
    hits = [t for t in _attempts[key] if now - t < window_seconds]
    _attempts[key] = hits
    return len(hits) >= max_attempts


def record_attempt(key: str) -> None:
    _attempts[key].append(time.time())


def clear_attempts(key: str) -> None:
    _attempts.pop(key, None)
