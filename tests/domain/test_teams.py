import pytest
from conftest import FLAT_TEE, PARS, STROKE_INDEXES, TEE, a_card, net_par_except

from league.domain.configs import (
    Basis,
    BestballFormat,
    CombinedFormat,
    FoursomeFormat,
    GreensomeFormat,
    ScrambleFormat,
)
from league.domain.results import NetCard
from league.domain.strokes import net_card, playing_handicap, stableford_points
from league.domain.teams import own_ball_score, team_playing_handicap

# R16's example: indexes 10.0 and 20.0 on FLAT_TEE give course handicaps 10 and 20.
TEN = 100
TWENTY = 200


def test_r16_best_ball_plays_off_9_and_17() -> None:
    allowance = BestballFormat().allowance
    assert playing_handicap(TEN, FLAT_TEE, allowance) == 9
    assert playing_handicap(TWENTY, FLAT_TEE, allowance) == 17


def test_r16_combined_plays_off_10_and_20() -> None:
    allowance = CombinedFormat().allowance
    assert playing_handicap(TEN, FLAT_TEE, allowance) == 10
    assert playing_handicap(TWENTY, FLAT_TEE, allowance) == 20


def test_r16_scramble_plays_off_6_5_rounded_to_7() -> None:
    assert team_playing_handicap((TEN, TWENTY), FLAT_TEE, ScrambleFormat()) == 7


def test_r16_greensome_plays_off_14() -> None:
    assert team_playing_handicap((TEN, TWENTY), FLAT_TEE, GreensomeFormat()) == 14


def test_r16_foursome_plays_off_15() -> None:
    assert team_playing_handicap((TEN, TWENTY), FLAT_TEE, FoursomeFormat()) == 15


def test_r16_the_order_of_the_two_players_does_not_change_the_team_handicap() -> None:
    # Foursome weighs both players alike, so only scramble and greensome can tell.
    assert team_playing_handicap((TWENTY, TEN), FLAT_TEE, ScrambleFormat()) == 7
    assert team_playing_handicap((TWENTY, TEN), FLAT_TEE, GreensomeFormat()) == 14


def test_r16_an_allowance_overridden_by_the_round() -> None:
    # 2.5 + 2 is 4.5, which rounds up to 5.
    assert team_playing_handicap((TEN, TWENTY), FLAT_TEE, ScrambleFormat(low=25, high=10)) == 5
    allowance = BestballFormat(allowance=90).allowance
    assert playing_handicap(TEN, FLAT_TEE, allowance) == 9
    assert playing_handicap(TWENTY, FLAT_TEE, allowance) == 18


def test_r16_course_handicaps_are_kept_exact_and_the_team_handicap_is_rounded_once() -> None:
    # 3.675 + 1.575 is 5.25, so 5. Rounding each term gives 4 + 2, and rounding each
    # course handicap first gives 5.5, both 6.
    assert team_playing_handicap((105, 105), FLAT_TEE, ScrambleFormat()) == 5
    # 22.6 * 0.5 is 11.3, so 11. Rounding each player's half gives 6 + 6, and rounding
    # the course handicaps first gives 23 * 0.5, so 12.
    assert team_playing_handicap((116, 110), FLAT_TEE, FoursomeFormat()) == 11


# R17's example on hole 1, par 4: nets 3 and 7. Every other hole is net par for both.
NET_3 = NetCard(net_par_except({1: 3}))
NET_7 = NetCard(net_par_except({1: 7}))


@pytest.mark.parametrize("basis", ["holes", "total", "stableford"])
def test_r17_best_ball_scores_the_lower_net_per_hole_on_every_basis(basis: Basis) -> None:
    # Each player has the lower net on one hole, so taking the better whole card fails.
    a = NetCard(net_par_except({1: 3, 2: 6}))
    b = NetCard(net_par_except({1: 7, 2: 3}))
    expected = NetCard(net_par_except({1: 3, 2: 3}))
    assert own_ball_score((a, b), BestballFormat(), basis, TEE) == expected


@pytest.mark.parametrize("basis", ["holes", "total"])
def test_r17_combined_scores_the_summed_net(basis: Basis) -> None:
    score = own_ball_score((NET_3, NET_7), CombinedFormat(), basis, TEE)
    assert score == NetCard(tuple(10 if hole == 1 else 2 * par for hole, par in enumerate(PARS, 1)))


def test_r17_combined_on_stableford_sums_the_points_not_the_points_of_the_summed_net() -> None:
    # Hole 1 is 3 + 0 points, where the summed net 10 would score 0. Every other hole is
    # 2 + 2, where the lower net alone would score 2.
    score = own_ball_score((NET_3, NET_7), CombinedFormat(), "stableford", TEE)
    assert score is not None
    assert stableford_points(score, TEE) == (3,) + (4,) * 17


def test_r17_a_shared_ball_team_card_is_netted_at_the_team_playing_handicap() -> None:
    handicap = team_playing_handicap((TEN, TWENTY), FLAT_TEE, ScrambleFormat())
    net = net_card(a_card(PARS), FLAT_TEE, handicap)
    strokes = tuple(1 if index <= 7 else 0 for index in STROKE_INDEXES)
    assert net == NetCard(tuple(par - given for par, given in zip(PARS, strokes, strict=True)))


@pytest.mark.parametrize("config", [BestballFormat(), CombinedFormat()])
@pytest.mark.parametrize("nets", [(None, NET_3), (NET_3, None)])
def test_r17_an_own_ball_team_missing_one_players_card_has_no_score(
    config: BestballFormat | CombinedFormat, nets: tuple[NetCard | None, NetCard | None]
) -> None:
    assert own_ball_score(nets, config, "total", TEE) is None
