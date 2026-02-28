import re
from datetime import datetime, timezone


def normalize_phone(raw: str) -> str | None:
    """
    Normalize any Uzbek phone to +998XXXXXXXXX.
    Accepts: 901234567 / 998901234567 / +998901234567 / 90 123 45 67
    Returns normalized string or None if invalid.
    """
    digits = re.sub(r"[^\d]", "", raw)

    VALID_PREFIXES = {
        "90","91","93","94","95","97","98","99",
        "33","50","55","70","71","77","88"
    }

    def ok(nine: str) -> bool:
        return nine[:2] in VALID_PREFIXES

    if len(digits) == 9 and ok(digits):
        return f"+998{digits}"
    if len(digits) == 10 and digits.startswith("0") and ok(digits[1:]):
        return f"+998{digits[1:]}"
    if len(digits) == 12 and digits.startswith("998") and ok(digits[3:]):
        return f"+{digits}"

    return None


def validate_phone(phone: str) -> bool:
    return normalize_phone(phone) is not None


def format_phone(phone: str) -> str:
    return normalize_phone(phone) or phone.strip()


def validate_positive_int(value: str) -> int | None:
    try:
        v = int(value.strip())
        return v if v > 0 else None
    except (ValueError, TypeError, AttributeError):
        return None


def validate_positive_float(value: str) -> float | None:
    try:
        v = float(value.strip().replace(",", ".").replace(" ", ""))
        return v if v > 0 else None
    except (ValueError, TypeError, AttributeError):
        return None


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def days_since(date_val) -> int:
    """Works with both datetime objects (asyncpg) and ISO strings."""
    try:
        if isinstance(date_val, str):
            dt = datetime.fromisoformat(date_val)
        else:
            dt = date_val  # asyncpg returns datetime directly
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(delta.days, 1)
    except Exception:
        return 1


def format_date(date_val) -> str:
    """Works with both datetime objects (asyncpg) and ISO strings."""
    try:
        if isinstance(date_val, str):
            dt = datetime.fromisoformat(date_val)
        else:
            dt = date_val
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(date_val)


def format_number(n) -> str:
    try:
        return f"{float(n):,.0f}".replace(",", " ")
    except (ValueError, TypeError):
        return str(n)
