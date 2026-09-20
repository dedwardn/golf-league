import pytest
from conftest import PARS, STROKE_INDEXES, a_card, an_index_rule

from league.domain.facts import Tee


def a_tee(
    pars: tuple[int, ...] = PARS,
    stroke_indexes: tuple[int, ...] = STROKE_INDEXES,
) -> Tee:
    return Tee(pars, stroke_indexes, course_rating_tenths=732, slope=131)


def test_r13_a_well_formed_tee_and_card_are_accepted() -> None:
    tee = a_tee()
    assert tee.par_total == 72
    assert a_card((4,) * 18).scores == (4,) * 18


def test_r13_tee_needs_eighteen_pars() -> None:
    with pytest.raises(ValueError, match="18 pars"):
        a_tee(pars=PARS[:17])


def test_r13_tee_pars_are_three_to_six() -> None:
    with pytest.raises(ValueError, match="3 to 6"):
        a_tee(pars=(7, *PARS[1:]))


def test_r13_tee_needs_eighteen_stroke_indexes() -> None:
    with pytest.raises(ValueError, match="18 stroke indexes"):
        a_tee(stroke_indexes=STROKE_INDEXES[:17])


def test_r13_tee_stroke_indexes_are_one_to_eighteen_once_each() -> None:
    with pytest.raises(ValueError, match="1 to 18"):
        a_tee(stroke_indexes=(1, *STROKE_INDEXES[2:], 1))


def test_r13_card_needs_eighteen_scores() -> None:
    with pytest.raises(ValueError, match="18 scores"):
        a_card((4,) * 17)


def test_r13_card_scores_are_one_or_more() -> None:
    with pytest.raises(ValueError, match="1 or more"):
        a_card((0,) + (4,) * 17)


def test_r5_index_rule_rates_of_zero_and_one_hundred_are_legal() -> None:
    # A rate of 0 freezes the index, 100 makes it follow the differential exactly.
    rule = an_index_rule(early_rate=0, early_cards=0, rate_down=100, rate_up=100)
    assert rule.rate_down == 100


def test_r5_index_rule_rates_are_not_negative() -> None:
    with pytest.raises(ValueError, match="0 to 100"):
        an_index_rule(rate_down=-1)


def test_r5_index_rule_rates_are_not_above_one_hundred() -> None:
    with pytest.raises(ValueError, match="0 to 100"):
        an_index_rule(early_rate=101)


def test_r5_index_rule_early_cards_is_zero_or_more() -> None:
    with pytest.raises(ValueError, match="0 or more"):
        an_index_rule(early_cards=-1)
