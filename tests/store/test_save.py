from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection, Engine, create_engine, event, update
from sqlalchemy.sql import Update

from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.configs import AllplayConfig, BestballFormat, ScrambleFormat
from league.domain.facts import Card, ManualAward, RoundFacts, SeasonFacts
from league.store.load import load_season_facts
from league.store.save import (
    save_card,
    save_manual_award,
    save_player,
    save_round,
    save_season,
    save_season_team,
    save_seeded_player,
    save_team_card,
    save_tee,
)
from league.store.schema import cards, migrate

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


def save_whole_round(
    connection: Connection, season_id: str, round_: RoundFacts, state: str | None = None
) -> None:
    """The round on a tee of its own, with its cards, team cards and manual awards."""
    tee_id = f"{season_id}-r{round_.number}"
    save_tee(connection, tee_id, round_.tee)
    if state is None:
        state = "open" if round_.closed_at is None else "closed"
    save_round(connection, season_id, round_, tee_id, state)
    for player_id, card in round_.cards.items():
        save_card(connection, season_id, round_.number, player_id, card)
    for team_id, card in round_.team_cards.items():
        save_team_card(connection, season_id, round_.number, team_id, card)
    for award in round_.manual:
        save_manual_award(connection, season_id, round_.number, award)


def save_whole_season(connection: Connection, season_id: str, facts: SeasonFacts) -> None:
    """Every fact of the season but its players, whom several seasons share."""
    save_season(connection, season_id, facts.mode, facts.index_rule, facts.standings_rule)
    for player_id, seed in facts.seed_index_tenths.items():
        provisional = player_id in facts.provisional
        save_seeded_player(connection, season_id, player_id, seed, provisional)
    for team_id in set(facts.teams.values()):
        members = tuple(player for player, team in facts.teams.items() if team == team_id)
        save_season_team(connection, season_id, team_id, members)
    for round_ in facts.rounds:
        save_whole_round(connection, season_id, round_)


def golden_database(tmp_path: Path) -> Engine:
    """Both golden seasons in one database, so each load also shows it reads only its own."""
    engine = a_database(tmp_path)
    with engine.begin() as connection:
        for player_id in {*S9B.seed_index_tenths, *T3.seed_index_tenths}:
            save_player(connection, player_id)
        save_whole_season(connection, "s9b", S9B)
        save_whole_season(connection, "t3", T3)
    return engine


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    engine = golden_database(tmp_path)
    yield engine
    engine.dispose()


def a_card(card_id: str) -> Card:
    return Card(card_id, PLAYED, S9B.rounds[0].cards["ann"].scores)


def void(season_id: str, card_id: str) -> Update:
    """A void as S14 will store it, until then written by hand."""
    card = (cards.c.season_id == season_id, cards.c.card_id == card_id)
    return update(cards).where(*card).values(voided=True)


def load(engine: Engine, season_id: str) -> SeasonFacts:
    with engine.connect() as connection:
        return load_season_facts(connection, season_id)


def test_r13_the_golden_season_round_trips(database: Engine) -> None:
    assert load(database, "s9b") == S9B


def test_r15_the_golden_team_season_round_trips(database: Engine) -> None:
    assert load(database, "t3") == T3


def s9b_off_its_defaults() -> SeasonFacts:
    """S9b with a provisional player, a late_until, a negative third and a scale of two thirds.

    ann's adjustment sorts before eve's award by competitor and by key, so only the order the
    awards were given in puts it second.
    """
    round_1, round_2, round_3, round_4 = S9B.rounds
    allplay = round_3.contests[0]
    assert isinstance(allplay, AllplayConfig)
    assert round_2.closed_at is not None
    adjustment = ManualAward("ann", "adjustment", Fraction(-1, 3))
    return replace(
        S9B,
        provisional=frozenset({"fay"}),
        rounds=(
            replace(round_1, manual=(*round_1.manual, adjustment)),
            replace(round_2, late_until=round_2.closed_at + timedelta(days=1)),
            replace(round_3, contests=(replace(allplay, scale=Fraction(2, 3)),)),
            round_4,
        ),
    )


def test_r5_r9_r13_facts_off_their_defaults_round_trip(database: Engine) -> None:
    changed = s9b_off_its_defaults()
    with database.begin() as connection:
        save_whole_season(connection, "s9b-changed", changed)
    assert load(database, "s9b-changed") == changed


def test_r16_format_allowances_set_by_the_round_round_trip(database: Engine) -> None:
    round_1, round_2, round_3, round_4, round_5 = T3.rounds
    changed = replace(
        T3,
        rounds=(
            replace(round_1, format=BestballFormat(allowance=80)),
            round_2,
            replace(round_3, format=ScrambleFormat(low=30, high=20)),
            round_4,
            round_5,
        ),
    )
    with database.begin() as connection:
        save_whole_season(connection, "t3-changed", changed)
    assert load(database, "t3-changed") == changed
