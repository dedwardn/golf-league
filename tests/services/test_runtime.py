from pathlib import Path

from sqlalchemy import text

from league.services.play import player_for_link_token
from league.services.runtime import open_database
from league.store.save import save_player


def test_opened_database_enforces_its_foreign_keys(tmp_path: Path) -> None:
    engine = open_database(tmp_path / "league.db")
    with engine.connect() as held, engine.connect() as second:
        for connection in (held, second):
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    engine.dispose()


def test_opening_a_migrated_database_again_keeps_its_rows(tmp_path: Path) -> None:
    path = tmp_path / "league.db"
    first = open_database(path)
    with first.begin() as connection:
        save_player(connection, "ann", "ann-link")
    first.dispose()
    second = open_database(path)
    assert player_for_link_token(second, "ann-link") == "ann"
    second.dispose()
