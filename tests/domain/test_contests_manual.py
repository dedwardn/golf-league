from fractions import Fraction

from league.domain.contests import manual_awards
from league.domain.facts import ManualAward
from league.domain.results import Award


def test_r9_a_manual_award_is_added_as_it_is() -> None:
    manual = [
        ManualAward("ann", "longest-drive", Fraction(1)),
        ManualAward("bob", "closest-to-pin", Fraction(1, 2)),
    ]
    assert manual_awards(manual) == (
        Award("ann", "longest-drive", Fraction(1), "manual"),
        Award("bob", "closest-to-pin", Fraction(1, 2), "manual"),
    )


def test_r9_a_manual_award_takes_points_away_and_its_key_is_a_label() -> None:
    # One adjustment given to two players is one label on two awards, not a clash of ids.
    manual = [ManualAward(name, "adjustment", Fraction(-2)) for name in ("ann", "bob")]
    assert manual_awards(manual) == (
        Award("ann", "adjustment", Fraction(-2), "manual"),
        Award("bob", "adjustment", Fraction(-2), "manual"),
    )
