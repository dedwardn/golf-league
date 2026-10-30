from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine
from test_play import t3_open
from test_setup import CLOSES, OPENS, assert_refused, everything_loaded, tee

from fixtures.database import golden_database, load, save_whole_round, save_whole_season
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.facts import RoundFacts, SeasonFacts
from league.domain.season import compute_season
from league.services.play import Submission, admin_season_view, season_view, submit_card
from league.services.run import close_round, open_round, reopen_round
from league.services.setup import RoundSetup, create_round

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
    submit_card(database, Submission("t3", 3, "cam", (5,) * 18), NOW)
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
