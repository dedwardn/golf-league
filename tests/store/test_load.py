import json
from collections.abc import Iterator
from dataclasses import asdict, replace
from datetime import timedelta
from fractions import Fraction
from pathlib import Path

import pytest
from sqlalchemy import Engine, insert, update
from sqlalchemy.sql import Update
from test_schema import a_card, card_row, golden_database, insert_round, insert_season

from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.configs import AllplayConfig, BestballFormat, ScrambleFormat
from league.domain.facts import ManualAward, SeasonFacts
from league.store.load import load_season_facts
from league.store.schema import cards, rounds, seasons


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    engine = golden_database(tmp_path)
    yield engine
    engine.dispose()


def load(engine: Engine, season_id: str) -> SeasonFacts:
    with engine.connect() as connection:
        return load_season_facts(connection, season_id)


def test_s9b_golden_season_loads_as_inserted(database: Engine) -> None:
    assert load(database, "s9b") == S9B


def test_t3_golden_team_season_loads_as_inserted(database: Engine) -> None:
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


def test_r5_r9_r13_facts_off_their_defaults_load_as_inserted(database: Engine) -> None:
    changed = s9b_off_its_defaults()
    with database.begin() as connection:
        insert_season(connection, "s9b-changed", changed)
    assert load(database, "s9b-changed") == changed


def test_r16_format_allowances_set_by_the_round_load_as_inserted(database: Engine) -> None:
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
        insert_season(connection, "t3-changed", changed)
    assert load(database, "t3-changed") == changed


def test_r13_voided_card_is_left_out(database: Engine) -> None:
    with database.begin() as connection:
        row = card_row("t3", 1, a_card("r1-hal"), voided=True)
        connection.execute(insert(cards).values(**row, player_id="hal"))
    assert load(database, "t3") == T3


def test_r15_voided_team_card_is_left_out(database: Engine) -> None:
    with database.begin() as connection:
        row = card_row("t3", 3, a_card("r3-blue"), voided=True)
        connection.execute(insert(cards).values(**row, team_id="blue"))
    assert load(database, "t3") == T3


def _round(season_id: str, number: int) -> Update:
    return update(rounds).where(rounds.c.season_id == season_id, rounds.c.number == number)


def test_r13_draft_round_is_left_out(database: Engine) -> None:
    draft = replace(S9B.rounds[2], number=5, cards={}, closed_at=None)
    with database.begin() as connection:
        insert_round(connection, "s9b", draft)
        connection.execute(_round("s9b", 5).values(state="draft"))
    assert load(database, "s9b") == S9B


REFUSED_CONFIGS = [
    pytest.param(
        "s9b",
        _round("s9b", 3).values(
            contests=json.dumps(
                [asdict(S9B.rounds[2].contests[0]) | {"allowance": 120}], default=str
            )
        ),
        "allowance is a whole percent",
        id="contest-allowance",
    ),
    pytest.param(
        "s9b",
        update(seasons)
        .where(seasons.c.season_id == "s9b")
        .values(index_rule=json.dumps(asdict(S9B.index_rule) | {"rate_up": 150})),
        "every rate is a whole percent",
        id="index-rule-rate",
    ),
    pytest.param(
        "s9b",
        update(seasons)
        .where(seasons.c.season_id == "s9b")
        .values(standings_rule=json.dumps(asdict(S9B.standings_rule) | {"best_n": 0})),
        "best_n is 1 or more",
        id="standings-rule-best-n",
    ),
    pytest.param(
        "t3",
        _round("t3", 1).values(format=json.dumps(asdict(BestballFormat()) | {"allowance": 120})),
        "allowance is a whole percent",
        id="format-allowance",
    ),
    pytest.param(
        "s9b",
        _round("s9b", 3).values(
            contests=json.dumps(
                [{k: v for k, v in asdict(S9B.rounds[2].contests[0]).items() if k != "kind"}],
                default=str,
            )
        ),
        "discriminator",
        id="contest-without-its-kind",
    ),
    pytest.param(
        "t3",
        _round("t3", 3).values(format=json.dumps({"low": 30, "high": 20})),
        "discriminator",
        id="format-without-its-tag",
    ),
]


@pytest.mark.parametrize(("season_id", "statement", "message"), REFUSED_CONFIGS)
def test_r5_r9_r10_r16_config_out_of_bounds_or_untagged_is_refused_on_load(
    database: Engine, season_id: str, statement: Update, message: str
) -> None:
    with database.begin() as connection:
        connection.execute(statement)
    with pytest.raises(ValueError, match=message):
        load(database, season_id)
