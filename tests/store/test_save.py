from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

import pytest
from sqlalchemy import Engine

from fixtures.database import golden_database, load, save_whole_season
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.configs import AllplayConfig, BestballFormat, ScrambleFormat
from league.domain.facts import Card, ManualAward, SeasonFacts
from league.store.load import load_tee
from league.store.save import update_tee

PLAYED = datetime(2026, 1, 5, 19, 0)


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    engine = golden_database(tmp_path)
    yield engine
    engine.dispose()


def a_card(card_id: str) -> Card:
    return Card(card_id, PLAYED, S9B.rounds[0].cards["ann"].scores)


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


def test_r14_update_tee_replaces_only_that_tee(database: Engine) -> None:
    changed = replace(S9B.rounds[0].tee, course_rating_tenths=700, slope=125)
    with database.begin() as connection:
        update_tee(connection, "s9b-r1", changed)
    with database.connect() as connection:
        assert load_tee(connection, "s9b-r1") == changed
        assert load_tee(connection, "s9b-r2") == S9B.rounds[1].tee
