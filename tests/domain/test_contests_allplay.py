from fractions import Fraction

from conftest import LATE, a_contest, net_total

from league.domain.configs import AllplayConfig
from league.domain.contests import allplay_awards
from league.domain.results import Award


def an_allplay(scale: Fraction = Fraction(2)) -> AllplayConfig:
    return AllplayConfig("allplay", "total", scale)


def test_r9_allplay_example_five_cards_scale_2_gives_1_25() -> None:
    # Ann beats Cal and Dee, halves with Bob and loses to Eve: 2 * (2 + 0.5) / 4.
    field = [net_total(n, p) for n, p in [(72, "ann"), (72, "bob"), (73, "cal"), (74, "dee")]]
    field.append(net_total(71, "eve"))
    assert allplay_awards(a_contest(field), an_allplay()) == (
        Award("ann", "allplay", Fraction(5, 4), "record"),
        Award("bob", "allplay", Fraction(5, 4), "record"),
        Award("cal", "allplay", Fraction(1, 2), "record"),
        Award("dee", "allplay", Fraction(0), "record"),
        Award("eve", "allplay", Fraction(2), "record"),
    )


def test_r9_allplay_with_one_card_gives_no_award() -> None:
    assert allplay_awards(a_contest([net_total(70, "ann")]), an_allplay()) == ()


def test_r9_allplay_ignores_late_cards() -> None:
    # Ann's late 69 would beat both, and would make n three instead of two.
    field = [net_total(69, "ann", submitted_at=LATE), net_total(72, "bob"), net_total(73, "cal")]
    assert allplay_awards(a_contest(field), an_allplay(Fraction(1))) == (
        Award("bob", "allplay", Fraction(1), "record"),
        Award("cal", "allplay", Fraction(0), "record"),
    )


def test_r9_allplay_records_of_one_third_are_exact() -> None:
    # Bob, Cal and Dee halve with each other and lose to Ann: (0 + 0.5 * 2) / 3 each.
    field = [net_total(n, p) for n, p in [(70, "ann"), (72, "bob"), (72, "cal"), (72, "dee")]]
    awards = allplay_awards(a_contest(field), an_allplay(Fraction(1)))
    assert [award.points for award in awards[1:]] == [Fraction(1, 3)] * 3


def test_r9_allplay_applies_the_multiplier() -> None:
    field = [net_total(70, "ann"), net_total(71, "bob")]
    doubled = AllplayConfig("allplay", "total", Fraction(2), multiplier=2)
    assert [award.points for award in allplay_awards(a_contest(field), doubled)] == [
        Fraction(4),
        Fraction(0),
    ]
