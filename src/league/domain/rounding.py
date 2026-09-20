"""Half-up rounding over exact arithmetic (the arithmetic rule).

One function serves every rule that rounds. R1 rounds to a whole stroke; R4 and R5
round to one decimal, which is the same operation because one-decimal values are held
in tenths as integers, so rounding to one decimal is rounding the tenths to an integer.
"""

import math
from fractions import Fraction


def round_half_up(value: Fraction) -> int:
    """floor(x + 1/2). Python's round sends an exact half to even, which the spec forbids."""
    return math.floor(value + Fraction(1, 2))
