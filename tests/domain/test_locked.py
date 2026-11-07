from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from fixtures.season import SEASON as S9B
from fixtures.team_season import t3_open
from league.domain.facts import RoundHeading, SeasonFacts
from league.domain.locked import LockedRound, LockedTeam, locked_round
from league.domain.season import compute_season

NOW = datetime(2026, 3, 2, 20, 0)
CLOSES = NOW + timedelta(days=4)


def locked(facts: SeasonFacts, number: int, viewer_id: str) -> LockedRound | None:
    """The round before playing as a service hands it in, over compute_season's whole view."""
    return locked_round(facts, compute_season(facts), RoundHeading(number, CLOSES), viewer_id, NOW)


def test_r12_hal_reads_round_1_with_gold_one_of_two_cards() -> None:
    """team_members reads red, blue, green, gold in T3, so team id order has to be chosen."""
    view = locked(t3_open(), 1, "hal")
    assert view is not None
    assert view == LockedRound(
        1,
        CLOSES,
        (
            LockedTeam("blue", "score_in", mine=False),
            LockedTeam("gold", "one_of_two", mine=True),
            LockedTeam("green", "score_in", mine=False),
            LockedTeam("red", "score_in", mine=False),
        ),
        takes_card=True,
    )
    assert view.with_score == 3


def test_r12_cam_reads_round_3_with_blue_not_yet() -> None:
    """A shared-ball team's players hold its one team card together, so it is never one of two."""
    view = locked(t3_open(), 3, "cam")
    assert view is not None
    assert view == LockedRound(
        3,
        CLOSES,
        (
            LockedTeam("blue", "not_yet", mine=True),
            LockedTeam("gold", "score_in", mine=False),
            LockedTeam("green", "score_in", mine=False),
            LockedTeam("red", "score_in", mine=False),
        ),
        takes_card=True,
    )
    assert view.with_score == 3


def test_r17_own_ball_team_without_cards_reads_not_yet() -> None:
    facts = t3_open()
    round_1, *rest = facts.rounds
    cards = {player_id: card for player_id, card in round_1.cards.items() if player_id != "gus"}
    view = locked(replace(facts, rounds=(replace(round_1, cards=cards), *rest)), 1, "hal")
    assert view is not None
    assert view == LockedRound(
        1,
        CLOSES,
        (
            LockedTeam("blue", "score_in", mine=False),
            LockedTeam("gold", "not_yet", mine=True),
            LockedTeam("green", "score_in", mine=False),
            LockedTeam("red", "score_in", mine=False),
        ),
        takes_card=True,
    )
    assert view.with_score == 3


def test_r12_viewer_outside_the_season_reads_the_round_without_register_card() -> None:
    """gold is one of two cards here with no viewer of its own, so the status is the team's."""
    view = locked(t3_open(), 1, "ivy")
    assert view is not None
    assert view == LockedRound(
        1,
        CLOSES,
        (
            LockedTeam("blue", "score_in", mine=False),
            LockedTeam("gold", "one_of_two", mine=False),
            LockedTeam("green", "score_in", mine=False),
            LockedTeam("red", "score_in", mine=False),
        ),
        takes_card=False,
    )
    assert (view.with_score, view.takes_card) == (3, False)


@pytest.mark.parametrize(("number", "viewer_id"), [(1, "gus"), (3, "ann")])
def test_r12_viewer_who_sees_the_round_reads_none(number: int, viewer_id: str) -> None:
    """gus's own card is in round 1, and ann's team red has its team card in round 3."""
    assert locked(t3_open(), number, viewer_id) is None


def test_section_7_no_round_before_playing_in_an_individual_season_until_s21() -> None:
    *played, round_4 = S9B.rounds
    cards = {player_id: card for player_id, card in round_4.cards.items() if player_id != "ann"}
    facts = replace(S9B, rounds=(*played, replace(round_4, cards=cards)))
    assert "ann" not in facts.rounds[3].cards
    assert locked(facts, 4, "ann") is None
