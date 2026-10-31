"""What the app takes from the world rather than a use case: the clock and the database file."""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine

from league.store.schema import migrate, open_engine


def utc_now() -> datetime:
    """The one read of the clock: now in naive UTC, as the domain and the store hold time."""
    return datetime.now(UTC).replace(tzinfo=None)


def open_database(path: Path) -> Engine:
    """The engine on that file, brought to the latest migration."""
    engine = open_engine(path)
    with engine.begin() as connection:
        migrate(connection)
    return engine
