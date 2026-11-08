import json
from collections.abc import Iterator
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from sqlalchemy import Engine, update
from sqlalchemy.sql import Update
from test_save import a_card

from fixtures.database import WINDOW_CLOSES, golden_database, load, save_whole_round
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.configs import BestballFormat
from league.domain.facts import RoundFacts, RoundHeading, Tee
from league.store.load import (
    load_link_tokens,
    load_round,
    load_round_headings,
    load_rounds_on_tee,
    load_tee,
)
from league.store.save import (
    save_card,
    save_player,
    save_round,
    save_team_card,
    save_tee,
    update_card_voided,
)
from league.store.schema import rounds, seasons


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    engine = golden_database(tmp_path)
    yield engine
    engine.dispose()


def test_r13_voided_card_is_left_out(database: Engine) -> None:
    with database.begin() as connection:
        save_card(connection, "t3", 1, "hal", a_card("r1-hal"))
        update_card_voided(connection, "t3", "r1-hal")
    assert load(database, "t3") == T3


def test_r15_voided_team_card_is_left_out(database: Engine) -> None:
    with database.begin() as connection:
        save_team_card(connection, "t3", 3, "blue", a_card("r3-blue"))
        update_card_voided(connection, "t3", "r3-blue")
    assert load(database, "t3") == T3


def _round(season_id: str, number: int) -> Update:
    return update(rounds).where(rounds.c.season_id == season_id, rounds.c.number == number)


def test_r13_draft_round_is_left_out(database: Engine) -> None:
    draft = replace(S9B.rounds[2], number=5, cards={}, closed_at=None)
    with database.begin() as connection:
        save_whole_round(connection, "s9b", draft, state="draft")
    assert load(database, "s9b") == S9B


def test_r13_load_round_reads_only_a_round_in_that_state(database: Engine) -> None:
    """Round 6 carries round 4's duel and pairings, so the wrong draft would show."""
    fifth = replace(S9B.rounds[2], number=5, cards={}, closed_at=None)
    sixth = replace(S9B.rounds[3], number=6, cards={}, manual=())
    with database.begin() as connection:
        save_whole_round(connection, "s9b", fifth, state="draft")
        save_whole_round(connection, "s9b", sixth, state="draft")
        assert load_round(connection, "s9b", 6, "draft") == sixth
        assert load_round(connection, "s9b", 4, "draft") is None
        assert load_round(connection, "s9b", 4, "open") == S9B.rounds[3]


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


def test_load_round_headings_are_the_open_rounds_in_number_order(database: Engine) -> None:
    """S9b's round 4 is open and its rounds 1 to 3 closed. T3 has every round closed."""
    empty = replace(S9B.rounds[3], cards={}, manual=())
    with database.begin() as connection:
        save_whole_round(connection, "s9b", replace(empty, number=7))
        save_whole_round(connection, "s9b", replace(empty, number=6))
        save_whole_round(connection, "s9b", replace(empty, number=5), state="draft")
        assert load_round_headings(connection, "s9b") == (
            RoundHeading(4, WINDOW_CLOSES),
            RoundHeading(6, WINDOW_CLOSES),
            RoundHeading(7, WINDOW_CLOSES),
        )
        assert load_round_headings(connection, "t3") == ()


def test_load_tee_reads_the_tee_of_that_course_and_name(database: Engine) -> None:
    """T3's Blue shares the course of T3's White, and S9b's White shares its name."""
    tees = (T3.rounds[0].tee, T3.rounds[2].tee, S9B.rounds[0].tee)
    with database.connect() as connection:
        assert tuple(load_tee(connection, tee.course, tee.name) for tee in tees) == tees


def test_load_tee_reads_none_for_a_tee_nobody_stored(database: Engine) -> None:
    """One shares only the course of T3's White and Blue, the other only the name White."""
    with database.connect() as connection:
        assert load_tee(connection, T3.rounds[0].tee.course, "Red") is None
        assert load_tee(connection, "Nowhere", "White") is None


def rounds_on_tee(engine: Engine, tee: Tee) -> tuple[RoundFacts, ...]:
    with engine.connect() as connection:
        return load_rounds_on_tee(connection, tee.course, tee.name)


def test_r14_rounds_on_a_tee_leave_out_a_tee_sharing_its_course_or_its_name(
    database: Engine,
) -> None:
    """T3's White is on the course of its Blue, and has the name of S9b's White."""
    assert rounds_on_tee(database, T3.rounds[0].tee) == T3.rounds[:2]


def test_r14_rounds_on_a_tee_come_from_every_season_without_drafts_or_voided_cards(
    database: Engine,
) -> None:
    """S9b's tee, also used by an open T3 round 6 with one card and a draft S9b round 5."""
    tee = S9B.rounds[0].tee
    t3_round = replace(
        T3.rounds[0], number=6, tee=tee, cards={"hal": a_card("r6-hal")}, closed_at=None
    )
    draft = replace(S9B.rounds[0], number=5, cards={}, closed_at=None)
    with database.begin() as connection:
        save_round(connection, "t3", t3_round, "open")
        save_card(connection, "t3", 6, "hal", a_card("r6-hal"))
        save_round(connection, "s9b", draft, "draft")
        update_card_voided(connection, "s9b", "r1-ann")
    round_1, *later = S9B.rounds
    without_ann = {player: card for player, card in round_1.cards.items() if player != "ann"}
    expected = (replace(round_1, cards=without_ann), *later, t3_round)
    assert rounds_on_tee(database, tee) == expected


def test_r14_round_on_a_fresh_tee_takes_no_cards_from_another_seasons_round_of_its_number(
    database: Engine,
) -> None:
    """S9b's round 5 on a tee of its own meets T3's round 5, whose team cards are on another."""
    tee = replace(S9B.rounds[0].tee, name="Yellow")
    fresh = replace(S9B.rounds[0], number=5, tee=tee, cards={}, manual=(), closed_at=None)
    with database.begin() as connection:
        save_tee(connection, tee)
        save_round(connection, "s9b", fresh, "open")
    assert rounds_on_tee(database, tee) == (fresh,)


def test_load_link_tokens_reads_every_player_in_id_order(database: Engine) -> None:
    """Stored after the golden players, and Zed before Abe, so only an order by id passes."""
    with database.begin() as connection:
        save_player(connection, "Zed", "zed-token")
        save_player(connection, "Abe", "abe-token")
        tokens = load_link_tokens(connection)
    golden = ["ann", "bob", "cam", "dee", "eve", "fay", "gus", "hal"]
    assert list(tokens) == ["Abe", "Zed", *golden]
    assert tokens["Abe"] == "abe-token"
    assert tokens["ann"] == "ann-link"
