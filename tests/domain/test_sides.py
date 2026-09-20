from datetime import datetime

from conftest import PARS, SUBMITTED_AT, TEE

from league.domain.results import NetCard, NetEntry, Side
from league.domain.sides import bestball_side, single_side, virtual_side

LATER = datetime(2026, 1, 12, 18, 0)


def net_par_except(changes: dict[int, int]) -> tuple[int, ...]:
    """Net par on every hole, with these hole numbers set to these net scores."""
    return tuple(changes.get(hole, par) for hole, par in enumerate(PARS, start=1))


def an_entry(
    scores: tuple[int, ...],
    player_id: str = "ann",
    card_id: str = "card-1",
    submitted_at: datetime = SUBMITTED_AT,
) -> NetEntry:
    return NetEntry(card_id, player_id, submitted_at, NetCard(scores))


def test_r7_a_single_side_is_the_player_s_net_card() -> None:
    scores = net_par_except({1: 6})
    assert single_side(an_entry(scores, player_id="ann")) == Side(("ann",), NetCard(scores))


def test_r7_bestball_takes_the_lowest_net_on_each_hole() -> None:
    ann = an_entry(net_par_except({1: 6, 2: 3}), player_id="ann", card_id="a")
    bob = an_entry(net_par_except({1: 3, 2: 6}), player_id="bob", card_id="b")
    side = bestball_side([ann, bob])
    assert side is not None
    assert side.player_ids == ("ann", "bob")
    assert side.net.scores == net_par_except({1: 3, 2: 3})


def test_r7_a_side_with_no_on_time_card_is_missing() -> None:
    assert bestball_side([]) is None


def test_r7_the_virtual_side_is_the_mean_of_the_net_scores() -> None:
    # The R7 example: hole net scores 4, 5, 5, 6 give 5.
    references = [
        an_entry(net_par_except({1: score}), player_id=f"p{number}", card_id=f"c{number}")
        for number, score in enumerate((4, 5, 5, 6))
    ]
    side = virtual_side(references, [], TEE, 4)
    assert side.net.scores == net_par_except({1: 5})
    assert side.player_ids == ()


def test_r7_a_virtual_hole_mean_rounds_half_up() -> None:
    # The R7 example: 4, 4, 5, 5 give 4.5, which is 5 half up where Python's round gives 4.
    references = [
        an_entry(net_par_except({1: score}), player_id=f"p{number}", card_id=f"c{number}")
        for number, score in enumerate((4, 4, 5, 5))
    ]
    assert virtual_side(references, [], TEE, 4).net.scores == net_par_except({1: 5})


def test_r7_fewer_than_virtual_n_cards_uses_all_of_them() -> None:
    references = [
        an_entry(net_par_except({1: 4}), player_id="ann", card_id="a"),
        an_entry(net_par_except({1: 6}), player_id="bob", card_id="b"),
    ]
    assert virtual_side(references, [], TEE, 4).net.scores == net_par_except({1: 5})


def test_r7_a_tie_for_the_last_place_goes_to_the_earlier_card() -> None:
    # Both ties are on 72. The card ids are the other way round, so only submitted_at
    # can pick the one that joins the 70 in the best two.
    best = an_entry(net_par_except({1: 2}), player_id="ann", card_id="best")
    earlier = an_entry(net_par_except({2: 6, 3: 1}), player_id="bob", card_id="z")
    later = an_entry(net_par_except({2: 2, 3: 5}), player_id="cal", card_id="a", submitted_at=LATER)
    assert best.net.total == 70
    assert earlier.net.total == later.net.total == 72
    side = virtual_side([best, earlier, later], [], TEE, 2)
    assert side.net.scores == net_par_except({1: 3, 2: 5, 3: 2})


def test_r7_a_tie_on_submitted_at_is_broken_by_the_lower_card_id() -> None:
    best = an_entry(net_par_except({1: 2}), player_id="ann", card_id="best")
    lower_id = an_entry(net_par_except({2: 6, 3: 1}), player_id="bob", card_id="a")
    higher_id = an_entry(net_par_except({2: 2, 3: 5}), player_id="cal", card_id="z")
    side = virtual_side([best, higher_id, lower_id], [], TEE, 2)
    assert side.net.scores == net_par_except({1: 3, 2: 5, 3: 2})


def test_r7_the_opposing_players_cards_are_excluded() -> None:
    # Keeping the 2 would pull the hole mean to (6 + 6 + 2) / 3, which is 5.
    ann = an_entry(net_par_except({1: 6}), player_id="ann", card_id="a")
    bob = an_entry(net_par_except({1: 6}), player_id="bob", card_id="b")
    opponent = an_entry(net_par_except({1: 2}), player_id="cal", card_id="c")
    side = virtual_side([ann, bob, opponent], ["cal"], TEE, 4)
    assert side.net.scores == net_par_except({1: 6})


def test_r7_a_virtual_side_with_no_card_left_is_net_par() -> None:
    assert virtual_side([], [], TEE, 4) == Side((), NetCard(PARS))
    only = an_entry(net_par_except({1: 2}), player_id="ann", card_id="a")
    assert virtual_side([only], ["ann"], TEE, 4) == Side((), NetCard(PARS))
