from datetime import datetime

import pytest
from conftest import PARS, STROKE_INDEXES, SUBMITTED_AT, TEE, a_card, an_index_rule

from league.domain.index import (
    differential_tenths,
    index_by_card_tenths,
    next_index_tenths,
)

# Par plus one on every hole, plus one more on the first five: 95 gross, and on TEE off
# index 0.0 no hole reaches its cap, so the capped total is 95 as in the R4 example.
SCORES_95 = (6, 6, 5, 7, 6, 5, 4, 5, 6, 5, 5, 4, 6, 5, 5, 4, 5, 6)
SCORES_BLOWN = (15,) * 18

RULE = an_index_rule()

# Rate 100 makes the new index the differential itself, so a replay is readable by hand.
FOLLOW = an_index_rule(early_rate=100, early_cards=0, rate_down=100, rate_up=100)
# Follows the differential while provisional and early, then freezes at rate 0.
EARLY_ONLY = an_index_rule(early_rate=100, early_cards=2, rate_down=0, rate_up=0)

FIRST = SUBMITTED_AT
SECOND = datetime(2026, 1, 12, 18, 0)
THIRD = datetime(2026, 1, 19, 18, 0)
FOURTH = datetime(2026, 1, 26, 18, 0)


def test_r4_capped_total_95_on_rating_73_2_slope_131_gives_18_8() -> None:
    card = a_card(SCORES_95)
    # Pins the fixture, not the code: an edit to SCORES_95 would otherwise leave this
    # test passing while proving something other than the R4 example.
    assert sum(card.scores) == 95
    assert differential_tenths(card, TEE, 0) == 188


def test_r4_a_blow_up_hole_is_capped_at_par_plus_two() -> None:
    # Stroke index 15 gets no stroke off index 0.0, so its cap is par 3 plus 2.
    hole = STROKE_INDEXES.index(15)
    assert PARS[hole] == 3
    assert SCORES_95[hole] == 5
    blown = (*SCORES_95[:hole], 12, *SCORES_95[hole + 1 :])
    assert differential_tenths(a_card(blown), TEE, 0) == 188


def test_r4_a_stroke_raises_that_hole_s_cap() -> None:
    # Off index 0.0 the playing handicap is 1, so only stroke index 1 has a cap of par + 3.
    struck = STROKE_INDEXES.index(1)
    plain = STROKE_INDEXES.index(3)
    assert PARS[struck] == PARS[plain] == 4
    gross: list[int] = list(PARS)
    gross[struck] = 7
    # Capped total 75: the 7 stands under a cap of 4 + 2 + 1.
    assert differential_tenths(a_card(tuple(gross)), TEE, 0) == 16
    gross = list(PARS)
    gross[plain] = 7
    # Capped total 74: the same 7 is cut to 6 under a cap of 4 + 2 + 0.
    assert differential_tenths(a_card(tuple(gross)), TEE, 0) == 7


def test_r4_a_plus_handicap_lowers_the_cap() -> None:
    # Index -2.4 gives a playing handicap of -2, so stroke indexes 17 and 18 lose a stroke
    # and their cap falls to par + 2 - 1.
    hole = STROKE_INDEXES.index(17)
    assert PARS[hole] == 3
    gross: list[int] = list(PARS)
    gross[hole] = 9
    # Capped total 73: the 9 is cut to 4.
    assert differential_tenths(a_card(tuple(gross)), TEE, -24) == -2


def test_r5_old_18_4_with_differential_14_2_gives_16_3() -> None:
    assert next_index_tenths(184, 142, RULE, use_early_rate=False) == 163


def test_r5_old_18_4_with_differential_25_0_gives_20_4() -> None:
    assert next_index_tenths(184, 250, RULE, use_early_rate=False) == 204


def test_r5_the_early_rate_is_used_whichever_way_the_index_moves() -> None:
    # 18.4 + 70% of -4.2 is 15.46, which is 15.5 half up, not the 16.3 that rate_down gives.
    assert next_index_tenths(184, 142, RULE, use_early_rate=True) == 155


def test_r5_clamps_at_minus_5_0() -> None:
    assert next_index_tenths(-40, -500, RULE, use_early_rate=False) == -50


def test_r5_clamps_at_54_0() -> None:
    assert next_index_tenths(500, 900, RULE, use_early_rate=False) == 540


def test_r6_the_first_card_is_played_off_the_seed_index() -> None:
    card = a_card(SCORES_95, card_id="a")
    assert index_by_card_tenths(184, False, [(card, TEE)], FOLLOW) == {"a": 184}


def test_r6_a_later_card_uses_the_index_the_earlier_card_produced() -> None:
    first = a_card(SCORES_95, card_id="a", submitted_at=FIRST)
    second = a_card(SCORES_BLOWN, card_id="b", submitted_at=SECOND)
    used = index_by_card_tenths(0, False, [(first, TEE), (second, TEE)], FOLLOW)
    assert used == {"a": 0, "b": 188}


def test_r6_replay_is_ordered_by_submitted_at() -> None:
    # The blown card was handed in first, so it replays first although its id sorts last.
    late = a_card(SCORES_95, card_id="a", submitted_at=SECOND)
    early = a_card(SCORES_BLOWN, card_id="b", submitted_at=FIRST)
    used = index_by_card_tenths(0, False, [(late, TEE), (early, TEE)], FOLLOW)
    assert used == {"b": 0, "a": 309}


def test_r6_a_tie_on_submitted_at_is_broken_by_card_id() -> None:
    # Same instant, and the list is in the other order, so only the id can decide.
    lower_id = a_card(SCORES_95, card_id="a", submitted_at=FIRST)
    higher_id = a_card(SCORES_BLOWN, card_id="b", submitted_at=FIRST)
    used = index_by_card_tenths(0, False, [(higher_id, TEE), (lower_id, TEE)], FOLLOW)
    assert used == {"a": 0, "b": 188}


def test_r6_leaving_a_card_out_changes_later_indexes() -> None:
    first = a_card(SCORES_95, card_id="a", submitted_at=FIRST)
    second = a_card(SCORES_BLOWN, card_id="b", submitted_at=SECOND)
    third = a_card(SCORES_95, card_id="c", submitted_at=THIRD)
    with_all = index_by_card_tenths(0, False, [(first, TEE), (second, TEE), (third, TEE)], FOLLOW)
    assert with_all == {"a": 0, "b": 188, "c": 499}
    without_second = index_by_card_tenths(0, False, [(first, TEE), (third, TEE)], FOLLOW)
    assert without_second == {"a": 0, "c": 188}


def test_r6_early_rate_ends_after_early_cards() -> None:
    cards = [
        (a_card(SCORES_95, card_id="a", submitted_at=FIRST), TEE),
        (a_card(SCORES_BLOWN, card_id="b", submitted_at=SECOND), TEE),
        (a_card(SCORES_95, card_id="c", submitted_at=THIRD), TEE),
        (a_card(SCORES_95, card_id="d", submitted_at=FOURTH), TEE),
    ]
    # The first two cards move at early_rate 100. The third and fourth fall back to the
    # rates of 0, so the index the third card produced is still in force for the fourth.
    assert index_by_card_tenths(0, True, cards, EARLY_ONLY) == {
        "a": 0,
        "b": 188,
        "c": 499,
        "d": 499,
    }


def test_r6_a_non_provisional_player_never_uses_the_early_rate() -> None:
    cards = [
        (a_card(SCORES_95, card_id="a", submitted_at=FIRST), TEE),
        (a_card(SCORES_BLOWN, card_id="b", submitted_at=SECOND), TEE),
        (a_card(SCORES_95, card_id="c", submitted_at=THIRD), TEE),
    ]
    # With rate_down and rate_up at 0 the index never moves off the seed.
    assert index_by_card_tenths(0, False, cards, EARLY_ONLY) == {"a": 0, "b": 0, "c": 0}


def test_r13_a_repeated_card_id_is_an_error() -> None:
    first = a_card(SCORES_95, card_id="a", submitted_at=FIRST)
    again = a_card(SCORES_BLOWN, card_id="a", submitted_at=SECOND)
    with pytest.raises(ValueError, match="twice"):
        index_by_card_tenths(0, False, [(first, TEE), (again, TEE)], FOLLOW)
