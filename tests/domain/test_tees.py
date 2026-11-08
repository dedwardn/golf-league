from dataclasses import replace

import pytest
from conftest import PARS, STROKE_INDEXES

from league.domain.tees import Tee


def a_tee(
    pars: tuple[int, ...] = PARS,
    stroke_indexes: tuple[int, ...] = STROKE_INDEXES,
) -> Tee:
    return Tee("Course", "White", pars, stroke_indexes, course_rating_tenths=732, slope=131)


def test_r13_tee_has_a_course_name() -> None:
    with pytest.raises(ValueError, match="a tee has a course name"):
        replace(a_tee(), course="")


def test_r13_tee_has_a_tee_name() -> None:
    with pytest.raises(ValueError, match="a tee has a tee name"):
        replace(a_tee(), name="")


@pytest.mark.parametrize("tenths", [500, 900])
def test_r13_tee_takes_a_course_rating_of_50_0_and_90_0(tenths: int) -> None:
    assert replace(a_tee(), course_rating_tenths=tenths).course_rating_tenths == tenths


@pytest.mark.parametrize("tenths", [0, 499, 901])
def test_r13_tee_course_rating_is_50_0_to_90_0(tenths: int) -> None:
    with pytest.raises(ValueError, match=r"a course rating is 50\.0 to 90\.0"):
        replace(a_tee(), course_rating_tenths=tenths)


@pytest.mark.parametrize("slope", [55, 155])
def test_r13_tee_takes_a_slope_of_55_and_155(slope: int) -> None:
    assert replace(a_tee(), slope=slope).slope == slope


@pytest.mark.parametrize("slope", [-113, 0, 54, 156])
def test_r13_tee_slope_is_55_to_155(slope: int) -> None:
    with pytest.raises(ValueError, match="a slope is 55 to 155"):
        replace(a_tee(), slope=slope)


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
