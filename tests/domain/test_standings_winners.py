from fractions import Fraction

from conftest import net_total

from league.domain.results import Award, RoundAwards
from league.domain.standings import round_winners, team_round_winners


def test_r10_the_lowest_net_total_wins_the_round() -> None:
    entries = [net_total(71, "ann"), net_total(70, "bob"), net_total(72, "cal")]
    assert round_winners(entries) == ("bob",)


def test_r10_players_level_on_the_lowest_net_total_share_the_round() -> None:
    # Cal comes before Bob in the entries, so the order is the sort's and not the input's.
    entries = [net_total(70, "cal"), net_total(70, "bob"), net_total(71, "ann")]
    assert round_winners(entries) == ("bob", "cal")


def test_r10_no_on_time_card_means_no_winner() -> None:
    assert round_winners([]) == ()


def record(team: str, points: int) -> Award:
    return Award(team, "allplay", Fraction(points), "record")


def position(team: str, points: int) -> Award:
    return Award(team, "field", Fraction(points), "position")


def test_r15_the_highest_round_total_wins_a_team_round() -> None:
    # red leads the allplay and blue the field, and gold wins on the sum of the two.
    awards = (
        record("red", 3),
        record("gold", 2),
        record("blue", 0),
        position("blue", 4),
        position("gold", 3),
        position("red", 1),
    )
    assert team_round_winners(RoundAwards(1, awards)) == ("gold",)


def test_r15_teams_level_on_the_highest_round_total_share_the_round() -> None:
    awards = (record("red", 2), record("blue", 1), record("gold", 2))
    assert team_round_winners(RoundAwards(1, awards)) == ("gold", "red")


def test_r15_a_manual_award_is_no_part_of_the_round_total() -> None:
    awards = (
        record("red", 2),
        record("blue", 1),
        Award("blue", "longest-drive", Fraction(3), "manual"),
    )
    assert team_round_winners(RoundAwards(1, awards)) == ("red",)


def test_r15_a_round_without_a_contest_award_has_no_winner() -> None:
    awards = (Award("blue", "longest-drive", Fraction(3), "manual"),)
    assert team_round_winners(RoundAwards(1, awards)) == ()
