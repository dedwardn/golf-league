from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError

from fixtures.database import a_copy, a_template, everything, load, save_whole_round
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from fixtures.team_season import t3_open
from league.domain.facts import Card, RoundFacts, SeasonFacts
from league.domain.tees import Tee
from league.services.play import player_for_link_token
from league.services.run import close_round, open_round, reopen_round, void_card
from league.services.setup import (
    RoundSetup,
    change_round,
    change_tee,
    correct_seed_index,
    create_player,
    create_round,
    create_season,
    create_tee,
    link_tokens,
    replace_link_token,
    stored_season,
    stored_tee,
)
from league.store.schema import rounds

OPENS = datetime(2026, 3, 2, 8, 0)
CLOSES = datetime(2026, 3, 9, 22, 0)
LATE_UNTIL = datetime(2026, 3, 16, 22, 0)
S9B_TEE = S9B.rounds[0].tee
WHITE = T3.rounds[0].tee
BLUE = T3.rounds[2].tee
# A tee no round is on, with S9b's numbers.
FRESH_TEE = replace(S9B_TEE, name="Yellow")


def on(tee: Tee) -> tuple[str, str]:
    """The course and tee name a round setup names its tee by."""
    return (tee.course, tee.name)


def rerated(tee: Tee) -> Tee:
    """The tee of that course and name with other numbers."""
    return replace(tee, course_rating_tenths=700, slope=125)


def t3_first() -> SeasonFacts:
    """T3 at its start: round one is open and nothing has closed."""
    return replace(T3, rounds=(replace(T3.rounds[0], closed_at=None),))


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return a_template(
        tmp_path_factory.mktemp("template"), {"t3-open": t3_open(), "t3-first": t3_first()}
    )


@pytest.fixture
def database(template: Path, tmp_path: Path) -> Iterator[Engine]:
    engine = a_copy(template, tmp_path)
    yield engine
    engine.dispose()


def assert_refused(engine: Engine, action: Callable[[], object], match: str) -> None:
    """A ValueError from the service or the domain, not the database's, and nothing stored."""
    before = everything(engine)
    with pytest.raises(ValueError, match=match):
        action()
    assert everything(engine) == before


def stored(engine: Engine, course: str, tee_name: str) -> Tee:
    """The tee stored under that course and tee name, which a test expects to be there."""
    tee = stored_tee(engine, course, tee_name)
    assert tee is not None
    return tee


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


def test_create_player_refuses_a_stored_player(database: Engine) -> None:
    create_player(database, "ida")
    assert_refused(database, lambda: create_player(database, "ida"), "player ida is already stored")


def test_create_player_refuses_an_empty_id(database: Engine) -> None:
    assert_refused(database, lambda: create_player(database, ""), "a player has a name")


def test_link_tokens_reads_what_create_and_replace_wrote(database: Engine) -> None:
    ida = create_player(database, "ida")
    create_player(database, "jon")
    jon = replace_link_token(database, "jon")
    tokens = link_tokens(database)
    assert (tokens["ida"], tokens["jon"]) == (ida, jon)


def test_create_tee_stores_the_tee(database: Engine) -> None:
    create_tee(database, FRESH_TEE)
    assert stored(database, *on(FRESH_TEE)) == FRESH_TEE


def test_create_tee_refuses_a_stored_course_and_name(database: Engine) -> None:
    assert_refused(database, lambda: create_tee(database, rerated(WHITE)), "already stored")


def test_create_tee_stores_a_new_course_with_a_stored_tee_name(database: Engine) -> None:
    """White is stored, of T3's course and of S9b's, but not of this one."""
    tee = replace(WHITE, course="New Links")
    create_tee(database, tee)
    assert stored(database, *on(tee)) == tee


def test_stored_tee_reads_the_tee_and_none_for_a_tee_nobody_stored(database: Engine) -> None:
    assert stored_tee(database, *on(WHITE)) == WHITE
    assert stored_tee(database, "Nowhere", "White") is None


def test_change_tee_refuses_a_tee_nobody_stored(database: Engine) -> None:
    nobodys = replace(FRESH_TEE, course="Nowhere")
    assert_refused(database, lambda: change_tee(database, nobodys), "no tee Yellow of Nowhere")


def test_r14_tee_without_a_card_is_changed(database: Engine) -> None:
    create_tee(database, FRESH_TEE)
    setup = RoundSetup("s9b", 5, *on(FRESH_TEE), OPENS, CLOSES, S9B.rounds[0].contests)
    create_round(database, setup)
    change_tee(database, rerated(FRESH_TEE))
    assert stored(database, *on(FRESH_TEE)) == rerated(FRESH_TEE)


def test_r14_tee_with_a_card_is_not_changed(database: Engine) -> None:
    assert_refused(database, lambda: change_tee(database, rerated(S9B_TEE)), "has a card")


def test_r14_tee_with_a_team_card_is_not_changed(database: Engine) -> None:
    """T3's shared-ball rounds are on Blue, which holds team cards only."""
    assert_refused(database, lambda: change_tee(database, rerated(BLUE)), "has a card")


def test_r14_tee_whose_only_card_is_voided_is_changed(database: Engine) -> None:
    card = Card("r5-ann", OPENS, S9B.rounds[0].cards["ann"].scores)
    lone = replace(S9B.rounds[0], number=5, tee=FRESH_TEE, cards={"ann": card}, closed_at=None)
    with database.begin() as connection:
        save_whole_round(connection, "s9b", lone)
    void_card(database, "s9b", "r5-ann")
    change_tee(database, rerated(FRESH_TEE))
    assert stored(database, *on(FRESH_TEE)) == rerated(FRESH_TEE)


GOLDEN_SETUPS = [
    pytest.param(replace(S9B, rounds=(), provisional=frozenset({"ann"})), id="s9b"),
    pytest.param(replace(T3, rounds=()), id="t3"),
]


@pytest.mark.parametrize("facts", GOLDEN_SETUPS)
def test_create_season_stores_the_golden_season_setup(database: Engine, facts: SeasonFacts) -> None:
    create_season(database, "new", facts)
    assert load(database, "new") == facts


def test_section_7_create_season_refuses_a_season_team_naming_a_player_without_a_seed_index(
    database: Engine,
) -> None:
    seeds = {player: seed for player, seed in S9B.seed_index_tenths.items() if player != "fay"}
    facts = replace(S9B, rounds=(), seed_index_tenths=seeds)
    assert_refused(
        database, lambda: create_season(database, "new", facts), r"fay is not in the season\."
    )


def test_section_7_create_season_refuses_a_team_season_without_a_team(database: Engine) -> None:
    facts = replace(T3, rounds=(), seed_index_tenths={}, teams={})
    assert_refused(database, lambda: create_season(database, "new", facts), r"at least one team\.")
    create_season(database, "new", replace(S9B, rounds=(), teams={}))
    assert load(database, "new").teams == {}


def test_create_season_refuses_a_stored_season(database: Engine) -> None:
    facts = replace(T3, rounds=())
    assert_refused(database, lambda: create_season(database, "t3", facts), "already stored")


def test_stored_season_reads_the_season_and_none_for_one_nobody_stored(database: Engine) -> None:
    assert stored_season(database, "t3") == T3
    assert stored_season(database, "nobody") is None


def seed(engine: Engine, season_id: str, player_id: str) -> int:
    return load(engine, season_id).seed_index_tenths[player_id]


def test_r15_seed_index_is_corrected_while_no_round_is_closed(database: Engine) -> None:
    correct_seed_index(database, "t3-first", "ann", 25)
    assert seed(database, "t3-first", "ann") == 25
    assert (seed(database, "t3", "ann"), seed(database, "s9b", "ann")) == (20, 0)


def test_r15_seed_index_corrected_outside_minus_5_to_54_is_refused(database: Engine) -> None:
    assert_refused(
        database,
        lambda: correct_seed_index(database, "t3-first", "ann", 541),
        "not -5.0 to 54.0",
    )


def test_r15_seed_index_is_locked_once_round_one_closes(database: Engine) -> None:
    close_round(database, "t3-first", 1, CLOSES)
    assert_refused(database, lambda: correct_seed_index(database, "t3-first", "ann", 25), "locked")


def test_r15_seed_index_is_corrected_once_the_only_closed_round_reopens(database: Engine) -> None:
    close_round(database, "t3-first", 1, CLOSES)
    reopen_round(database, "t3-first", 1)
    correct_seed_index(database, "t3-first", "ann", 25)
    assert seed(database, "t3-first", "ann") == 25


def test_r15_seed_index_stays_locked_when_round_one_reopens_before_a_later_closed_round(
    database: Engine,
) -> None:
    reopen_round(database, "t3", 1)
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


NEW_ROUNDS = [
    pytest.param(
        RoundSetup(
            "s9b", 5, *on(S9B_TEE), OPENS, CLOSES, S9B.rounds[0].contests, late_until=LATE_UNTIL
        ),
        id="individual-with-late-until",
    ),
    pytest.param(
        RoundSetup(
            "t3", 6, *on(BLUE), OPENS, CLOSES, T3.rounds[2].contests, format=T3.rounds[2].format
        ),
        id="team-with-format",
    ),
]


def window(engine: Engine, setup: RoundSetup) -> tuple[Any, ...]:
    with engine.connect() as connection:
        row = connection.execute(
            select(rounds.c.state, rounds.c.opens_at, rounds.c.closes_at).where(
                rounds.c.season_id == setup.season_id, rounds.c.number == setup.number
            )
        ).one()
    return tuple(row)


def opened(engine: Engine, setup: RoundSetup) -> RoundFacts:
    """The round the setup describes, as it loads once open."""
    return RoundFacts(
        number=setup.number,
        tee=stored(engine, setup.course, setup.tee_name),
        contests=setup.contests,
        cards={},
        pairings={},
        manual=(),
        closed_at=None,
        format=setup.format,
        late_until=setup.late_until,
    )


@pytest.mark.parametrize("setup", NEW_ROUNDS)
def test_r13_create_round_stores_a_draft(database: Engine, setup: RoundSetup) -> None:
    before = load(database, setup.season_id)
    create_round(database, setup)
    assert load(database, setup.season_id) == before
    assert window(database, setup) == ("draft", OPENS, CLOSES)
    open_round(database, setup.season_id, setup.number)
    assert load(database, setup.season_id).rounds[-1] == opened(database, setup)


REFUSED_ROUNDS = [
    pytest.param(
        RoundSetup(
            "s9b",
            5,
            *on(S9B_TEE),
            OPENS,
            CLOSES,
            S9B.rounds[0].contests,
            format=T3.rounds[0].format,
        ),
        "an individual season's round has no format",
        id="r15-format-in-an-individual-season",
    ),
    pytest.param(
        RoundSetup("t3", 6, *on(WHITE), OPENS, CLOSES, T3.rounds[0].contests),
        "round 6 of a team season has no format",
        id="r15-team-round-without-a-format",
    ),
    pytest.param(
        RoundSetup(
            "t3", 6, *on(WHITE), OPENS, CLOSES, S9B.rounds[1].contests, format=T3.rounds[0].format
        ),
        "a team season's contests are field or allplay",
        id="r15-duel-in-a-team-season",
    ),
    pytest.param(
        RoundSetup(
            "t3",
            6,
            *on(WHITE),
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
        RoundSetup("s9b", 4, *on(S9B_TEE), OPENS, CLOSES, S9B.rounds[3].contests),
        "a round's number is unique in its season",
        id="r13-number-of-an-open-round",
    ),
    pytest.param(
        RoundSetup("s9b", 5, "Nowhere", "White", OPENS, CLOSES, S9B.rounds[0].contests),
        "no tee White of Nowhere",
        id="a-tee-nobody-stored",
    ),
]


@pytest.mark.parametrize(("setup", "match"), REFUSED_ROUNDS)
def test_r13_r15_round_that_does_not_fit_its_season_is_refused(
    database: Engine, setup: RoundSetup, match: str
) -> None:
    assert_refused(database, lambda: create_round(database, setup), match)


def test_r13_number_of_a_draft_round_is_refused_by_the_key(database: Engine) -> None:
    setup = RoundSetup("s9b", 5, *on(S9B_TEE), OPENS, CLOSES, S9B.rounds[0].contests)
    create_round(database, setup)
    before = everything(database)
    with pytest.raises(IntegrityError):
        create_round(database, replace(setup, closes_at=LATE_UNTIL))
    assert everything(database) == before


def everything_loaded(engine: Engine) -> dict[str, SeasonFacts]:
    return {season_id: load(engine, season_id) for season_id in ("s9b", "t3", "t3-open")}


CHANGES = [
    pytest.param(
        RoundSetup("s9b", 5, *on(S9B_TEE), OPENS, CLOSES, S9B.rounds[0].contests),
        RoundSetup(
            "s9b", 5, *on(BLUE), CLOSES, LATE_UNTIL, S9B.rounds[2].contests, late_until=LATE_UNTIL
        ),
        id="individual-tee-window-contests-late-until",
    ),
    pytest.param(
        RoundSetup(
            "t3", 6, *on(WHITE), OPENS, CLOSES, T3.rounds[0].contests, format=T3.rounds[0].format
        ),
        RoundSetup(
            "t3", 6, *on(WHITE), OPENS, CLOSES, T3.rounds[1].contests, format=T3.rounds[2].format
        ),
        id="team-format-and-contests",
    ),
]


@pytest.mark.parametrize(("created", "changed"), CHANGES)
def test_r14_change_round_replaces_a_draft(
    database: Engine, created: RoundSetup, changed: RoundSetup
) -> None:
    create_round(database, created)
    before = everything_loaded(database)
    change_round(database, changed)
    assert window(database, changed) == ("draft", changed.opens_at, changed.closes_at)
    open_round(database, changed.season_id, changed.number)
    facts = before[changed.season_id]
    expected = replace(facts, rounds=(*facts.rounds, opened(database, changed)))
    assert everything_loaded(database) == before | {changed.season_id: expected}


@pytest.mark.parametrize(
    ("season_id", "number"),
    [
        pytest.param("t3-open", 1, id="open"),
        pytest.param("t3", 1, id="closed"),
        pytest.param("t3", 9, id="no-round"),
    ],
)
def test_r14_r15_round_that_has_opened_does_not_change(
    database: Engine, season_id: str, number: int
) -> None:
    """A bestball round 1 changed to scramble would take team cards beside its players' cards."""
    setup = RoundSetup(
        season_id,
        number,
        *on(WHITE),
        OPENS,
        CLOSES,
        T3.rounds[2].contests,
        format=T3.rounds[2].format,
    )
    assert_refused(database, lambda: change_round(database, setup), "is not a draft")


MISFIT_CHANGES = [
    pytest.param(
        RoundSetup(
            "s9b",
            5,
            *on(S9B_TEE),
            OPENS,
            CLOSES,
            S9B.rounds[0].contests,
            format=T3.rounds[0].format,
        ),
        "an individual season's round has no format",
        id="r15-format-in-an-individual-season",
    ),
    pytest.param(
        RoundSetup(
            "t3", 6, *on(WHITE), OPENS, CLOSES, S9B.rounds[1].contests, format=T3.rounds[0].format
        ),
        "a team season's contests are field or allplay",
        id="r15-duel-in-a-team-season",
    ),
    pytest.param(
        RoundSetup("s9b", 5, "Nowhere", "White", OPENS, CLOSES, S9B.rounds[0].contests),
        "no tee White of Nowhere",
        id="a-tee-nobody-stored",
    ),
]


@pytest.mark.parametrize(("setup", "match"), MISFIT_CHANGES)
def test_r15_change_that_does_not_fit_its_season_is_refused(
    database: Engine, setup: RoundSetup, match: str
) -> None:
    create_round(
        database, RoundSetup("s9b", 5, *on(S9B_TEE), OPENS, CLOSES, S9B.rounds[0].contests)
    )
    create_round(
        database,
        RoundSetup(
            "t3", 6, *on(WHITE), OPENS, CLOSES, T3.rounds[0].contests, format=T3.rounds[0].format
        ),
    )
    assert_refused(database, lambda: change_round(database, setup), match)
