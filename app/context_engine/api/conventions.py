from __future__ import annotations

from datetime import UTC, datetime


def format_utc_timestamp(value: datetime) -> str:
    """Serialize a datetime as a whole-second RFC 3339 UTC timestamp."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
