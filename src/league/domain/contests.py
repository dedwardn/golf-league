"""Turning one duel contest's config, pairings and net entries into awards (R9).

Entries arrive netted at the contest's allowance, and the cards a virtual side may draw
on are this round's on-time entries: R7's default reference round. Which other rounds a
contest may refer to, and on which tee, is resolved before a contest gets here.
"""

from collections.abc import Sequence
from datetime import datetime

from league.domain.compare import compare
from league.domain.facts import ContestConfig, Pairing, Tee
from league.domain.results import Award, NetEntry, Reason, Side
from league.domain.sides import bestball_side, single_side, virtual_side


def _is_on_time(entry: NetEntry, closed_at: datetime | None) -> bool:
    """A counted card at or before the close, or any card while the round is open."""
    return closed_at is None or entry.submitted_at <= closed_at


def duel_awards(
    entries: Sequence[NetEntry],
    tee: Tee,
    closed_at: datetime | None,
    pairings: Sequence[Pairing],
    config: ContestConfig,
) -> tuple[Award, ...]:
    """Every award one duel contest produces (R9), in pairing order and late cards last."""
    on_time = [entry for entry in entries if _is_on_time(entry, closed_at)]
    awards: list[Award] = []
    for pairing in pairings:
        awards.extend(_pairing_awards(pairing, on_time, tee, config))
    # R13 gives a player one counted card per round, so a player with a late card has
    # none among the sides above: R9's "got no points in this contest" is automatic.
    for entry in entries:
        if not _is_on_time(entry, closed_at):
            awards.extend(_late_awards(entry, on_time, tee, config))
    return tuple(awards)


def _declared_side(
    player_ids: Sequence[str], on_time: Sequence[NetEntry], config: ContestConfig
) -> Side | None:
    """The side those players present, or None when none of them has an on-time card."""
    if config.side == "single" and len(player_ids) > 1:
        raise ValueError("a single side names exactly one player")
    members = [entry for entry in on_time if entry.player_id in player_ids]
    if not members:
        return None
    if config.side == "single":
        return single_side(members[0])
    return bestball_side(members)


def _pairing_awards(
    pairing: Pairing, on_time: Sequence[NetEntry], tee: Tee, config: ContestConfig
) -> list[Award]:
    """One pairing under R8, with a virtual side for a side that is missing or absent."""
    a = _declared_side(pairing.a, on_time, config)
    b = _declared_side(pairing.b, on_time, config)
    if a is None and b is None:
        # R9: with nobody to play, the pairing gives nothing and each late card is on its own.
        return []
    side_a = a if a is not None else virtual_side(on_time, pairing.b, tee, config.virtual_n)
    side_b = b if b is not None else virtual_side(on_time, pairing.a, tee, config.virtual_n)
    return _outcome_awards(side_a, side_b, tee, config)


def _late_awards(
    entry: NetEntry, on_time: Sequence[NetEntry], tee: Tee, config: ContestConfig
) -> list[Award]:
    """A late card from a player who earned nothing meets the virtual side alone (R9)."""
    side = single_side(entry)
    virtual = virtual_side(on_time, side.player_ids, tee, config.virtual_n)
    return _outcome_awards(side, virtual, tee, config)


def _side_awards(side: Side, reason: Reason, config: ContestConfig) -> list[Award]:
    """That side's points to each of its players. A virtual side has none, so earns none."""
    points = {
        "win": config.points_win,
        "draw": config.points_draw,
        "loss": config.points_loss,
    }[reason] * config.multiplier
    return [Award(player_id, config.key, points, reason) for player_id in side.player_ids]


def _outcome_awards(a: Side, b: Side, tee: Tee, config: ContestConfig) -> list[Award]:
    """What the two sides earned under R8, side a's players first."""
    result = compare(a, b, config.basis, tee)
    if result.winner is None:
        return _side_awards(a, "draw", config) + _side_awards(b, "draw", config)
    if result.winner is a:
        return _side_awards(a, "win", config) + _side_awards(b, "loss", config)
    return _side_awards(a, "loss", config) + _side_awards(b, "win", config)
