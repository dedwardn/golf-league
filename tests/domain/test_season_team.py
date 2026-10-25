from dataclasses import replace
from datetime import timedelta
from fractions import Fraction

from conftest import with_round
from fixtures.team_season import GREEN_LATE, ROUND_2, ROUND_3, ROUND_4, ROUND_5, SEASON

from league.domain.results import Award, RoundAwards, StandingsRow
from league.domain.season import compute_season


def allplay(points: dict[str, Fraction]) -> tuple[Award, ...]:
    return tuple(Award(team, "allplay", share, "record") for team, share in points.items())


ROUND_2_AWARDS = (
    *allplay(
        {"blue": Fraction(3, 2), "gold": Fraction(3, 2), "green": Fraction(0), "red": Fraction(3)}
    ),
    Award("blue", "field", Fraction(3), "position"),
    Award("gold", "field", Fraction(1), "position"),
    Award("green", "field", Fraction(2), "position"),
    Award("red", "field", Fraction(4), "position"),
)


def test_r17_the_golden_team_season_awards_every_round() -> None:
    assert [view.awards for view in compute_season(SEASON).rounds] == [
        RoundAwards(
            1, allplay({"blue": Fraction(3), "green": Fraction(3, 4), "red": Fraction(3, 4)})
        ),
        RoundAwards(2, ROUND_2_AWARDS),
        RoundAwards(
            3, allplay({"gold": Fraction(9, 4), "green": Fraction(0), "red": Fraction(9, 4)})
        ),
        RoundAwards(4, allplay({"blue": Fraction(0), "gold": Fraction(3, 2), "red": Fraction(3)})),
        RoundAwards(
            5,
            (
                *allplay(
                    {
                        "blue": Fraction(1, 2),
                        "gold": Fraction(3),
                        "green": Fraction(2),
                        "red": Fraction(1, 2),
                    }
                ),
                Award("red", "longest-drive", Fraction(3), "manual"),
            ),
        ),
    ]


def test_r10_the_golden_team_season_table() -> None:
    # Best 4: red drops round 5's 1/2 and keeps its longest drive. The others scored in four.
    assert compute_season(SEASON).standings == (
        StandingsRow(1, "red", Fraction(16)),
        StandingsRow(2, "gold", Fraction(37, 4)),
        StandingsRow(3, "blue", Fraction(8)),
        StandingsRow(4, "green", Fraction(19, 4)),
    )


def test_r15_the_golden_team_season_round_winners() -> None:
    assert [view.winners for view in compute_season(SEASON).rounds] == [
        ("blue",),
        ("red",),
        ("gold", "red"),
        ("red",),
        ("gold",),
    ]


def test_r15_a_late_team_card_scores_nothing() -> None:
    # Closed after green's 64, round 4 is green's.
    counted = with_round(SEASON, replace(ROUND_4, closed_at=GREEN_LATE))
    assert compute_season(SEASON).rounds[3].winners == ("red",)
    assert compute_season(counted).rounds[3].winners == ("green",)


def test_r15_a_late_players_card_leaves_their_team_without_a_score() -> None:
    # ann is red's first player by id and fay green's second, so the team's time is its latest.
    assert ROUND_2.closed_at is not None
    late = ROUND_2.closed_at + timedelta(hours=1)
    cards = {
        player_id: replace(card, submitted_at=late) if player_id in {"ann", "fay"} else card
        for player_id, card in ROUND_2.cards.items()
    }
    awards = compute_season(with_round(SEASON, replace(ROUND_2, cards=cards))).rounds[1].awards
    assert awards.awards == (
        *allplay({"blue": Fraction(3, 2), "gold": Fraction(3, 2)}),
        Award("blue", "field", Fraction(4), "position"),
        Award("gold", "field", Fraction(3), "position"),
    )


def test_r15_a_contest_allowance_is_not_read_in_a_team_season() -> None:
    contests = tuple(replace(config, allowance=50) for config in ROUND_2.contests)
    halved = with_round(SEASON, replace(ROUND_2, contests=contests))
    assert compute_season(halved).rounds[1].awards.awards == ROUND_2_AWARDS


def test_r15_an_open_team_round_has_no_winner_and_reaches_no_table() -> None:
    view = compute_season(with_round(SEASON, replace(ROUND_5, closed_at=None)))
    assert view.rounds[4].winners == ()
    assert view.standings == (
        StandingsRow(1, "red", Fraction(13)),
        StandingsRow(2, "blue", Fraction(15, 2)),
        StandingsRow(3, "gold", Fraction(25, 4)),
        StandingsRow(4, "green", Fraction(11, 4)),
    )


def test_r15_a_team_that_has_not_scored_has_a_row() -> None:
    # blue has no team card in round 3, and green's earns nothing.
    assert compute_season(replace(SEASON, rounds=(ROUND_3,))).standings == (
        StandingsRow(1, "gold", Fraction(9, 4)),
        StandingsRow(1, "red", Fraction(9, 4)),
        StandingsRow(3, "blue", Fraction(0)),
        StandingsRow(3, "green", Fraction(0)),
    )
