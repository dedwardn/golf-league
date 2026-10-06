from fractions import Fraction
from typing import Literal

from conftest import LATE, PARS, a_contest, an_entry, net_par_except, net_total

from league.domain.contests import field_awards
from league.domain.facts import FieldConfig
from league.domain.results import Award

POSITION_POINTS = (Fraction(5), Fraction(3), Fraction(1))


def a_field(basis: Literal["total", "stableford"] = "total", multiplier: int = 1) -> FieldConfig:
    """Five points for first, three for second, one for third, none beyond."""
    return FieldConfig("field", basis, POSITION_POINTS, multiplier)


def test_r9_field_tied_players_share_the_mean_of_their_positions_points() -> None:
    # Bob and Cal tie for second, so each takes the mean of second and third.
    field = [net_total(70, "ann"), net_total(71, "bob"), net_total(71, "cal")]
    assert field_awards(a_contest(field), a_field()) == (
        Award("ann", "field", Fraction(5), "position"),
        Award("bob", "field", Fraction(2), "position"),
        Award("cal", "field", Fraction(2), "position"),
    )


def test_r9_field_positions_beyond_the_list_score_0() -> None:
    # Cal and Dee tie for third and fourth: the fourth place is beyond the list, so 1/2 each.
    field = [net_total(n, p) for n, p in [(70, "ann"), (71, "bob"), (72, "cal"), (72, "dee")]]
    field.append(net_total(75, "eve"))
    points = [award.points for award in field_awards(a_contest(field), a_field())]
    assert points == [Fraction(5), Fraction(3), Fraction(1, 2), Fraction(1, 2), Fraction(0)]


def test_r9_field_on_stableford_more_points_ranks_higher() -> None:
    # Ann's blow-up on hole 1 costs her 6 strokes but only 2 points, and three birdies
    # win back 3: 37 points against Bob's 36, though her 75 loses on total.
    ann = an_entry(net_par_except({1: 10, 2: 3, 3: 2, 4: 4}), player_id="ann", card_id="a")
    bob = an_entry(PARS, player_id="bob", card_id="b")
    awards = field_awards(a_contest([ann, bob]), a_field("stableford"))
    assert [award.points for award in awards] == [Fraction(5), Fraction(3)]


def test_r9_field_ignores_late_cards() -> None:
    field = [net_total(69, "ann", submitted_at=LATE), net_total(72, "bob"), net_total(73, "cal")]
    assert field_awards(a_contest(field), a_field()) == (
        Award("bob", "field", Fraction(5), "position"),
        Award("cal", "field", Fraction(3), "position"),
    )


def test_r9_field_applies_the_multiplier() -> None:
    field = [net_total(70, "ann"), net_total(71, "bob")]
    awards = field_awards(a_contest(field), a_field(multiplier=2))
    assert [award.points for award in awards] == [Fraction(10), Fraction(6)]
