from dataclasses import replace
from datetime import datetime
from fractions import Fraction

import pytest

from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from fixtures.team_season import t3_open
from league.domain.configs import AllplayConfig
from league.domain.facts import SeasonFacts
from league.domain.results import Gap, RoundTotal, StandingsRow
from league.domain.round_result import (
    RankedTeam,
    ResultAllplay,
    ResultPlayer,
    ResultTeam,
    RoundResult,
    round_result,
)
from league.domain.season import compute_season

NOW = datetime(2026, 3, 2, 20, 0)
COURSE = "Trinity Forest Golf Club"


def result(facts: SeasonFacts, number: int, viewer_id: str) -> RoundResult | None:
    """The round result as a service hands it in, over compute_season's whole view."""
    return round_result(facts, compute_season(facts), number, viewer_id, NOW)


def totals(*points: Fraction | None) -> tuple[RoundTotal, ...]:
    """A row's round totals from round 1 on, none of them dropped."""
    return tuple(RoundTotal(number, total, False) for number, total in enumerate(points, start=1))


ROUND_1_FIELD = ResultAllplay(
    (
        RankedTeam("blue", 66, Fraction(2), 100, mine=False),
        RankedTeam("green", 67, Fraction(1, 2), 25, mine=False),
        RankedTeam("red", 67, Fraction(1, 2), 25, mine=False),
    ),
    ("gold",),
)


def test_section_7_gus_reads_round_5_with_gold_beating_every_team() -> None:
    """Gold's 8 on hole 18 nets +4 and counts as net double bogey, so 66 reads 64."""
    view = result(T3, 5, "gus")
    assert view is not None
    assert view.allplay.without_score_text is None
    assert view == RoundResult(
        5,
        COURSE,
        "Blue",
        ResultTeam("gold", "foursome", 64, (), team_gross=79, team_playing_handicap=13),
        ResultAllplay(
            (
                RankedTeam("gold", 64, Fraction(3), 100, mine=True),
                RankedTeam("green", 65, Fraction(2), 67, mine=False),
                RankedTeam("blue", 66, Fraction(1, 2), 17, mine=False),
                RankedTeam("red", 66, Fraction(1, 2), 17, mine=False),
            ),
            (),
        ),
        Fraction(3),
        StandingsRow(
            3,
            "gold",
            Fraction(25, 4),
            3,
            totals(None, Fraction(5, 2), Fraction(9, 4), Fraction(3, 2)),
            Gap(Fraction(12, 10), 2),
        ),
        StandingsRow(
            2,
            "gold",
            Fraction(37, 4),
            4,
            totals(None, Fraction(5, 2), Fraction(9, 4), Fraction(3, 2), Fraction(3)),
            Gap(Fraction(67, 10), 1),
        ),
    )


def test_section_7_hal_reads_round_2_with_each_players_net_capped_and_summed() -> None:
    """Decision 1 of S16c1: hal's 9 on hole 18 counts as 6, so 69 and 74 read 141, not 143."""
    view = result(T3, 2, "hal")
    assert view is not None
    assert view == RoundResult(
        2,
        COURSE,
        "White",
        ResultTeam(
            "gold",
            "combined",
            141,
            (ResultPlayer("hal", 87, 18), ResultPlayer("gus", 82, 8)),
            team_gross=None,
            team_playing_handicap=None,
        ),
        ResultAllplay(
            (
                RankedTeam("red", 140, Fraction(3), 100, mine=False),
                RankedTeam("blue", 141, Fraction(3, 2), 50, mine=False),
                RankedTeam("gold", 141, Fraction(3, 2), 50, mine=True),
                RankedTeam("green", 142, Fraction(0), 0, mine=False),
            ),
            (),
        ),
        Fraction(5, 2),
        StandingsRow(4, "gold", Fraction(0), 0, totals(None), Gap(Fraction(8, 10), 2)),
        StandingsRow(
            4, "gold", Fraction(5, 2), 1, totals(None, Fraction(5, 2)), Gap(Fraction(3, 10), 3)
        ),
    )
    assert (view.allplay.beaten_text, view.allplay.others) == ("1.5", 3)


def test_r10_ann_reads_round_2_from_2nd_to_1st_with_no_gap() -> None:
    view = result(T3, 2, "ann")
    assert view is not None
    assert (view.points, view.points_text) == (Fraction(7), "7.0")
    assert view.before is not None
    assert view.after is not None
    assert (view.before.position, view.after.position, view.after.gap) == (2, 1, None)


def test_r10_ann_reads_round_5_without_reds_manual_award() -> None:
    view = result(T3, 5, "ann")
    assert view is not None
    assert view.points == Fraction(1, 2)


def test_r17_a_late_team_card_has_no_score() -> None:
    view = result(T3, 4, "ann")
    assert view is not None
    assert view.allplay == ResultAllplay(
        (
            RankedTeam("red", 67, Fraction(2), 100, mine=True),
            RankedTeam("gold", 68, Fraction(1), 50, mine=False),
            RankedTeam("blue", 69, Fraction(0), 0, mine=False),
        ),
        ("green",),
    )
    assert view.allplay.without_score_text == "green have no score this round."


def test_section_7_gus_reads_round_1_without_a_score_and_only_his_place_after() -> None:
    """No closed round comes before round 1, so there is no place before it (the owner)."""
    view = result(T3, 1, "gus")
    assert view is not None
    assert view == RoundResult(
        1,
        COURSE,
        "White",
        ResultTeam(
            "gold",
            "bestball",
            None,
            (ResultPlayer("gus", 72, 7), ResultPlayer("hal", None, 15)),
            team_gross=None,
            team_playing_handicap=None,
        ),
        ROUND_1_FIELD,
        None,
        None,
        StandingsRow(4, "gold", Fraction(0), 0, totals(None), Gap(Fraction(8, 10), 2)),
    )
    assert (view.points_text, view.allplay.beaten_text) == ("\N{EN DASH}", None)


def test_section_7_a_shared_ball_team_without_its_team_card_reads_its_strokes() -> None:
    view = result(T3, 3, "cam")
    assert view is not None
    assert view.team == ResultTeam(
        "blue", "scramble", None, (), team_gross=None, team_playing_handicap=4
    )


def test_r12_gus_reads_open_round_1_once_his_card_is_in() -> None:
    assert result(t3_open(), 1, "gus") == RoundResult(
        1,
        COURSE,
        "White",
        ResultTeam(
            "gold",
            "bestball",
            None,
            (ResultPlayer("gus", 72, 7), ResultPlayer("hal", None, 15)),
            team_gross=None,
            team_playing_handicap=None,
        ),
        ROUND_1_FIELD,
        None,
        None,
        None,
    )


def test_r10_ann_reads_open_round_3_with_its_points_and_no_place() -> None:
    """Blue has no team card, so red beats one of the other two and ties gold."""
    view = result(t3_open(), 3, "ann")
    assert view is not None
    assert view == RoundResult(
        3,
        COURSE,
        "Blue",
        ResultTeam("red", "scramble", 70, (), team_gross=72, team_playing_handicap=2),
        ResultAllplay(
            (
                RankedTeam("gold", 70, Fraction(3, 2), 75, mine=False),
                RankedTeam("red", 70, Fraction(3, 2), 75, mine=True),
                RankedTeam("green", 73, Fraction(0), 0, mine=False),
            ),
            ("blue",),
        ),
        Fraction(9, 4),
        None,
        None,
    )
    assert (view.points_text, view.allplay.beaten_text, view.allplay.others) == ("2.3", "1.5", 2)
    assert view.team is not None
    # Only the template reads these two otherwise, and this case decides both.
    assert (view.team.team_gross, view.allplay.ranked[1].bar_percent) == (72, 75)


def test_section_7_a_viewer_outside_the_season_reads_the_ranking_alone() -> None:
    assert result(T3, 1, "ivy") == RoundResult(
        1, COURSE, "White", None, ROUND_1_FIELD, None, None, None
    )


def test_section_7_teams_without_a_score_are_named_in_team_id_order() -> None:
    round_1, *rest = T3.rounds
    cards = {player_id: card for player_id, card in round_1.cards.items() if player_id != "dee"}
    view = result(replace(T3, rounds=(replace(round_1, cards=cards), *rest)), 1, "gus")
    assert view is not None
    assert view.allplay.without_score == ("blue", "gold")
    assert view.allplay.without_score_text == "blue and gold have no score this round."


@pytest.mark.parametrize(("number", "viewer_id"), [(1, "hal"), (6, "gus")])
def test_r12_no_result_for_a_viewer_it_is_hidden_from_or_a_round_not_in_the_season(
    number: int, viewer_id: str
) -> None:
    """hal has no card in open round 1, and round 6 does not exist."""
    assert result(t3_open(), number, viewer_id) is None


def test_section_7_no_round_result_in_an_individual_season_until_s21() -> None:
    assert result(S9B, 1, "ann") is None


def test_r9_a_lone_team_reads_no_ranking_and_no_points() -> None:
    """Only red's team card is in, so there is no one to play and no allplay award."""
    facts = t3_open()
    round_1, round_2, round_3, *rest = facts.rounds
    alone = replace(round_3, team_cards={"red": round_3.team_cards["red"]})
    view = result(replace(facts, rounds=(round_1, round_2, alone, *rest)), 3, "ann")
    assert view is not None
    assert view == RoundResult(
        3,
        COURSE,
        "Blue",
        ResultTeam("red", "scramble", 70, (), team_gross=72, team_playing_handicap=2),
        ResultAllplay((), ("blue", "gold", "green")),
        None,
        None,
        None,
    )
    assert view.points_text == "\N{EN DASH}"


def test_section_7_a_combined_net_is_read_on_the_stableford_basis_whatever_the_allplay_basis() -> (
    None
):
    round_1, round_2, *rest = T3.rounds
    on_total = replace(round_2, contests=(AllplayConfig("allplay", "total", Fraction(3)),))
    view = result(replace(T3, rounds=(round_1, on_total, *rest)), 2, "hal")
    assert view is not None
    assert view.team is not None
    assert view.team.net == 141
