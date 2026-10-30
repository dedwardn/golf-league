from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest
from sqlalchemy import Engine, select
from test_play import SCORES, stored_round, t3_open
from test_setup import CLOSES, OPENS, assert_refused, everything_loaded, tee

from fixtures.database import golden_database, load, save_whole_round, save_whole_season
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.facts import ManualAward, RoundFacts, SeasonFacts
from league.domain.season import compute_season
from league.services.play import Submission, admin_season_view, season_view, submit_card
from league.services.run import (
    add_manual_award,
    close_round,
    correct_card,
    open_round,
    reopen_round,
    void_card,
)
from league.services.setup import RoundSetup, create_round
from league.store.schema import cards

# After every golden round has closed, so each card stays on time.
NOW = datetime(2026, 3, 9, 22, 0)


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    engine = golden_database(tmp_path)
    with engine.begin() as connection:
        save_whole_season(connection, "t3-open", t3_open())
    yield engine
    engine.dispose()


def with_round(facts: SeasonFacts, changed: RoundFacts) -> SeasonFacts:
    """The season with the round of that number replaced, or added after the others."""
    kept = tuple(round_ for round_ in facts.rounds if round_.number != changed.number)
    return replace(facts, rounds=tuple(sorted((*kept, changed), key=lambda r: r.number)))


def draft_allplay(engine: Engine) -> RoundSetup:
    """s9b's round 5 as a draft without a duel. t3 and t3-open have a round 5 of their own."""
    setup = RoundSetup("s9b", 5, "s9b-r1", OPENS, CLOSES, S9B.rounds[2].contests)
    create_round(engine, setup)
    return setup


def test_r13_open_round_opens_a_draft(database: Engine) -> None:
    setup = draft_allplay(database)
    before = everything_loaded(database)
    open_round(database, "s9b", 5)
    opened = RoundFacts(5, tee(database, "s9b-r1"), setup.contests, {}, {}, (), None)
    assert everything_loaded(database) == before | {"s9b": with_round(before["s9b"], opened)}


@pytest.mark.parametrize(
    "number",
    [pytest.param(4, id="open"), pytest.param(1, id="closed"), pytest.param(9, id="no-round")],
)
def test_r13_round_that_is_not_a_draft_does_not_open(database: Engine, number: int) -> None:
    assert_refused(database, lambda: open_round(database, "s9b", number), "is not a draft")


def test_r14_duel_round_without_published_pairings_does_not_open(database: Engine) -> None:
    create_round(database, RoundSetup("s9b", 5, "s9b-r2", OPENS, CLOSES, S9B.rounds[1].contests))
    assert_refused(database, lambda: open_round(database, "s9b", 5), "unpublished pairings")


def test_r14_duel_round_with_published_pairings_opens(database: Engine) -> None:
    published = replace(S9B.rounds[1], number=5, cards={}, closed_at=None)
    with database.begin() as connection:
        save_whole_round(connection, "s9b", published, state="draft")
    before = load(database, "s9b")
    open_round(database, "s9b", 5)
    assert load(database, "s9b") == with_round(before, published)


def test_r13_close_round_records_closed_at(database: Engine) -> None:
    before = everything_loaded(database)
    close_round(database, "t3-open", 1, NOW)
    closed = replace(before["t3-open"].rounds[0], closed_at=NOW)
    assert everything_loaded(database) == before | {
        "t3-open": with_round(before["t3-open"], closed)
    }


@pytest.mark.parametrize(
    "number",
    [pytest.param(5, id="draft"), pytest.param(1, id="closed"), pytest.param(9, id="no-round")],
)
def test_r13_round_that_is_not_open_does_not_close(database: Engine, number: int) -> None:
    draft_allplay(database)
    assert_refused(database, lambda: close_round(database, "s9b", number, NOW), "is not open")


def test_r13_closed_round_with_only_on_time_cards_reopens(database: Engine) -> None:
    before = everything_loaded(database)
    reopen_round(database, "t3", 5)
    reopened = replace(T3.rounds[4], closed_at=None)
    assert everything_loaded(database) == before | {"t3": with_round(T3, reopened)}


def test_r13_r10_reopened_round_is_in_no_table_until_it_closes_again(database: Engine) -> None:
    reopen_round(database, "t3", 5)
    reopened = compute_season(with_round(T3, replace(T3.rounds[4], closed_at=None)))
    assert admin_season_view(database, "t3") == reopened
    assert reopened.standings != compute_season(T3).standings
    close_round(database, "t3", 5, NOW)
    closed_again = with_round(T3, replace(T3.rounds[4], closed_at=NOW))
    assert load(database, "t3") == closed_again
    assert admin_season_view(database, "t3") == compute_season(T3)


def test_r13_reopened_round_takes_a_card_from_a_player_who_saw_its_results(
    database: Engine,
) -> None:
    """blue handed in no team card for round 3, and cam sees it while it is closed (R12)."""
    seen = season_view(database, "t3", "cam", NOW)
    assert 3 in {round_view.awards.number for round_view in seen.rounds}
    reopen_round(database, "t3", 3)
    submit_card(database, Submission("t3", 3, "cam", SCORES), NOW)
    assert load(database, "t3").rounds[2].team_cards["blue"].submitted_at == NOW


REFUSED_REOPENS = [
    pytest.param("s9b", 2, id="late-card"),
    pytest.param("t3", 4, id="late-team-card"),
    pytest.param("s9b", 4, id="open"),
    pytest.param("s9b", 5, id="draft"),
    pytest.param("s9b", 9, id="no-round"),
]


@pytest.mark.parametrize(("season_id", "number"), REFUSED_REOPENS)
def test_r13_round_that_is_not_closed_or_has_a_late_card_does_not_reopen(
    database: Engine, season_id: str, number: int
) -> None:
    draft_allplay(database)
    assert_refused(database, lambda: reopen_round(database, season_id, number), "does not reopen")


def correct(engine: Engine, season_id: str, card_id: str) -> None:
    correct_card(engine, season_id, card_id, SCORES)


CARD_ACTIONS = [pytest.param(correct, id="correct"), pytest.param(void_card, id="void")]


@pytest.mark.parametrize(
    ("season_id", "number", "player_id"),
    [
        pytest.param("s9b", 2, "dee", id="late-card-in-a-closed-round"),
        pytest.param("s9b", 4, "ann", id="open-round"),
        pytest.param("t3-open", 1, "ann", id="own-ball-card-in-a-team-season"),
    ],
)
def test_r13_correct_card_replaces_its_scores_and_keeps_submitted_at(
    database: Engine, season_id: str, number: int, player_id: str
) -> None:
    before = everything_loaded(database)
    round_ = stored_round(database, season_id, number)
    card = round_.cards[player_id]
    correct_card(database, season_id, card.card_id, SCORES)
    corrected = replace(round_, cards={**round_.cards, player_id: replace(card, scores=SCORES)})
    assert everything_loaded(database) == before | {
        season_id: with_round(before[season_id], corrected)
    }


def test_r15_corrected_team_card_stays_the_teams_and_gives_no_player_a_card(
    database: Engine,
) -> None:
    before = everything_loaded(database)
    round_ = T3.rounds[2]
    team_cards = {**round_.team_cards, "red": replace(round_.team_cards["red"], scores=SCORES)}
    correct_card(database, "t3", "r3-red", SCORES)
    corrected = replace(round_, team_cards=team_cards)
    assert everything_loaded(database) == before | {"t3": with_round(T3, corrected)}


@pytest.mark.parametrize(
    ("scores", "match"),
    [
        pytest.param((5,) * 17, "18 scores", id="too-few"),
        pytest.param((0, *(5,) * 17), "1 or more", id="a-zero"),
    ],
)
def test_r13_correction_with_a_bad_card_is_refused(
    database: Engine, scores: tuple[int, ...], match: str
) -> None:
    assert_refused(database, lambda: correct_card(database, "s9b", "r1-ann", scores), match)


def test_r13_void_keeps_the_row_and_leaves_the_card_out(database: Engine) -> None:
    before = everything_loaded(database)
    round_ = S9B.rounds[0]
    void_card(database, "s9b", "r1-ann")
    kept = {player_id: card for player_id, card in round_.cards.items() if player_id != "ann"}
    assert everything_loaded(database) == before | {
        "s9b": with_round(S9B, replace(round_, cards=kept))
    }
    where = (cards.c.season_id == "s9b", cards.c.card_id == "r1-ann")
    with database.connect() as connection:
        assert connection.execute(select(cards.c.voided).where(*where)).scalar_one()


def test_r15_void_leaves_the_team_card_out(database: Engine) -> None:
    before = everything_loaded(database)
    round_ = T3.rounds[2]
    void_card(database, "t3", "r3-red")
    kept = {team_id: card for team_id, card in round_.team_cards.items() if team_id != "red"}
    assert everything_loaded(database) == before | {
        "t3": with_round(T3, replace(round_, team_cards=kept))
    }


@pytest.mark.parametrize("action", CARD_ACTIONS)
def test_r13_correction_and_void_change_only_their_season(
    database: Engine, action: Callable[[Engine, str, str], None]
) -> None:
    """t3 and t3-open hold cards of the same id."""
    action(database, "t3-open", "r1-ann")
    assert load(database, "t3") == T3


@pytest.mark.parametrize("action", CARD_ACTIONS)
@pytest.mark.parametrize(
    ("season_id", "card_id"),
    [
        pytest.param("s9b", "nobody", id="unknown"),
        pytest.param("s9b", "r1-ann", id="voided"),
        pytest.param("t3", "r4-ann", id="counted-in-another-season"),
    ],
)
def test_r13_card_that_is_not_counted_is_neither_corrected_nor_voided(
    database: Engine,
    action: Callable[[Engine, str, str], None],
    season_id: str,
    card_id: str,
) -> None:
    void_card(database, "s9b", "r1-ann")
    assert_refused(database, lambda: action(database, season_id, card_id), "no counted card")


def test_r13_card_voided_in_a_closed_round_is_not_replaced(database: Engine) -> None:
    """A new card is accepted under the same rule, and this round takes no more."""
    void_card(database, "t3", "r1-ann")
    submission = Submission("t3", 1, "ann", SCORES)
    assert_refused(database, lambda: submit_card(database, submission, NOW), "does not take")


def test_r15_new_team_card_after_a_void_is_stored(database: Engine) -> None:
    void_card(database, "t3-open", "r3-red")
    submit_card(database, Submission("t3-open", 3, "bob", SCORES), NOW)
    round_3 = stored_round(database, "t3-open", 3)
    assert round_3.team_cards["red"].scores == SCORES
    assert round_3.cards == {}


@pytest.mark.parametrize(
    ("number", "key"),
    [pytest.param(1, "longest-drive", id="closed"), pytest.param(4, "bb", id="open")],
)
def test_r9_manual_award_is_added_after_the_rounds_earlier_ones(
    database: Engine, number: int, key: str
) -> None:
    """ann sorts before the award already there, and the key is a label a round may repeat."""
    before = everything_loaded(database)
    award = ManualAward("ann", key, Fraction(-1, 2))
    add_manual_award(database, "s9b", number, award)
    round_ = S9B.rounds[number - 1]
    added = replace(round_, manual=(*round_.manual, award))
    assert everything_loaded(database) == before | {"s9b": with_round(S9B, added)}


def test_r9_r15_team_season_manual_award_names_a_team(database: Engine) -> None:
    before = everything_loaded(database)
    award = ManualAward("gold", "adjustment", Fraction(1))
    add_manual_award(database, "t3", 1, award)
    added = replace(T3.rounds[0], manual=(award,))
    assert everything_loaded(database) == before | {"t3": with_round(T3, added)}


@pytest.mark.parametrize(
    ("season_id", "competitor_id"),
    [
        pytest.param("s9b", "gus", id="unseeded-player"),
        pytest.param("s9b", "east", id="season-team-in-an-individual-season"),
        pytest.param("t3", "ann", id="player-in-a-team-season"),
    ],
)
def test_r9_manual_award_naming_no_competitor_is_refused(
    database: Engine, season_id: str, competitor_id: str
) -> None:
    award = ManualAward(competitor_id, "adjustment", Fraction(1))
    assert_refused(
        database, lambda: add_manual_award(database, season_id, 1, award), "names no competitor"
    )


@pytest.mark.parametrize("number", [pytest.param(5, id="draft"), pytest.param(9, id="no-round")])
def test_r9_manual_award_in_a_draft_or_missing_round_is_refused(
    database: Engine, number: int
) -> None:
    draft_allplay(database)
    award = ManualAward("ann", "adjustment", Fraction(1))
    assert_refused(
        database, lambda: add_manual_award(database, "s9b", number, award), "no open or closed"
    )
