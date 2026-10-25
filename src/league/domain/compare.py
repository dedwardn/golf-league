"""Comparing two sides on a basis (R8)."""

from league.domain.configs import Basis
from league.domain.facts import Tee
from league.domain.results import Comparison, Side
from league.domain.strokes import stableford_points


def compare(a: Side, b: Side, basis: Basis, tee: Tee) -> Comparison:
    """Which side wins on this basis, and the margin in that basis' own unit (R8)."""
    if basis == "holes":
        holes = list(zip(a.net.scores, b.net.scores, strict=True))
        a_score = sum(1 for one, other in holes if one < other)
        b_score = sum(1 for one, other in holes if other < one)
    elif basis == "stableford":
        a_score = sum(stableford_points(a.net, tee))
        b_score = sum(stableford_points(b.net, tee))
    else:
        # total: the lower total wins, so its sign is flipped and one comparison serves all three.
        a_score, b_score = -a.net.total, -b.net.total
    if a_score == b_score:
        return Comparison(None, 0)
    return Comparison(a if a_score > b_score else b, abs(a_score - b_score))
