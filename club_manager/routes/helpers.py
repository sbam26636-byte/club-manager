"""Small helpers shared by several route files."""
from datetime import date


def to_int(text):
    """'12' -> 12, anything else -> None."""
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def valid_date(text):
    """True if text looks like 2026-03-10 and is a real calendar date."""
    try:
        date.fromisoformat(text)
        return True
    except (TypeError, ValueError):
        return False
