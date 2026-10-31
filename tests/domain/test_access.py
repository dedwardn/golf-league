from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from conftest import CLOSED_AT, FLAT_TEE, a_card, a_duel, a_field, an_index_rule

from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.access import (
    accepts_card,
    competitor_of,
    may_reopen,
    pairings_published,
    seed_index_locked,
    sees_round,
    takes_team_card,
    tee_locked,
)
from league.domain.configs import (
    BestballFormat,
    CombinedFormat,
    FormatConfig,
    FoursomeFormat,
    GreensomeFormat,
    ScrambleFormat,
)
from league.domain.facts import Card, Pairing, RoundFacts, SeasonFacts, StandingsRule

OPEN_NOW = CLOSED_AT - timedelta(hours=1)
LATE_UNTIL = CLOSED_AT + timedelta(hours=12)
SECOND = timedelta(seconds=1)
PAR = (4,) * 18
SEEDS = {"ann": 100, "bob": 200, "cam": 150, "dee": 50}
TEAMS = {"ann": "red", "bob": "red", "cam": "blue", "dee": "blue"}
SHARED_BALL = (ScrambleFormat(), GreensomeFormat(), FoursomeFormat())
OWN_BALL = (BestballFormat(), CombinedFormat())


def cards(*player_ids: str) -> dict[str, Card]:
    return {player_id: a_card(PAR, card_id=player_id) for player_id in player_ids}


def a_round(
    held: dict[str, Card],
    closed_at: datetime | None = None,
    late_until: datetime | None = None,
    number: int = 1,
) -> RoundFacts:
    return RoundFacts(number, FLAT_TEE, (), held, {}, (), closed_at, late_until=late_until)


def a_team_round(
    format_: FormatConfig,
    held: dict[str, Card] | None = None,
    team_cards: dict[str, Card] | None = None,
    closed_at: datetime | None = None,
    number: int = 1,
) -> RoundFacts:
    return RoundFacts(
        number,
        FLAT_TEE,
        (),
        held or {},
        {},
        (),
        closed_at,
        format=format_,
        team_cards=team_cards or {},
    )


def a_season(*rounds: RoundFacts, team: bool = False) -> SeasonFacts:
    return SeasonFacts(
        rounds,
        SEEDS,
        frozenset(),
        an_index_rule(),
        StandingsRule(),
        TEAMS,
        mode="team" if team else "individual",
    )


INDIVIDUAL = a_season()
TEAM = a_season(team=True)


def test_r13_an_open_round_accepts_a_first_card() -> None:
    assert accepts_card("ann", a_round(cards("bob")), INDIVIDUAL, OPEN_NOW)


def test_r13_a_second_card_is_rejected() -> None:
    assert not accepts_card("ann", a_round(cards("ann", "bob")), INDIVIDUAL, OPEN_NOW)
    late = a_round(cards("ann", "bob"), CLOSED_AT, LATE_UNTIL)
    assert not accepts_card("ann", late, INDIVIDUAL, CLOSED_AT + SECOND)


def test_r13_a_new_card_is_accepted_after_a_void() -> None:
    held = a_round(cards("ann", "bob"))
    assert not accepts_card("ann", held, INDIVIDUAL, OPEN_NOW)
    voided = replace(held, cards=cards("bob"))
    assert accepts_card("ann", voided, INDIVIDUAL, OPEN_NOW)


def test_r13_a_late_card_is_rejected_without_late_until() -> None:
    closed = a_round(cards("bob"), CLOSED_AT)
    assert not accepts_card("ann", closed, INDIVIDUAL, CLOSED_AT + SECOND)


def test_r13_a_late_card_is_accepted_at_or_before_late_until() -> None:
    closed = a_round(cards("bob"), CLOSED_AT, LATE_UNTIL)
    assert accepts_card("ann", closed, INDIVIDUAL, LATE_UNTIL)
    assert accepts_card("ann", closed, INDIVIDUAL, LATE_UNTIL - SECOND)


def test_r13_a_card_after_late_until_is_rejected() -> None:
    closed = a_round(cards("bob"), CLOSED_AT, LATE_UNTIL)
    assert not accepts_card("ann", closed, INDIVIDUAL, LATE_UNTIL + SECOND)


def test_r13_a_player_without_a_seed_index_is_refused() -> None:
    assert not accepts_card("eve", a_round(cards("bob")), INDIVIDUAL, OPEN_NOW)
    shared = a_team_round(ScrambleFormat(), team_cards=cards("blue"))
    assert not accepts_card("eve", shared, TEAM, OPEN_NOW)


@pytest.mark.parametrize("format_", SHARED_BALL)
def test_r15_a_shared_ball_round_accepts_one_team_card_per_team(format_: FormatConfig) -> None:
    before = a_team_round(format_, team_cards=cards("blue"))
    assert accepts_card("ann", before, TEAM, OPEN_NOW)
    assert accepts_card("bob", before, TEAM, OPEN_NOW)
    after = a_team_round(format_, team_cards=cards("blue", "red"))
    assert not accepts_card("ann", after, TEAM, OPEN_NOW)
    assert not accepts_card("bob", after, TEAM, OPEN_NOW)


@pytest.mark.parametrize("format_", OWN_BALL)
def test_r15_an_own_ball_round_takes_each_player_card_on_its_own(format_: FormatConfig) -> None:
    round_ = a_team_round(format_, held=cards("bob", "cam"))
    assert accepts_card("ann", round_, TEAM, OPEN_NOW)
    assert not accepts_card("bob", round_, TEAM, OPEN_NOW)


@pytest.mark.parametrize(
    ("round_", "takes"),
    [
        *(pytest.param(a_team_round(f), True, id=f.format) for f in SHARED_BALL),
        *(pytest.param(a_team_round(f), False, id=f.format) for f in OWN_BALL),
        pytest.param(a_round({}), False, id="individual"),
    ],
)
def test_r15_only_a_shared_ball_round_takes_team_cards(round_: RoundFacts, takes: bool) -> None:
    assert takes_team_card(round_) is takes


def test_r12_a_player_before_their_own_card_sees_nothing() -> None:
    assert not sees_round("ann", a_round(cards("bob", "cam")), TEAMS, OPEN_NOW)


def test_r12_a_player_after_their_own_card_sees_the_round() -> None:
    assert sees_round("ann", a_round(cards("ann")), TEAMS, OPEN_NOW)


def test_r12_after_close_everyone_sees_the_round() -> None:
    closed = a_round(cards("bob"), CLOSED_AT)
    assert sees_round("ann", closed, TEAMS, CLOSED_AT)
    assert sees_round("eve", closed, TEAMS, CLOSED_AT)


def test_r12_a_closed_round_that_still_takes_late_cards_stays_hidden() -> None:
    closed = a_round(cards("bob"), CLOSED_AT, LATE_UNTIL)
    assert not sees_round("ann", closed, TEAMS, LATE_UNTIL)


def test_r12_the_round_shows_once_late_until_is_past() -> None:
    closed = a_round(cards("bob"), CLOSED_AT, LATE_UNTIL)
    assert sees_round("ann", closed, TEAMS, LATE_UNTIL + SECOND)


def test_r15_a_shared_ball_team_card_shows_the_round_to_both_players() -> None:
    round_ = a_team_round(GreensomeFormat(), team_cards=cards("red"))
    assert sees_round("ann", round_, TEAMS, OPEN_NOW)
    assert sees_round("bob", round_, TEAMS, OPEN_NOW)
    assert not sees_round("cam", round_, TEAMS, OPEN_NOW)


def test_r15_in_an_own_ball_round_a_partners_card_shows_nothing() -> None:
    round_ = a_team_round(BestballFormat(), held=cards("bob"))
    assert not sees_round("ann", round_, TEAMS, OPEN_NOW)


def test_r15_a_team_seasons_seed_index_is_locked_while_any_round_is_closed() -> None:
    assert not seed_index_locked(a_season(team=True))
    assert not seed_index_locked(a_season(a_team_round(BestballFormat()), team=True))
    closed = a_team_round(BestballFormat(), closed_at=CLOSED_AT)
    assert seed_index_locked(a_season(closed, team=True))
    round_two_closed = a_team_round(BestballFormat(), closed_at=CLOSED_AT, number=2)
    assert seed_index_locked(a_season(a_team_round(BestballFormat()), round_two_closed, team=True))


def test_r15_an_individual_seasons_seed_index_never_locks() -> None:
    assert not seed_index_locked(a_season(a_round({}, CLOSED_AT)))


def test_r14_a_tee_without_cards_is_unlocked() -> None:
    assert not tee_locked((a_round({}), a_round({}, number=2)))
    assert not tee_locked(())


def test_r14_a_card_locks_its_tee() -> None:
    assert tee_locked((a_round({}), a_round(cards("ann"), number=2)))


def test_r14_a_team_card_locks_its_tee() -> None:
    assert tee_locked((a_team_round(ScrambleFormat(), team_cards=cards("red")),))


def a_duel_round(pairings: dict[str, tuple[Pairing, ...]], *duels: str) -> RoundFacts:
    contests = (*(a_duel(key) for key in duels), a_field())
    return RoundFacts(1, FLAT_TEE, contests, {}, pairings, (), None)


A_PAIRING = (Pairing(("ann",), ("bob",)),)


def test_r14_round_without_a_duel_opens_without_pairings() -> None:
    assert pairings_published(a_duel_round({}))


def test_r14_duel_round_opens_once_its_pairings_are_published() -> None:
    assert pairings_published(a_duel_round({"bb": A_PAIRING}, "bb"))


@pytest.mark.parametrize(
    "round_",
    [
        pytest.param(a_duel_round({}, "bb"), id="no-pairings"),
        pytest.param(a_duel_round({"bb": ()}, "bb"), id="empty-pairings"),
        pytest.param(a_duel_round({"bb": A_PAIRING}, "bb", "duel"), id="one-of-two-duels"),
    ],
)
def test_r14_duel_round_waits_for_its_pairings(round_: RoundFacts) -> None:
    assert not pairings_published(round_)


def test_r13_closed_round_with_on_time_cards_reopens() -> None:
    on_time = {"ann": a_card(PAR, "ann", CLOSED_AT)}
    team_on_time = {"red": a_card(PAR, "red", CLOSED_AT)}
    assert may_reopen(a_round(on_time, CLOSED_AT))
    assert may_reopen(a_team_round(ScrambleFormat(), team_cards=team_on_time, closed_at=CLOSED_AT))


def test_r13_open_round_does_not_reopen() -> None:
    assert not may_reopen(a_round(cards("ann")))


def test_r13_closed_round_with_a_late_card_does_not_reopen() -> None:
    late = a_card(PAR, "bob", CLOSED_AT + SECOND)
    assert not may_reopen(a_round({**cards("ann"), "bob": late}, CLOSED_AT, LATE_UNTIL))


def test_r13_closed_round_with_a_late_team_card_does_not_reopen() -> None:
    late = {"red": a_card(PAR, "red", CLOSED_AT + SECOND)}
    assert not may_reopen(a_team_round(ScrambleFormat(), team_cards=late, closed_at=CLOSED_AT))


def test_r15_a_players_competitor_is_their_team_in_a_team_season() -> None:
    assert competitor_of("ann", T3) == "red"


def test_r15_a_player_outside_a_team_season_is_no_competitor() -> None:
    assert competitor_of("nobody", T3) is None


def test_r15_a_players_competitor_is_themself_in_an_individual_season() -> None:
    # ann has a season team in S9B, which a teambonus reads and which earns nothing else.
    assert competitor_of("ann", S9B) == "ann"


def test_r10_a_player_without_a_seed_index_is_no_competitor() -> None:
    assert competitor_of("nobody", S9B) is None
