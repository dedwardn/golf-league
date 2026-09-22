from datetime import datetime
from fractions import Fraction
from typing import Literal

import pytest
from conftest import PARS, TEE, an_entry, net_par_except

from league.domain.contests import allplay_awards, duel_awards, field_awards
from league.domain.facts import AllplayConfig, DuelConfig, FieldConfig, Pairing
from league.domain.results import Award, NetEntry

CLOSED_AT = datetime(2026, 1, 5, 20, 0)
LATE = datetime(2026, 1, 6, 9, 0)

WIN = Fraction(1)
DRAW = Fraction(1, 2)
LOSS = Fraction(0)


def a_config(
    side: Literal["single", "bestball"] = "single",
    multiplier: int = 1,
    points_win: Fraction = WIN,
    points_draw: Fraction = DRAW,
    points_loss: Fraction = LOSS,
) -> DuelConfig:
    """Match play on net totals: a win is a point, a draw a half, a loss nothing."""
    return DuelConfig(
        key="duel",
        basis="total",
        points_win=points_win,
        points_draw=points_draw,
        points_loss=points_loss,
        side=side,
        multiplier=multiplier,
    )


def test_r9_the_winning_side_takes_points_win_and_the_loser_points_loss() -> None:
    ann = an_entry(net_par_except({1: 3}), player_id="ann", card_id="a")
    bob = an_entry(PARS, player_id="bob", card_id="b")
    awards = duel_awards([ann, bob], TEE, CLOSED_AT, [Pairing(("ann",), ("bob",))], a_config())
    assert awards == (
        Award("ann", "duel", WIN, "win"),
        Award("bob", "duel", LOSS, "loss"),
    )


def test_r9_a_draw_gives_both_sides_points_draw() -> None:
    ann = an_entry(PARS, player_id="ann", card_id="a")
    bob = an_entry(PARS, player_id="bob", card_id="b")
    awards = duel_awards([ann, bob], TEE, CLOSED_AT, [Pairing(("ann",), ("bob",))], a_config())
    assert [award.reason for award in awards] == ["draw", "draw"]
    assert [award.points for award in awards] == [DRAW, DRAW]
    assert [award.contest_key for award in awards] == ["duel", "duel"]


def test_r9_a_bestball_side_awards_every_member_with_an_on_time_card() -> None:
    # Ann and Bob are 70 between them, which beats Cal and Dee's net par.
    ann = an_entry(net_par_except({1: 3}), player_id="ann", card_id="a")
    bob = an_entry(net_par_except({2: 3}), player_id="bob", card_id="b")
    cal = an_entry(PARS, player_id="cal", card_id="c")
    dee = an_entry(PARS, player_id="dee", card_id="d")
    pairing = Pairing(("ann", "bob"), ("cal", "dee"))
    awards = duel_awards([ann, bob, cal, dee], TEE, CLOSED_AT, [pairing], a_config("bestball"))
    assert awards == (
        Award("ann", "duel", WIN, "win"),
        Award("bob", "duel", WIN, "win"),
        Award("cal", "duel", LOSS, "loss"),
        Award("dee", "duel", LOSS, "loss"),
    )


def test_r9_a_bestball_member_without_an_on_time_card_gets_nothing() -> None:
    ann = an_entry(net_par_except({1: 3}), player_id="ann", card_id="a")
    cal = an_entry(PARS, player_id="cal", card_id="c")
    dee = an_entry(PARS, player_id="dee", card_id="d")
    pairing = Pairing(("ann", "bob"), ("cal", "dee"))
    awards = duel_awards([ann, cal, dee], TEE, CLOSED_AT, [pairing], a_config("bestball"))
    assert [award.player_id for award in awards] == ["ann", "cal", "dee"]


def test_r9_a_missing_side_is_replaced_by_the_virtual_side() -> None:
    # Bob has no card at all, so the virtual side of Cal and Dee's 70 plays Ann's net par.
    ann = an_entry(PARS, player_id="ann", card_id="a")
    cal = an_entry(net_par_except({1: 2}), player_id="cal", card_id="c")
    dee = an_entry(net_par_except({1: 2}), player_id="dee", card_id="d")
    pairing = Pairing(("ann",), ("bob",))
    awards = duel_awards([ann, cal, dee], TEE, CLOSED_AT, [pairing], a_config())
    assert awards == (Award("ann", "duel", LOSS, "loss"),)


def test_r9_a_single_sided_pairing_meets_the_virtual_side() -> None:
    ann = an_entry(net_par_except({1: 2}), player_id="ann", card_id="a")
    cal = an_entry(PARS, player_id="cal", card_id="c")
    dee = an_entry(PARS, player_id="dee", card_id="d")
    awards = duel_awards([ann, cal, dee], TEE, CLOSED_AT, [Pairing(("ann",))], a_config())
    assert awards == (Award("ann", "duel", WIN, "win"),)


def test_r9_a_late_card_meets_the_virtual_side_alone() -> None:
    # Ann's side is missing while the round runs, so Bob plays the virtual side and
    # loses to it. Ann's late 70 then beats the virtual side built from the same cards.
    ann = an_entry(net_par_except({1: 2}), player_id="ann", card_id="a", submitted_at=LATE)
    bob = an_entry(PARS, player_id="bob", card_id="b")
    cal = an_entry(net_par_except({1: 3}), player_id="cal", card_id="c")
    dee = an_entry(net_par_except({1: 3}), player_id="dee", card_id="d")
    pairing = Pairing(("ann",), ("bob",))
    awards = duel_awards([ann, bob, cal, dee], TEE, CLOSED_AT, [pairing], a_config())
    assert awards == (
        Award("bob", "duel", LOSS, "loss"),
        Award("ann", "duel", WIN, "win"),
    )


def test_r9_a_late_card_changes_no_other_award() -> None:
    # Eve's late 64 would drag the virtual side to 69 and turn Ann's win into a loss,
    # if a late card could reach the cards a virtual side is built from.
    ann = an_entry(net_par_except({1: 3}), player_id="ann", card_id="a")
    cal = an_entry(PARS, player_id="cal", card_id="c")
    dee = an_entry(PARS, player_id="dee", card_id="d")
    eve = an_entry(
        net_par_except({1: 1, 2: 1, 3: 1}), player_id="eve", card_id="e", submitted_at=LATE
    )
    pairing = Pairing(("ann",), ("bob",))
    without = duel_awards([ann, cal, dee], TEE, CLOSED_AT, [pairing], a_config())
    with_late = duel_awards([ann, cal, dee, eve], TEE, CLOSED_AT, [pairing], a_config())
    assert without == (Award("ann", "duel", WIN, "win"),)
    assert with_late[:1] == without
    assert with_late[1] == Award("eve", "duel", WIN, "win")


def test_r9_a_late_bestball_member_earns_from_the_virtual_side_alone() -> None:
    # Ann played on alone and lost the best ball, so Bob's late card earned him nothing
    # from the side and meets the virtual side by itself.
    ann = an_entry(PARS, player_id="ann", card_id="a")
    bob = an_entry(net_par_except({1: 2, 2: 2}), player_id="bob", card_id="b", submitted_at=LATE)
    cal = an_entry(net_par_except({1: 3}), player_id="cal", card_id="c")
    dee = an_entry(net_par_except({2: 3}), player_id="dee", card_id="d")
    pairing = Pairing(("ann", "bob"), ("cal", "dee"))
    awards = duel_awards([ann, bob, cal, dee], TEE, CLOSED_AT, [pairing], a_config("bestball"))
    assert awards == (
        Award("ann", "duel", LOSS, "loss"),
        Award("cal", "duel", WIN, "win"),
        Award("dee", "duel", WIN, "win"),
        Award("bob", "duel", WIN, "win"),
    )


def test_r9_both_sides_missing_leaves_each_late_card_to_the_virtual_side() -> None:
    ann = an_entry(net_par_except({1: 2}), player_id="ann", card_id="a", submitted_at=LATE)
    bob = an_entry(net_par_except({1: 5}), player_id="bob", card_id="b", submitted_at=LATE)
    cal = an_entry(net_par_except({1: 3}), player_id="cal", card_id="c")
    dee = an_entry(net_par_except({1: 3}), player_id="dee", card_id="d")
    pairing = Pairing(("ann",), ("bob",))
    awards = duel_awards([ann, bob, cal, dee], TEE, CLOSED_AT, [pairing], a_config())
    assert awards == (
        Award("ann", "duel", WIN, "win"),
        Award("bob", "duel", LOSS, "loss"),
    )


def test_r9_the_multiplier_applies_to_every_award() -> None:
    ann = an_entry(net_par_except({1: 3}), player_id="ann", card_id="a")
    bob = an_entry(PARS, player_id="bob", card_id="b")
    config = a_config(multiplier=2, points_loss=Fraction(1, 4))
    awards = duel_awards([ann, bob], TEE, CLOSED_AT, [Pairing(("ann",), ("bob",))], config)
    assert [award.points for award in awards] == [Fraction(2), Fraction(1, 2)]


def test_r9_an_open_round_has_no_late_cards() -> None:
    # No closed_at, so Ann's card counts as on time however late it looks.
    ann = an_entry(net_par_except({1: 2}), player_id="ann", card_id="a", submitted_at=LATE)
    bob = an_entry(PARS, player_id="bob", card_id="b")
    awards = duel_awards([ann, bob], TEE, None, [Pairing(("ann",), ("bob",))], a_config())
    assert awards == (
        Award("ann", "duel", WIN, "win"),
        Award("bob", "duel", LOSS, "loss"),
    )


def test_r9_a_single_side_names_exactly_one_player() -> None:
    ann = an_entry(PARS, player_id="ann", card_id="a")
    pairing = Pairing(("ann", "bob"), ("cal",))
    with pytest.raises(ValueError, match="exactly one player"):
        duel_awards([ann], TEE, CLOSED_AT, [pairing], a_config())


POSITION_POINTS = (Fraction(5), Fraction(3), Fraction(1))


def a_field(basis: Literal["total", "stableford"] = "total", multiplier: int = 1) -> FieldConfig:
    """Five points for first, three for second, one for third, none beyond."""
    return FieldConfig("field", basis, POSITION_POINTS, multiplier)


def an_allplay(scale: Fraction = Fraction(2)) -> AllplayConfig:
    return AllplayConfig("allplay", "total", scale)


def net_total(total: int, player_id: str, submitted_at: datetime = CLOSED_AT) -> NetEntry:
    """An on-time entry whose net total is that, all of the difference on hole 1."""
    return an_entry(
        net_par_except({1: PARS[0] + total - sum(PARS)}),
        player_id=player_id,
        card_id=player_id,
        submitted_at=submitted_at,
    )


def test_r9_field_tied_players_share_the_mean_of_their_positions_points() -> None:
    # Bob and Cal tie for second, so each takes the mean of second and third.
    field = [net_total(70, "ann"), net_total(71, "bob"), net_total(71, "cal")]
    assert field_awards(field, TEE, CLOSED_AT, a_field()) == (
        Award("ann", "field", Fraction(5), "position"),
        Award("bob", "field", Fraction(2), "position"),
        Award("cal", "field", Fraction(2), "position"),
    )


def test_r9_field_positions_beyond_the_list_score_0() -> None:
    # Cal and Dee tie for third and fourth: the fourth place is beyond the list, so 1/2 each.
    field = [net_total(n, p) for n, p in [(70, "ann"), (71, "bob"), (72, "cal"), (72, "dee")]]
    field.append(net_total(75, "eve"))
    points = [award.points for award in field_awards(field, TEE, CLOSED_AT, a_field())]
    assert points == [Fraction(5), Fraction(3), Fraction(1, 2), Fraction(1, 2), Fraction(0)]


def test_r9_field_on_stableford_more_points_ranks_higher() -> None:
    # Ann's blow-up on hole 1 costs her 6 strokes but only 2 points, and three birdies
    # win back 3: 37 points against Bob's 36, though her 75 loses on total.
    ann = an_entry(net_par_except({1: 10, 2: 3, 3: 2, 4: 4}), player_id="ann", card_id="a")
    bob = an_entry(PARS, player_id="bob", card_id="b")
    awards = field_awards([ann, bob], TEE, CLOSED_AT, a_field("stableford"))
    assert [award.points for award in awards] == [Fraction(5), Fraction(3)]


def test_r9_field_ignores_late_cards() -> None:
    field = [net_total(69, "ann", submitted_at=LATE), net_total(72, "bob"), net_total(73, "cal")]
    assert field_awards(field, TEE, CLOSED_AT, a_field()) == (
        Award("bob", "field", Fraction(5), "position"),
        Award("cal", "field", Fraction(3), "position"),
    )


def test_r9_field_and_allplay_apply_the_multiplier() -> None:
    field = [net_total(70, "ann"), net_total(71, "bob")]
    awards = field_awards(field, TEE, CLOSED_AT, a_field(multiplier=2))
    assert [award.points for award in awards] == [Fraction(10), Fraction(6)]
    doubled = AllplayConfig("allplay", "total", Fraction(2), multiplier=2)
    assert [award.points for award in allplay_awards(field, TEE, CLOSED_AT, doubled)] == [
        Fraction(4),
        Fraction(0),
    ]


def test_r9_allplay_example_five_cards_scale_2_gives_1_25() -> None:
    # Ann beats Cal and Dee, halves with Bob and loses to Eve: 2 * (2 + 0.5) / 4.
    field = [net_total(n, p) for n, p in [(72, "ann"), (72, "bob"), (73, "cal"), (74, "dee")]]
    field.append(net_total(71, "eve"))
    assert allplay_awards(field, TEE, CLOSED_AT, an_allplay()) == (
        Award("ann", "allplay", Fraction(5, 4), "record"),
        Award("bob", "allplay", Fraction(5, 4), "record"),
        Award("cal", "allplay", Fraction(1, 2), "record"),
        Award("dee", "allplay", Fraction(0), "record"),
        Award("eve", "allplay", Fraction(2), "record"),
    )


def test_r9_allplay_with_one_card_gives_no_award() -> None:
    assert allplay_awards([net_total(70, "ann")], TEE, CLOSED_AT, an_allplay()) == ()


def test_r9_allplay_ignores_late_cards() -> None:
    # Ann's late 69 would beat both, and would make n three instead of two.
    field = [net_total(69, "ann", submitted_at=LATE), net_total(72, "bob"), net_total(73, "cal")]
    assert allplay_awards(field, TEE, CLOSED_AT, an_allplay(Fraction(1))) == (
        Award("bob", "allplay", Fraction(1), "record"),
        Award("cal", "allplay", Fraction(0), "record"),
    )


def test_r9_allplay_records_of_one_third_are_exact() -> None:
    # Bob, Cal and Dee halve with each other and lose to Ann: (0 + 0.5 * 2) / 3 each.
    field = [net_total(n, p) for n, p in [(70, "ann"), (72, "bob"), (72, "cal"), (72, "dee")]]
    awards = allplay_awards(field, TEE, CLOSED_AT, an_allplay(Fraction(1)))
    assert [award.points for award in awards[1:]] == [Fraction(1, 3)] * 3
