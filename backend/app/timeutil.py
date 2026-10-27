from datetime import datetime, timezone


def aware(dt: datetime) -> datetime:
    """Treat a naive datetime (SQLite drops time zones) as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
