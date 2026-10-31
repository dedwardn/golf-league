"""The one read of the clock, on its own so that reading it imports no database."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Now in naive UTC, as the domain and the store hold time."""
    return datetime.now(UTC).replace(tzinfo=None)
