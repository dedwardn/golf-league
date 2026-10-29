import json
from collections.abc import Iterator
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from sqlalchemy import Engine, update
from sqlalchemy.sql import Update
from test_save import a_card

from fixtures.database import golden_database, load, save_whole_round, void
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.configs import BestballFormat
from league.store.save import save_card, save_team_card
from league.store.schema import rounds, seasons


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    engine = golden_database(tmp_path)
    yield engine
    engine.dispose()


def test_r13_voided_card_is_left_out(database: Engine) -> None:
    with database.begin() as connection:
        save_card(connection, "t3", 1, "hal", a_card("r1-hal"))
        connection.execute(void("t3", "r1-hal"))
    assert load(database, "t3") == T3


def test_r15_voided_team_card_is_left_out(database: Engine) -> None:
    with database.begin() as connection:
        save_team_card(connection, "t3", 3, "blue", a_card("r3-blue"))
        connection.execute(void("t3", "r3-blue"))
    assert load(database, "t3") == T3


def _round(season_id: str, number: int) -> Update:
    return update(rounds).where(rounds.c.season_id == season_id, rounds.c.number == number)


def test_r13_draft_round_is_left_out(database: Engine) -> None:
    draft = replace(S9B.rounds[2], number=5, cards={}, closed_at=None)
    with database.begin() as connection:
        save_whole_round(connection, "s9b", draft, state="draft")
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
