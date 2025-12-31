from datetime import datetime, timezone


def get_utc_now() -> datetime:
    """Return a timezone-aware UTC datetime for consistent timestamps."""
    return datetime.now(timezone.utc)


def ensure_utc_datetime(value: object) -> datetime:
    """
    Normalize input into an aware UTC datetime.

    Accepts:
    - None: returns current UTC
    - datetime: attaches/ converts to UTC
    - ISO string: parses and converts to UTC
    """
    if value is None:
        return get_utc_now()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except Exception:
            return get_utc_now()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return get_utc_now()
