"""What the app takes from the world rather than a use case: the database file."""

from pathlib import Path

from sqlalchemy import Engine

from league.store.schema import migrate, open_engine


def open_database(path: Path) -> Engine:
    """The engine on that file, brought to the latest migration."""
    engine = open_engine(path)
    with engine.begin() as connection:
        migrate(connection)
    return engine
