"""Playing handicap, stroke allocation, net card and stableford points (R1, R2, R3)."""

from fractions import Fraction

from league.domain.facts import HOLES, Card, Tee
from league.domain.results import NetCard
from league.domain.rounding import round_half_up

SLOPE_BASE = 113
TENTHS = 10


def playing_handicap(index_tenths: int, tee: Tee, allowance: int) -> int:
    """Whole strokes the player receives on this tee under this allowance (R1)."""
    course = SLOPE_BASE * (tee.course_rating_tenths - TENTHS * tee.par_total)
    exact = Fraction(allowance * (index_tenths * tee.slope + course), SLOPE_BASE * TENTHS * 100)
    return round_half_up(exact)


def allocate_strokes(playing_handicap: int, tee: Tee) -> tuple[int, ...]:
    """Strokes received on each hole, in hole order (R2)."""
    if playing_handicap < -HOLES:
        raise ValueError(f"a playing handicap below -{HOLES} cannot be allocated")
    if playing_handicap < 0:
        cutoff = HOLES + playing_handicap
        return tuple(-1 if index > cutoff else 0 for index in tee.stroke_indexes)
    whole, extra = divmod(playing_handicap, HOLES)
    return tuple(whole + (1 if index <= extra else 0) for index in tee.stroke_indexes)


def net_card(card: Card, tee: Tee, playing_handicap: int) -> NetCard:
    """The card's gross scores less the strokes allocated for this playing handicap (R3)."""
    strokes = allocate_strokes(playing_handicap, tee)
    return NetCard(tuple(gross - given for gross, given in zip(card.scores, strokes, strict=True)))


def stableford_points(net: NetCard, tee: Tee) -> tuple[int, ...]:
    """Points on each hole: max(0, 2 + par - net) (R3)."""
    return tuple(max(0, 2 + par - score) for par, score in zip(tee.pars, net.scores, strict=True))
