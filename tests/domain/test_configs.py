from dataclasses import replace
from fractions import Fraction

import pytest
from conftest import a_duel, a_field

from league.domain.configs import AllplayConfig, FieldConfig


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
