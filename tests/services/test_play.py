from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine

from fixtures.database import a_copy, a_template, load, save_whole_round
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.facts import RoundFacts, SeasonFacts
from league.domain.results import SeasonView
from league.domain.season import compute_season
from league.services.play import (
    Submission,
    admin_season_view,
    player_for_link_token,
    season_view,
    submit_card,
)
from league.services.run import void_card

SCORES = (5,) * 18
# After every golden round has closed. An open round takes a card at any time.
NOW = datetime(2026, 3, 2, 20, 0)
T3_CLOSED_1 = T3.rounds[0].closed_at
assert T3_CLOSED_1 is not None
LATE_UNTIL = T3_CLOSED_1 + timedelta(days=1)


def s9b_open() -> SeasonFacts:
    """S9b with ann's card taken out of round 4, which is open."""
    *played, round_4 = S9B.rounds
    cards = {player_id: card for player_id, card in round_4.cards.items() if player_id != "ann"}
    return replace(S9B, rounds=(*played, replace(round_4, cards=cards)))


def t3_open() -> SeasonFacts:
    """T3 with rounds 1 (bestball, hal has no card) and 3 (scramble, blue has none) reopened."""
    round_1, round_2, round_3, round_4, round_5 = T3.rounds
    reopened = (replace(round_1, closed_at=None), round_2, replace(round_3, closed_at=None))
    return replace(T3, rounds=(*reopened, round_4, round_5))


def t3_late() -> SeasonFacts:
    """T3 with round 1 closed but taking late cards for a day."""
    round_1, *rest = T3.rounds
    return replace(T3, rounds=(replace(round_1, late_until=LATE_UNTIL), *rest))


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return a_template(
        tmp_path_factory.mktemp("template"),
        {"s9b-open": s9b_open(), "t3-open": t3_open(), "t3-late": t3_late()},
    )


@pytest.fixture
def database(template: Path, tmp_path: Path) -> Iterator[Engine]:
    engine = a_copy(template, tmp_path)
    yield engine
    engine.dispose()


def submit(
    engine: Engine, season_id: str, round_number: int, player_id: str, now: datetime = NOW
) -> None:
    submit_card(engine, Submission(season_id, round_number, player_id, SCORES), now)


def assert_refused(
    engine: Engine, season_id: str, round_number: int, player_id: str, now: datetime = NOW
) -> None:
    """A ValueError from the service, not the database's, and nothing stored."""
    before = load(engine, season_id)
    with pytest.raises(ValueError, match="does not take this card"):
        submit(engine, season_id, round_number, player_id, now)
    assert load(engine, season_id) == before


def stored_round(engine: Engine, season_id: str, number: int) -> RoundFacts:
    return next(round_ for round_ in load(engine, season_id).rounds if round_.number == number)


def test_link_token_finds_its_player(database: Engine) -> None:
    assert player_for_link_token(database, "ann-link") == "ann"
    assert player_for_link_token(database, "hal-link") == "hal"


def test_unknown_link_token_finds_nobody(database: Engine) -> None:
    assert player_for_link_token(database, "nobody-link") is None


def test_r13_card_in_an_open_round_is_stored(database: Engine) -> None:
    submit(database, "s9b-open", 4, "ann")
    card = stored_round(database, "s9b-open", 4).cards["ann"]
    assert (card.scores, card.submitted_at) == (SCORES, NOW)


def test_r13_second_card_is_refused(database: Engine) -> None:
    assert_refused(database, "s9b", 4, "ann")


def test_r13_card_after_close_without_late_until_is_refused(database: Engine) -> None:
    assert_refused(database, "t3", 1, "hal")


def test_r13_late_card_at_late_until_is_stored(database: Engine) -> None:
    submit(database, "t3-late", 1, "hal", LATE_UNTIL)
    card = stored_round(database, "t3-late", 1).cards["hal"]
    assert (card.scores, card.submitted_at) == (SCORES, LATE_UNTIL)


def test_r13_late_card_after_late_until_is_refused(database: Engine) -> None:
    assert_refused(database, "t3-late", 1, "hal", LATE_UNTIL + timedelta(seconds=1))


def test_r13_card_for_a_draft_round_is_refused(database: Engine) -> None:
    draft = replace(S9B.rounds[2], number=5, cards={}, closed_at=None)
    with database.begin() as connection:
        save_whole_round(connection, "s9b", draft, state="draft")
    assert_refused(database, "s9b", 5, "ann")


def test_r13_card_from_a_player_without_a_seed_index_is_refused(database: Engine) -> None:
    assert_refused(database, "s9b", 4, "gus")


def test_r13_new_card_after_a_void_is_stored(database: Engine) -> None:
    void_card(database, "s9b", "r4-ann")
    submit(database, "s9b", 4, "ann")
    card = stored_round(database, "s9b", 4).cards["ann"]
    assert (card.scores, card.submitted_at) == (SCORES, NOW)


def test_r15_shared_ball_round_stores_the_team_card(database: Engine) -> None:
    submit(database, "t3-open", 3, "cam")
    round_3 = stored_round(database, "t3-open", 3)
    card = round_3.team_cards["blue"]
    assert (card.scores, card.submitted_at) == (SCORES, NOW)
    assert "cam" not in round_3.cards


def test_r15_partner_card_after_the_team_card_is_refused(database: Engine) -> None:
    submit(database, "t3-open", 3, "cam")
    assert_refused(database, "t3-open", 3, "dee")


def test_r15_own_ball_round_stores_the_players_card(database: Engine) -> None:
    submit(database, "t3-open", 1, "hal")
    round_1 = stored_round(database, "t3-open", 1)
    card = round_1.cards["hal"]
    assert (card.scores, card.submitted_at) == (SCORES, NOW)
    assert round_1.team_cards == {}


def test_r15_own_ball_round_refuses_a_second_card(database: Engine) -> None:
    assert_refused(database, "t3-open", 1, "ann")


def computed(
    engine: Engine, season_id: str, numbers: tuple[int, ...], competitor: str
) -> SeasonView:
    """compute_season over the stored season, as a viewer of that competitor sees those rounds."""
    view = compute_season(load(engine, season_id))
    rounds = tuple(r for r in view.rounds if r.awards.number in numbers)
    return replace(view, rounds=rounds, viewer_competitor=competitor)


def test_r12_player_without_a_card_does_not_see_the_open_round(database: Engine) -> None:
    assert season_view(database, "s9b-open", "ann", NOW) == computed(
        database, "s9b-open", (1, 2, 3), "ann"
    )


def test_r12_player_sees_the_open_round_once_their_card_is_in(database: Engine) -> None:
    submit(database, "s9b-open", 4, "ann")
    seen = season_view(database, "s9b-open", "ann", NOW)
    assert seen == computed(database, "s9b-open", (1, 2, 3, 4), "ann")


def test_r12_closed_round_is_seen_by_everyone(database: Engine) -> None:
    assert season_view(database, "t3", "hal", NOW) == computed(
        database, "t3", (1, 2, 3, 4, 5), "gold"
    )


def test_r12_closed_round_taking_late_cards_is_hidden_from_a_player_without_a_card(
    database: Engine,
) -> None:
    now = LATE_UNTIL - timedelta(hours=1)
    assert season_view(database, "t3-late", "hal", now) == computed(
        database, "t3-late", (2, 3, 4, 5), "gold"
    )
    assert season_view(database, "t3-late", "ann", now) == computed(
        database, "t3-late", (1, 2, 3, 4, 5), "red"
    )


def test_r12_r15_partner_sees_the_round_once_the_team_card_is_in(database: Engine) -> None:
    before = season_view(database, "t3-open", "dee", NOW)
    assert before == computed(database, "t3-open", (1, 2, 4, 5), "blue")
    submit(database, "t3-open", 3, "cam")
    after = season_view(database, "t3-open", "dee", NOW)
    assert after == computed(database, "t3-open", (1, 2, 3, 4, 5), "blue")


def test_r15_a_viewer_is_their_team_in_a_team_season(database: Engine) -> None:
    assert season_view(database, "t3", "ann", NOW).viewer_competitor == "red"


def test_r15_a_player_outside_a_team_season_is_no_competitor(database: Engine) -> None:
    assert season_view(database, "t3", "nobody", NOW).viewer_competitor is None


def test_r10_a_viewer_is_themself_in_an_individual_season(database: Engine) -> None:
    assert season_view(database, "s9b", "ann", NOW).viewer_competitor == "ann"


def test_r10_a_player_outside_an_individual_season_is_no_competitor(database: Engine) -> None:
    assert season_view(database, "s9b", "hal", NOW).viewer_competitor is None


def test_r12_admin_sees_every_round(database: Engine) -> None:
    assert 4 not in [r.awards.number for r in season_view(database, "s9b-open", "ann", NOW).rounds]
    seen = admin_season_view(database, "s9b-open")
    assert seen == compute_season(load(database, "s9b-open"))
    assert 4 in [r.awards.number for r in seen.rounds]
