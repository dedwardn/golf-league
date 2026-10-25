"""Building single, bestball and virtual sides (R7).

A side is built from net cards the caller has already computed at the contest's
allowance, and from on-time entries only. This module has no concept of a round: which
cards a contest may refer to, and on which tee, is settled before the entries get here.
"""

from collections.abc import Sequence
from fractions import Fraction

from league.domain.facts import Tee
from league.domain.results import NetCard, NetEntry, Side
from league.domain.rounding import round_half_up


def single_side(entry: NetEntry) -> Side:
    """One competitor's net card as a side (R7)."""
    return Side((entry.competitor_id,), entry.net)


def bestball_side(members: Sequence[NetEntry]) -> Side | None:
    """The lowest net score per hole among the members (R7).

    None is R7's missing side. A single side cannot be missing in the same way, because
    a caller with no entry has nothing to pass to single_side at all.
    """
    if not members:
        return None
    holes = zip(*(member.net.scores for member in members), strict=True)
    return Side(
        tuple(member.competitor_id for member in members),
        NetCard(tuple(min(hole) for hole in holes)),
    )


def virtual_side(
    references: Sequence[NetEntry],
    opponent_competitor_ids: Sequence[str],
    tee: Tee,
    virtual_n: int,
) -> Side:
    """The rounded mean of the best virtual_n reference cards, or net par (R7)."""
    kept = sorted(
        (entry for entry in references if entry.competitor_id not in opponent_competitor_ids),
        key=lambda entry: (entry.net.total, entry.submitted_at, entry.card_id),
    )[:virtual_n]
    if not kept:
        return Side((), NetCard(tee.pars))
    holes = zip(*(entry.net.scores for entry in kept), strict=True)
    return Side((), NetCard(tuple(round_half_up(Fraction(sum(h), len(kept))) for h in holes)))
