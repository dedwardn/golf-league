from conftest import PARS, TEE

from league.domain.compare import compare
from league.domain.results import Comparison, NetCard, Side

# A is under B on the first seven holes, over B on the next five, level on the last six.
A = Side(("ann",), NetCard((3,) * 7 + (5,) * 5 + (4,) * 6))
B = Side(("bob",), NetCard((4,) * 7 + (3,) * 5 + (4,) * 6))

# The same total by two routes: one hole under par and one over, the other way round.
EVEN_A = Side(("ann",), NetCard((3, 5, *PARS[2:])))
EVEN_B = Side(("bob",), NetCard((5, 3, *PARS[2:])))


def test_r8_seven_holes_to_five_is_two_up() -> None:
    result = compare(A, B, "holes", TEE)
    assert result.winner is A
    assert result.margin == 2


def test_r8_total_compares_net_totals_with_the_margin_in_strokes() -> None:
    # B lost the hole count but is three strokes better on the card, so the basis decides.
    assert A.net.total == 70
    assert B.net.total == 67
    assert compare(A, B, "total", TEE) == Comparison(B, 3)


def test_r8_stableford_compares_points_with_the_margin_in_points() -> None:
    level = Side(("ann",), NetCard(PARS))
    one_birdie = Side(("bob",), NetCard((PARS[0] - 1, *PARS[1:])))
    assert compare(level, one_birdie, "stableford", TEE) == Comparison(one_birdie, 1)


def test_r8_equal_holes_is_a_draw() -> None:
    assert compare(EVEN_A, EVEN_B, "holes", TEE) == Comparison(None, 0)


def test_r8_equal_totals_is_a_draw() -> None:
    assert compare(EVEN_A, EVEN_B, "total", TEE) == Comparison(None, 0)


def test_r8_equal_points_is_a_draw() -> None:
    assert compare(EVEN_A, EVEN_B, "stableford", TEE) == Comparison(None, 0)
