from collections.abc import Sequence
from datetime import datetime
from fractions import Fraction
from typing import Literal

import pytest
from conftest import CLOSED_AT, LATE, PARS, a_contest, an_entry, net_par_except, net_total

from league.domain.configs import DuelConfig
from league.domain.contests import duel_awards
from league.domain.facts import Pairing
from league.domain.results import Award, NetEntry

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


def on_time(entries: Sequence[NetEntry], closed_at: datetime | None = CLOSED_AT) -> list[NetEntry]:
    """The reference pool of a round that names no reference_rounds: its own on-time cards.

    Filtering is the caller's job, so the tests that mean a round's default pool say so here.
    """
    return [entry for entry in entries if closed_at is None or entry.submitted_at <= closed_at]


def test_r9_the_winning_side_takes_points_win_and_the_loser_points_loss() -> None:
    ann = an_entry(net_par_except({1: 3}), competitor_id="ann", card_id="a")
    bob = an_entry(PARS, competitor_id="bob", card_id="b")
    awards = duel_awards(
        a_contest([ann, bob]), on_time([ann, bob]), [Pairing(("ann",), ("bob",))], a_config()
    )
    assert awards == (
        Award("ann", "duel", WIN, "win"),
        Award("bob", "duel", LOSS, "loss"),
    )


def test_r9_a_draw_gives_both_sides_points_draw() -> None:
    ann = an_entry(PARS, competitor_id="ann", card_id="a")
    bob = an_entry(PARS, competitor_id="bob", card_id="b")
    awards = duel_awards(
        a_contest([ann, bob]), on_time([ann, bob]), [Pairing(("ann",), ("bob",))], a_config()
    )
    assert [award.reason for award in awards] == ["draw", "draw"]
    assert [award.points for award in awards] == [DRAW, DRAW]
    assert [award.key for award in awards] == ["duel", "duel"]


def test_r9_a_bestball_side_awards_every_member_with_an_on_time_card() -> None:
    # Ann and Bob are 70 between them, which beats Cal and Dee's net par.
    ann = an_entry(net_par_except({1: 3}), competitor_id="ann", card_id="a")
    bob = an_entry(net_par_except({2: 3}), competitor_id="bob", card_id="b")
    cal = an_entry(PARS, competitor_id="cal", card_id="c")
    dee = an_entry(PARS, competitor_id="dee", card_id="d")
    pairing = Pairing(("ann", "bob"), ("cal", "dee"))
    awards = duel_awards(
        a_contest([ann, bob, cal, dee]),
        on_time([ann, bob, cal, dee]),
        [pairing],
        a_config("bestball"),
    )
    assert awards == (
        Award("ann", "duel", WIN, "win"),
        Award("bob", "duel", WIN, "win"),
        Award("cal", "duel", LOSS, "loss"),
        Award("dee", "duel", LOSS, "loss"),
    )


def test_r9_a_bestball_member_without_an_on_time_card_gets_nothing() -> None:
    ann = an_entry(net_par_except({1: 3}), competitor_id="ann", card_id="a")
    cal = an_entry(PARS, competitor_id="cal", card_id="c")
    dee = an_entry(PARS, competitor_id="dee", card_id="d")
    pairing = Pairing(("ann", "bob"), ("cal", "dee"))
    awards = duel_awards(
        a_contest([ann, cal, dee]), on_time([ann, cal, dee]), [pairing], a_config("bestball")
    )
    assert [award.competitor_id for award in awards] == ["ann", "cal", "dee"]


def test_r9_a_missing_side_is_replaced_by_the_virtual_side() -> None:
    # Bob has no card at all, so the virtual side of Cal and Dee's 70 plays Ann's net par.
    ann = an_entry(PARS, competitor_id="ann", card_id="a")
    cal = an_entry(net_par_except({1: 2}), competitor_id="cal", card_id="c")
    dee = an_entry(net_par_except({1: 2}), competitor_id="dee", card_id="d")
    pairing = Pairing(("ann",), ("bob",))
    awards = duel_awards(
        a_contest([ann, cal, dee]), on_time([ann, cal, dee]), [pairing], a_config()
    )
    assert awards == (
        Award("ann", "duel", LOSS, "loss"),
        Award("cal", "duel", WIN, "win"),
        Award("dee", "duel", WIN, "win"),
    )


def test_r9_a_single_sided_pairing_meets_the_virtual_side() -> None:
    ann = an_entry(net_par_except({1: 2}), competitor_id="ann", card_id="a")
    cal = an_entry(PARS, competitor_id="cal", card_id="c")
    dee = an_entry(PARS, competitor_id="dee", card_id="d")
    awards = duel_awards(
        a_contest([ann, cal, dee]), on_time([ann, cal, dee]), [Pairing(("ann",))], a_config()
    )
    assert awards == (
        Award("ann", "duel", WIN, "win"),
        Award("cal", "duel", LOSS, "loss"),
        Award("dee", "duel", LOSS, "loss"),
    )


def test_r9_a_late_card_meets_the_virtual_side_alone() -> None:
    # Ann's side is missing while the round runs, so Bob plays the virtual side and
    # loses to it. Ann's late 70 then beats the virtual side built from the same cards.
    ann = an_entry(net_par_except({1: 2}), competitor_id="ann", card_id="a", submitted_at=LATE)
    bob = an_entry(PARS, competitor_id="bob", card_id="b")
    cal = an_entry(net_par_except({1: 3}), competitor_id="cal", card_id="c")
    dee = an_entry(net_par_except({1: 3}), competitor_id="dee", card_id="d")
    pairing = Pairing(("ann",), ("bob",))
    awards = duel_awards(
        a_contest([ann, bob, cal, dee]), on_time([ann, bob, cal, dee]), [pairing], a_config()
    )
    assert awards == (
        Award("bob", "duel", LOSS, "loss"),
        Award("ann", "duel", WIN, "win"),
        Award("cal", "duel", WIN, "win"),
        Award("dee", "duel", WIN, "win"),
    )


def test_r9_a_late_card_changes_no_other_award() -> None:
    # Eve's late 64 would drag the virtual side to 69 and turn Ann's win into a loss.
    # The caller's on_time filter keeps her out of the reference pool, and duel_awards must
    # take the pool from references alone: reading contest.entries for it would let her in.
    ann = an_entry(net_par_except({1: 3}), competitor_id="ann", card_id="a")
    cal = an_entry(PARS, competitor_id="cal", card_id="c")
    dee = an_entry(PARS, competitor_id="dee", card_id="d")
    eve = an_entry(
        net_par_except({1: 1, 2: 1, 3: 1}), competitor_id="eve", card_id="e", submitted_at=LATE
    )
    pairing = Pairing(("ann",), ("bob",))
    without = duel_awards(
        a_contest([ann, cal, dee]), on_time([ann, cal, dee]), [pairing], a_config()
    )
    with_late = duel_awards(
        a_contest([ann, cal, dee, eve]), on_time([ann, cal, dee, eve]), [pairing], a_config()
    )
    assert without == (
        Award("ann", "duel", WIN, "win"),
        Award("cal", "duel", DRAW, "draw"),
        Award("dee", "duel", DRAW, "draw"),
    )
    assert with_late[:3] == without
    assert with_late[3] == Award("eve", "duel", WIN, "win")


def test_r9_a_late_bestball_member_earns_from_the_virtual_side_alone() -> None:
    # Ann played on alone and lost the best ball, so Bob's late card earned him nothing
    # from the side and meets the virtual side by itself.
    ann = an_entry(PARS, competitor_id="ann", card_id="a")
    bob = an_entry(
        net_par_except({1: 2, 2: 2}), competitor_id="bob", card_id="b", submitted_at=LATE
    )
    cal = an_entry(net_par_except({1: 3}), competitor_id="cal", card_id="c")
    dee = an_entry(net_par_except({2: 3}), competitor_id="dee", card_id="d")
    pairing = Pairing(("ann", "bob"), ("cal", "dee"))
    awards = duel_awards(
        a_contest([ann, bob, cal, dee]),
        on_time([ann, bob, cal, dee]),
        [pairing],
        a_config("bestball"),
    )
    assert awards == (
        Award("ann", "duel", LOSS, "loss"),
        Award("cal", "duel", WIN, "win"),
        Award("dee", "duel", WIN, "win"),
        Award("bob", "duel", WIN, "win"),
    )


def test_r9_both_sides_missing_leaves_each_card_to_the_virtual_side() -> None:
    ann = an_entry(net_par_except({1: 2}), competitor_id="ann", card_id="a", submitted_at=LATE)
    bob = an_entry(net_par_except({1: 5}), competitor_id="bob", card_id="b", submitted_at=LATE)
    cal = an_entry(net_par_except({1: 3}), competitor_id="cal", card_id="c")
    dee = an_entry(net_par_except({1: 3}), competitor_id="dee", card_id="d")
    pairing = Pairing(("ann",), ("bob",))
    awards = duel_awards(
        a_contest([ann, bob, cal, dee]), on_time([ann, bob, cal, dee]), [pairing], a_config()
    )
    assert awards == (
        Award("ann", "duel", WIN, "win"),
        Award("bob", "duel", LOSS, "loss"),
        Award("cal", "duel", DRAW, "draw"),
        Award("dee", "duel", DRAW, "draw"),
    )


def test_r9_the_multiplier_applies_to_every_award() -> None:
    ann = an_entry(net_par_except({1: 3}), competitor_id="ann", card_id="a")
    bob = an_entry(PARS, competitor_id="bob", card_id="b")
    config = a_config(multiplier=2, points_loss=Fraction(1, 4))
    awards = duel_awards(
        a_contest([ann, bob]), on_time([ann, bob]), [Pairing(("ann",), ("bob",))], config
    )
    assert [award.points for award in awards] == [Fraction(2), Fraction(1, 2)]


def test_r9_an_open_round_has_no_late_cards() -> None:
    # No closed_at, so Ann's card counts as on time however late it looks.
    ann = an_entry(net_par_except({1: 2}), competitor_id="ann", card_id="a", submitted_at=LATE)
    bob = an_entry(PARS, competitor_id="bob", card_id="b")
    awards = duel_awards(
        a_contest([ann, bob], None),
        on_time([ann, bob], None),
        [Pairing(("ann",), ("bob",))],
        a_config(),
    )
    assert awards == (
        Award("ann", "duel", WIN, "win"),
        Award("bob", "duel", LOSS, "loss"),
    )


def test_r9_an_unpaired_on_time_card_meets_the_virtual_side() -> None:
    # Ann joined after the pairings locked (R14), so she is in none of them. Her card is
    # on time and earns nothing from a pairing, so R9 gives her the virtual side.
    ann = an_entry(net_par_except({1: 2}), competitor_id="ann", card_id="a")
    bob = an_entry(PARS, competitor_id="bob", card_id="b")
    cal = an_entry(PARS, competitor_id="cal", card_id="c")
    pairings = [Pairing(("bob",), ("cal",))]
    assert duel_awards(
        a_contest([ann, bob, cal]), on_time([ann, bob, cal]), pairings, a_config()
    ) == (
        Award("bob", "duel", DRAW, "draw"),
        Award("cal", "duel", DRAW, "draw"),
        Award("ann", "duel", WIN, "win"),
    )


def test_r9_a_player_who_lost_a_pairing_is_not_swept_again() -> None:
    # Ann is the sharp case: she loses her pairing and takes points_loss, which is 0 here,
    # while her card would beat the virtual side. A missing earned guard therefore shows up
    # as a second award worth a win rather than as a harmless duplicate, and a sweep asking
    # for no points rather than no award hands her the same one.
    ann = an_entry(net_par_except({1: 2}), competitor_id="ann", card_id="a")
    bob = an_entry(net_par_except({1: 1, 2: 1}), competitor_id="bob", card_id="b")
    cal = an_entry(net_par_except({1: 6}), competitor_id="cal", card_id="c")
    dee = an_entry(net_par_except({1: 6}), competitor_id="dee", card_id="d")
    pairings = [Pairing(("ann",), ("bob",)), Pairing(("cal",), ("dee",))]
    assert duel_awards(
        a_contest([ann, bob, cal, dee]), on_time([ann, bob, cal, dee]), pairings, a_config()
    ) == (
        Award("ann", "duel", LOSS, "loss"),
        Award("bob", "duel", WIN, "win"),
        Award("cal", "duel", DRAW, "draw"),
        Award("dee", "duel", DRAW, "draw"),
    )


def test_r9_a_duel_with_no_pairings_is_an_error() -> None:
    # Unpublished pairings would otherwise award the whole field against the field,
    # which reads as a result rather than as a round the admin forgot to publish.
    ann = an_entry(PARS, competitor_id="ann", card_id="a")
    with pytest.raises(ValueError, match="needs pairings"):
        duel_awards(a_contest([ann]), on_time([ann]), [], a_config())


def test_r9_a_single_side_names_exactly_one_player() -> None:
    ann = an_entry(PARS, competitor_id="ann", card_id="a")
    pairing = Pairing(("ann", "bob"), ("cal",))
    with pytest.raises(ValueError, match="exactly one player"):
        duel_awards(a_contest([ann]), on_time([ann]), [pairing], a_config())


def test_r7_a_virtual_side_is_drawn_from_the_reference_entries() -> None:
    # Bob has no card, so Ann meets a virtual side. Zed's 70 is a reference card from
    # another round and no entry of this one: the virtual side is 70 and beats Ann's 72,
    # where one built from this round's entries would be net par and draw.
    ann = an_entry(PARS, competitor_id="ann", card_id="a")
    references = [net_total(70, "zed")]
    pairing = Pairing(("ann",), ("bob",))
    awards = duel_awards(a_contest([ann]), references, [pairing], a_config())
    assert awards == (Award("ann", "duel", LOSS, "loss"),)


def test_r7_reference_entries_still_exclude_the_players_the_virtual_side_will_meet() -> None:
    # Ann is in no pairing, so she meets the virtual side alone. Her own 60 from the
    # reference round is left out, which leaves Zed's 74 for Ann's 72 to beat. Counted, it
    # would make the virtual side 67 and beat her.
    ann = an_entry(PARS, competitor_id="ann", card_id="a")
    bob = an_entry(PARS, competitor_id="bob", card_id="b")
    cal = an_entry(PARS, competitor_id="cal", card_id="c")
    references = [net_total(60, "ann"), net_total(74, "zed")]
    pairings = [Pairing(("bob",), ("cal",))]
    awards = duel_awards(a_contest([ann, bob, cal]), references, pairings, a_config())
    assert awards == (
        Award("bob", "duel", DRAW, "draw"),
        Award("cal", "duel", DRAW, "draw"),
        Award("ann", "duel", WIN, "win"),
    )
