import json
from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection, Engine, create_engine, event, insert, select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import Insert

from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.facts import Card, RoundFacts, SeasonFacts
from league.store.schema import (
    cards,
    manual_awards,
    metadata,
    migrate,
    players,
    rounds,
    season_players,
    seasons,
    tees,
)

PLAYED = datetime(2026, 1, 5, 19, 0)


def _foreign_keys_on(dbapi_connection: Any, _record: Any) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def a_database(tmp_path: Path) -> Engine:
    """A migrated SQLite file that enforces its foreign keys."""
    engine = create_engine(f"sqlite:///{tmp_path / 'league.db'}")
    event.listen(engine, "connect", _foreign_keys_on)
    with engine.begin() as connection:
        migrate(connection)
    return engine


def _json(value: Any) -> str:
    """The JSON a stored config holds, written without the store's help, Fractions as strings."""
    return json.dumps(value, default=str)


def card_row(season_id: str, number: int, card: Card, voided: bool = False) -> dict[str, Any]:
    """A cards row without its holder, which the caller adds as player_id or team_id."""
    return {
        "season_id": season_id,
        "card_id": card.card_id,
        "round_number": number,
        "submitted_at": card.submitted_at,
        "scores": _json(card.scores),
        "voided": voided,
    }


def insert_round(connection: Connection, season_id: str, round_: RoundFacts) -> None:
    """The round on a tee of its own, with its cards, team cards and manual awards."""
    tee_id = f"{season_id}-r{round_.number}"
    tee = round_.tee
    connection.execute(
        insert(tees).values(
            tee_id=tee_id,
            pars=_json(tee.pars),
            stroke_indexes=_json(tee.stroke_indexes),
            course_rating_tenths=tee.course_rating_tenths,
            slope=tee.slope,
        )
    )
    connection.execute(
        insert(rounds).values(
            season_id=season_id,
            number=round_.number,
            tee_id=tee_id,
            state="open" if round_.closed_at is None else "closed",
            contests=_json([asdict(contest) for contest in round_.contests]),
            pairings=_json({key: [asdict(p) for p in ps] for key, ps in round_.pairings.items()}),
            format=None if round_.format is None else _json(asdict(round_.format)),
            closed_at=round_.closed_at,
            late_until=round_.late_until,
        )
    )
    for player_id, card in round_.cards.items():
        row = card_row(season_id, round_.number, card)
        connection.execute(insert(cards).values(**row, player_id=player_id))
    for team_id, card in round_.team_cards.items():
        row = card_row(season_id, round_.number, card)
        connection.execute(insert(cards).values(**row, team_id=team_id))
    for award in round_.manual:
        connection.execute(
            insert(manual_awards).values(
                season_id=season_id,
                round_number=round_.number,
                competitor_id=award.competitor_id,
                key=award.key,
                points=str(award.points),
            )
        )


def insert_season(connection: Connection, season_id: str, facts: SeasonFacts) -> None:
    """Every fact of the season as rows, in key order."""
    connection.execute(
        sqlite_insert(players).on_conflict_do_nothing(),
        [{"player_id": player_id} for player_id in facts.seed_index_tenths],
    )
    connection.execute(
        insert(seasons).values(
            season_id=season_id,
            mode=facts.mode,
            index_rule=_json(asdict(facts.index_rule)),
            standings_rule=_json(asdict(facts.standings_rule)),
        )
    )
    connection.execute(
        insert(season_players),
        [
            {
                "season_id": season_id,
                "player_id": player_id,
                "seed_index_tenths": seed,
                "provisional": player_id in facts.provisional,
                "team_id": facts.teams.get(player_id),
            }
            for player_id, seed in facts.seed_index_tenths.items()
        ],
    )
    for round_ in facts.rounds:
        insert_round(connection, season_id, round_)


def golden_database(tmp_path: Path) -> Engine:
    """Both golden seasons in one database, so each load also shows it reads only its own."""
    engine = a_database(tmp_path)
    with engine.begin() as connection:
        insert_season(connection, "s9b", S9B)
        insert_season(connection, "t3", T3)
    return engine


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    engine = golden_database(tmp_path)
    yield engine
    engine.dispose()


def a_card(card_id: str) -> Card:
    return Card(card_id, PLAYED, S9B.rounds[0].cards["ann"].scores)


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
        connection.execute(
            insert(cards).values(**card_row("s9b", 1, a_card("second")), player_id="ann")
        )


def test_r15_a_second_counted_team_card_is_refused(database: Engine) -> None:
    with database.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            insert(cards).values(**card_row("t3", 3, a_card("second")), team_id="red")
        )


def test_r13_a_new_card_after_a_void_is_accepted(database: Engine) -> None:
    with database.begin() as connection:
        connection.execute(
            update(cards)
            .where(cards.c.season_id == "s9b", cards.c.card_id == "r1-ann")
            .values(voided=True)
        )
        connection.execute(
            insert(cards).values(**card_row("s9b", 1, a_card("again")), player_id="ann")
        )
        counted = connection.execute(
            select(cards.c.card_id).where(
                cards.c.season_id == "s9b",
                cards.c.round_number == 1,
                cards.c.player_id == "ann",
                cards.c.voided.is_(False),
            )
        ).scalars()
        assert list(counted) == ["again"]
