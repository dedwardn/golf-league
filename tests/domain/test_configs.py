from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction

import pytest
from conftest import a_duel, a_field

from league.domain.configs import (
    AllplayConfig,
    BestballFormat,
    CombinedFormat,
    FieldConfig,
    FoursomeFormat,
    GreensomeFormat,
    ScrambleFormat,
)


def test_r9_virtual_n_is_one_or_more() -> None:
    with pytest.raises(ValueError, match="1 or more"):
        replace(a_duel(), virtual_n=0)


def test_r9_a_field_ranks_on_total_or_stableford_never_holes() -> None:
    with pytest.raises(ValueError, match="total or stableford"):
        FieldConfig(key="field", basis="holes", position_points=(Fraction(3),))


def test_r9_an_allowance_outside_0_to_100_is_an_error() -> None:
    with pytest.raises(ValueError, match="allowance"):
        replace(a_duel(), allowance=-1)
    with pytest.raises(ValueError, match="allowance"):
        replace(a_field(), allowance=101)
    with pytest.raises(ValueError, match="allowance"):
        AllplayConfig("allplay", "total", Fraction(2), allowance=-1)


def test_r9_allowances_of_0_and_100_are_accepted() -> None:
    assert replace(a_duel(), allowance=0).allowance == 0
    assert replace(a_field(), allowance=100).allowance == 100


# Each allowance of each format set alone, the rest at R16's defaults, and read back.
SET_ALONE: tuple[Callable[[int], int], ...] = (
    lambda allowance: BestballFormat(allowance=allowance).allowance,
    lambda allowance: CombinedFormat(allowance=allowance).allowance,
    lambda allowance: ScrambleFormat(low=allowance).low,
    lambda allowance: ScrambleFormat(high=allowance).high,
    lambda allowance: GreensomeFormat(low=allowance).low,
    lambda allowance: GreensomeFormat(high=allowance).high,
    lambda allowance: FoursomeFormat(allowance=allowance).allowance,
)


@pytest.mark.parametrize("set_alone", SET_ALONE)
@pytest.mark.parametrize("allowance", [-1, 101])
def test_r16_an_allowance_outside_0_to_100_is_an_error(
    set_alone: Callable[[int], int], allowance: int
) -> None:
    with pytest.raises(ValueError, match="allowance"):
        set_alone(allowance)


@pytest.mark.parametrize("set_alone", SET_ALONE)
@pytest.mark.parametrize("allowance", [0, 100])
def test_r16_allowances_of_0_and_100_are_accepted(
    set_alone: Callable[[int], int], allowance: int
) -> None:
    assert set_alone(allowance) == allowance
