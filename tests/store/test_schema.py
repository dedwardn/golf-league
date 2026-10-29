from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import Insert
from test_save import PLAYED, a_card

from fixtures.database import a_database, golden_database, void
from league.store.save import save_card, save_player, save_team_card
from league.store.schema import cards, metadata, rounds


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    engine = golden_database(tmp_path)
    yield engine
    engine.dispose()


def _ddl(engine: Engine) -> dict[str, str]:
    """Every table's and index's SQL, which holds its CHECKs and partial index clauses."""
    query = text(
        "SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name != 'alembic_version'"
    )
    with engine.connect() as connection:
        ddl = {name: sql for name, sql in connection.execute(query)}
    engine.dispose()
    return ddl


def test_migrations_build_the_tables_the_store_reads(tmp_path: Path) -> None:
    built = create_engine(f"sqlite:///{tmp_path / 'built.db'}")
    metadata.create_all(built)
    assert _ddl(a_database(tmp_path)) == _ddl(built)


OUT_OF_SHAPE = [
    pytest.param(
        insert(cards).values(
            season_id="s9b",
            card_id="r1-ann",
            round_number=2,
            player_id="ann",
            submitted_at=PLAYED,
            scores="[]",
            voided=True,
        ),
        id="r13-card-id-twice-in-a-season",
    ),
    pytest.param(
        insert(rounds).values(
            season_id="s9b", number=1, tee_id="s9b-r1", state="open", contests="[]", pairings="{}"
        ),
        id="r13-round-number-twice-in-a-season",
    ),
    pytest.param(
        insert(rounds).values(
            season_id="s9b",
            number=9,
            tee_id="s9b-r1",
            state="finished",
            contests="[]",
            pairings="{}",
        ),
        id="r13-state-outside-draft-open-closed",
    ),
    pytest.param(
        insert(cards).values(
            season_id="t3",
            card_id="both",
            round_number=3,
            player_id="cam",
            team_id="blue",
            submitted_at=PLAYED,
            scores="[]",
            voided=False,
        ),
        id="r15-card-of-a-player-and-a-team",
    ),
    pytest.param(
        insert(cards).values(
            season_id="t3",
            card_id="neither",
            round_number=3,
            submitted_at=PLAYED,
            scores="[]",
            voided=False,
        ),
        id="r15-card-of-nobody",
    ),
]


@pytest.mark.parametrize("statement", OUT_OF_SHAPE)
def test_r13_r15_a_fact_out_of_shape_is_refused(database: Engine, statement: Insert) -> None:
    with database.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(statement)


def test_r13_a_second_counted_card_is_refused(database: Engine) -> None:
    with database.begin() as connection, pytest.raises(IntegrityError):
        save_card(connection, "s9b", 1, "ann", a_card("second"))


def test_r15_a_second_counted_team_card_is_refused(database: Engine) -> None:
    with database.begin() as connection, pytest.raises(IntegrityError):
        save_team_card(connection, "t3", 3, "red", a_card("second"))


def test_r13_a_new_card_after_a_void_is_accepted(database: Engine) -> None:
    with database.begin() as connection:
        connection.execute(void("s9b", "r1-ann"))
        save_card(connection, "s9b", 1, "ann", a_card("again"))
        counted = connection.execute(
            select(cards.c.card_id).where(
                cards.c.season_id == "s9b",
                cards.c.round_number == 1,
                cards.c.player_id == "ann",
                cards.c.voided.is_(False),
            )
        ).scalars()
        assert list(counted) == ["again"]


def test_a_link_token_held_by_two_players_is_refused(database: Engine) -> None:
    with database.begin() as connection, pytest.raises(IntegrityError):
        save_player(connection, "ivy", "ann-link")
