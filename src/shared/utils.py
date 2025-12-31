from datetime import datetime, timezone


def get_utc_now() -> datetime:
    """Return a timezone-aware UTC datetime for consistent timestamps."""
    return datetime.now(timezone.utc)
