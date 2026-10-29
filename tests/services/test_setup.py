from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select, update
from sqlalchemy.exc import IntegrityError
from test_play import t3_open

from fixtures.database import golden_database, load, save_whole_round, save_whole_season, void
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.facts import Card, RoundFacts, SeasonFacts, Tee
from league.services.play import player_for_link_token
from league.services.setup import (
    RoundSetup,
    change_tee,
    correct_seed_index,
    create_player,
    create_round,
    create_season,
    create_tee,
    replace_link_token,
)
from league.store.load import load_tee
from league.store.schema import metadata, rounds

OPENS = datetime(2026, 3, 2, 8, 0)
CLOSES = datetime(2026, 3, 9, 22, 0)
LATE_UNTIL = datetime(2026, 3, 16, 22, 0)
OTHER_TEE = replace(S9B.rounds[0].tee, course_rating_tenths=700, slope=125)


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    engine = golden_database(tmp_path)
    with engine.begin() as connection:
        save_whole_season(connection, "t3-open", t3_open())
    yield engine
    engine.dispose()


def everything(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    with engine.connect() as connection:
        return {
            table.name: [tuple(row) for row in connection.execute(select(table))]
            for table in metadata.sorted_tables
        }


def assert_refused(engine: Engine, action: Callable[[], object], match: str) -> None:
    """A ValueError from the service or the domain, not the database's, and nothing stored."""
    before = everything(engine)
    with pytest.raises(ValueError, match=match):
        action()
    assert everything(engine) == before


def tee(engine: Engine, tee_id: str) -> Tee:
    with engine.connect() as connection:
        return load_tee(connection, tee_id)


def test_create_player_link_token_finds_them(database: Engine) -> None:
    link_token = create_player(database, "ida")
    assert player_for_link_token(database, link_token) == "ida"


def test_create_player_gives_each_player_their_own_link_token(database: Engine) -> None:
    assert create_player(database, "ida") != create_player(database, "jon")


def test_replaced_link_token_finds_them_and_the_old_one_finds_nobody(database: Engine) -> None:
    old = create_player(database, "ida")
    jons = create_player(database, "jon")
    new = replace_link_token(database, "ida")
    assert player_for_link_token(database, new) == "ida"
    assert player_for_link_token(database, old) is None
    assert player_for_link_token(database, jons) == "jon"


def test_replacing_the_link_token_of_an_unknown_player_is_refused(database: Engine) -> None:
    assert_refused(database, lambda: replace_link_token(database, "nobody"), "no player nobody")


def test_create_tee_stores_the_tee(database: Engine) -> None:
    create_tee(database, "fresh", OTHER_TEE)
    assert tee(database, "fresh") == OTHER_TEE


def test_r14_tee_without_a_card_is_changed(database: Engine) -> None:
    create_tee(database, "fresh", S9B.rounds[0].tee)
    create_round(database, RoundSetup("s9b", 5, "fresh", OPENS, CLOSES, S9B.rounds[0].contests))
    change_tee(database, "fresh", OTHER_TEE)
    assert tee(database, "fresh") == OTHER_TEE


def test_r14_tee_with_a_card_is_not_changed(database: Engine) -> None:
    assert_refused(database, lambda: change_tee(database, "s9b-r1", OTHER_TEE), "has a card")


def test_r14_tee_with_a_team_card_is_not_changed(database: Engine) -> None:
    assert_refused(database, lambda: change_tee(database, "t3-r3", OTHER_TEE), "has a card")


def test_r14_tee_whose_only_card_is_voided_is_changed(database: Engine) -> None:
    card = Card("r5-ann", OPENS, S9B.rounds[0].cards["ann"].scores)
    lone = replace(S9B.rounds[0], number=5, cards={"ann": card}, closed_at=None)
    with database.begin() as connection:
        save_whole_round(connection, "s9b", lone)
        connection.execute(void("s9b", "r5-ann"))
    change_tee(database, "s9b-r5", OTHER_TEE)
    assert tee(database, "s9b-r5") == OTHER_TEE


GOLDEN_SETUPS = [
    pytest.param(replace(S9B, rounds=(), provisional=frozenset({"ann"})), id="s9b"),
    pytest.param(replace(T3, rounds=()), id="t3"),
]


@pytest.mark.parametrize("facts", GOLDEN_SETUPS)
def test_create_season_stores_the_golden_season_setup(database: Engine, facts: SeasonFacts) -> None:
    create_season(database, "new", facts)
    assert load(database, "new") == facts


def test_create_season_refuses_a_season_team_naming_a_player_without_a_seed_index(
    database: Engine,
) -> None:
    seeds = {player: seed for player, seed in S9B.seed_index_tenths.items() if player != "fay"}
    facts = replace(S9B, rounds=(), seed_index_tenths=seeds)
    assert_refused(database, lambda: create_season(database, "new", facts), "no seed index")


def seed(engine: Engine, season_id: str, player_id: str) -> int:
    return load(engine, season_id).seed_index_tenths[player_id]


def test_r15_seed_index_is_corrected_before_round_one_closes(database: Engine) -> None:
    correct_seed_index(database, "t3-open", "ann", 25)
    assert seed(database, "t3-open", "ann") == 25
    assert (seed(database, "t3", "ann"), seed(database, "s9b", "ann")) == (20, 0)


def test_r15_seed_index_is_locked_once_round_one_closes(database: Engine) -> None:
    assert_refused(database, lambda: correct_seed_index(database, "t3", "ann", 25), "locked")


def test_r15_individual_season_seed_index_is_corrected_after_round_one_closes(
    database: Engine,
) -> None:
    correct_seed_index(database, "s9b", "ann", 5)
    assert seed(database, "s9b", "ann") == 5
    assert (seed(database, "t3", "ann"), seed(database, "t3-open", "ann")) == (20, 20)


def test_seed_index_of_a_player_not_seeded_in_the_season_is_refused(database: Engine) -> None:
    """gus is a league player seeded in T3, not in S9b."""
    assert_refused(
        database,
        lambda: correct_seed_index(database, "s9b", "gus", 5),
        "has no seed index in season s9b",
    )


def open_by_hand(engine: Engine, season_id: str, number: int) -> None:
    """An open as S14b will store it, until then written by hand."""
    round_ = (rounds.c.season_id == season_id, rounds.c.number == number)
    with engine.begin() as connection:
        connection.execute(update(rounds).where(*round_).values(state="open"))


NEW_ROUNDS = [
    pytest.param(
        RoundSetup(
            "s9b", 5, "s9b-r1", OPENS, CLOSES, S9B.rounds[0].contests, late_until=LATE_UNTIL
        ),
        id="individual-with-late-until",
    ),
    pytest.param(
        RoundSetup(
            "t3", 6, "t3-r3", OPENS, CLOSES, T3.rounds[2].contests, format=T3.rounds[2].format
        ),
        id="team-with-format",
    ),
]


@pytest.mark.parametrize("setup", NEW_ROUNDS)
def test_r13_create_round_stores_a_draft(database: Engine, setup: RoundSetup) -> None:
    before = load(database, setup.season_id)
    create_round(database, setup)
    assert load(database, setup.season_id) == before
    with database.connect() as connection:
        row = connection.execute(
            select(rounds.c.state, rounds.c.opens_at, rounds.c.closes_at).where(
                rounds.c.season_id == setup.season_id, rounds.c.number == setup.number
            )
        ).one()
    assert tuple(row) == ("draft", OPENS, CLOSES)
    open_by_hand(database, setup.season_id, setup.number)
    expected = RoundFacts(
        number=setup.number,
        tee=tee(database, setup.tee_id),
        contests=setup.contests,
        cards={},
        pairings={},
        manual=(),
        closed_at=None,
        format=setup.format,
        late_until=setup.late_until,
    )
    assert load(database, setup.season_id).rounds[-1] == expected


REFUSED_ROUNDS = [
    pytest.param(
        RoundSetup(
            "s9b", 5, "s9b-r1", OPENS, CLOSES, S9B.rounds[0].contests, format=T3.rounds[0].format
        ),
        "an individual season's round has no format",
        id="r15-format-in-an-individual-season",
    ),
    pytest.param(
        RoundSetup("t3", 6, "t3-r1", OPENS, CLOSES, T3.rounds[0].contests),
        "round 6 of a team season has no format",
        id="r15-team-round-without-a-format",
    ),
    pytest.param(
        RoundSetup(
            "t3", 6, "t3-r1", OPENS, CLOSES, S9B.rounds[1].contests, format=T3.rounds[0].format
        ),
        "a team season's contests are field or allplay",
        id="r15-duel-in-a-team-season",
    ),
    pytest.param(
        RoundSetup(
            "t3",
            6,
            "t3-r1",
            OPENS,
            CLOSES,
            T3.rounds[0].contests,
            format=T3.rounds[0].format,
            late_until=LATE_UNTIL,
        ),
        "a team season's round takes no late cards",
        id="r13-late-until-in-a-team-season",
    ),
    pytest.param(
        RoundSetup("s9b", 4, "s9b-r4", OPENS, CLOSES, S9B.rounds[3].contests),
        "a round's number is unique in its season",
        id="r13-number-of-an-open-round",
    ),
]


@pytest.mark.parametrize(("setup", "match"), REFUSED_ROUNDS)
def test_r13_r15_round_that_does_not_fit_its_season_is_refused(
    database: Engine, setup: RoundSetup, match: str
) -> None:
    assert_refused(database, lambda: create_round(database, setup), match)


def test_r13_number_of_a_draft_round_is_refused_by_the_key(database: Engine) -> None:
    setup = RoundSetup("s9b", 5, "s9b-r1", OPENS, CLOSES, S9B.rounds[0].contests)
    create_round(database, setup)
    before = everything(database)
    with pytest.raises(IntegrityError):
        create_round(database, replace(setup, closes_at=LATE_UNTIL))
    assert everything(database) == before
