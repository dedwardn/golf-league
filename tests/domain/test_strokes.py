import pytest
from conftest import PARS, STROKE_INDEXES, TEE

from league.domain.facts import Card, Tee
from league.domain.results import NetCard
from league.domain.strokes import (
    allocate_strokes,
    net_card,
    playing_handicap,
    stableford_points,
)

# Rating equal to par on slope 113, so R1 reduces to the index itself.
FLAT_TEE = Tee(PARS, STROKE_INDEXES, course_rating_tenths=720, slope=113)


def by_stroke_index(strokes: tuple[int, ...]) -> dict[int, int]:
    return dict(zip(STROKE_INDEXES, strokes, strict=True))


def test_r1_index_18_4_on_slope_131_at_allowance_100_gives_23() -> None:
    assert playing_handicap(184, TEE, 100) == 23


def test_r1_index_18_4_on_slope_131_at_allowance_90_gives_20() -> None:
    assert playing_handicap(184, TEE, 90) == 20


def test_r1_exact_half_rounds_up_not_to_even() -> None:
    # Index 4.5 where rating equals par on slope 113 is exactly 4.5.
    # Half up gives 5. Python's round, which sends a half to even, would give 4.
    assert playing_handicap(45, FLAT_TEE, 100) == 5


def test_r2_handicap_5_gives_one_stroke_on_stroke_index_1_to_5() -> None:
    strokes = by_stroke_index(allocate_strokes(5, TEE))
    assert all(strokes[si] == 1 for si in range(1, 6))
    assert all(strokes[si] == 0 for si in range(6, 19))


def test_r2_handicap_20_gives_two_strokes_on_stroke_index_1_and_2() -> None:
    strokes = by_stroke_index(allocate_strokes(20, TEE))
    assert all(strokes[si] == 2 for si in (1, 2))
    assert all(strokes[si] == 1 for si in range(3, 19))


def test_r2_handicap_40_gives_three_strokes_on_stroke_index_1_to_4() -> None:
    strokes = by_stroke_index(allocate_strokes(40, TEE))
    assert all(strokes[si] == 3 for si in range(1, 5))
    assert all(strokes[si] == 2 for si in range(5, 19))


def test_r2_handicap_minus_2_gives_minus_one_on_stroke_index_17_and_18() -> None:
    strokes = by_stroke_index(allocate_strokes(-2, TEE))
    assert all(strokes[si] == -1 for si in (17, 18))
    assert all(strokes[si] == 0 for si in range(1, 17))


def test_r2_handicap_zero_gives_no_strokes() -> None:
    assert allocate_strokes(0, TEE) == (0,) * 18


def test_r2_handicap_minus_18_gives_minus_one_on_every_hole() -> None:
    assert allocate_strokes(-18, TEE) == (-1,) * 18


def test_r2_handicap_below_minus_18_is_an_error() -> None:
    with pytest.raises(ValueError, match="-18"):
        allocate_strokes(-19, TEE)


def test_r3_net_is_gross_minus_allocated_strokes() -> None:
    # H 20 gives two strokes on stroke index 1 and 2, which sit on holes 1 and 10,
    # and one stroke on every other hole. Gross runs 3, 4, 5 ... 20.
    net = net_card(Card(tuple(range(3, 21))), TEE, 20)
    assert net.scores == (1, 3, 4, 5, 6, 7, 8, 9, 10, 10, 12, 13, 14, 15, 16, 17, 18, 19)
    assert net.total == 187


def test_r3_net_total_is_the_sum_of_the_net_scores() -> None:
    net = net_card(Card((5,) * 18), TEE, 18)
    assert net.scores == (4,) * 18
    assert net.total == 72


def test_r3_par_4_stroke_index_3_handicap_20_gross_6_is_one_stableford_point() -> None:
    hole = STROKE_INDEXES.index(3)
    assert PARS[hole] == 4
    gross: list[int] = [4] * 18
    gross[hole] = 6
    net = net_card(Card(tuple(gross)), TEE, 20)
    assert net.scores[hole] == 5
    assert stableford_points(net, TEE)[hole] == 1


def test_r3_stableford_is_never_below_zero() -> None:
    assert stableford_points(NetCard((12,) * 18), TEE) == (0,) * 18
