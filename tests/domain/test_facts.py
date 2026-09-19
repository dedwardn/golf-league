import pytest
from conftest import PARS, STROKE_INDEXES

from league.domain.facts import Card, Tee


def a_tee(
    pars: tuple[int, ...] = PARS,
    stroke_indexes: tuple[int, ...] = STROKE_INDEXES,
) -> Tee:
    return Tee(pars, stroke_indexes, course_rating_tenths=732, slope=131)


def test_r13_a_well_formed_tee_and_card_are_accepted() -> None:
    tee = a_tee()
    assert tee.par_total == 72
    assert Card((4,) * 18).scores == (4,) * 18


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
        Card((4,) * 17)


def test_r13_card_scores_are_one_or_more() -> None:
    with pytest.raises(ValueError, match="1 or more"):
        Card((0,) + (4,) * 17)
