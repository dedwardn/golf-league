"""Turning one contest's config, pairings and net entries into awards (R9).

Entries arrive netted at the contest's allowance. The cards a duel's virtual side draws on
arrive separately, as references: this round's on-time entries when the contest names no
reference rounds (R7), or those of the rounds it names. Which rounds a contest may refer to,
and on which tee, is resolved, and each round's cards filtered against its own close, before
a contest gets here.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from fractions import Fraction

from league.domain.compare import compare
from league.domain.facts import (
    AllplayConfig,
    Basis,
    DuelConfig,
    FieldConfig,
    ManualAward,
    Pairing,
    TeamBonusConfig,
    Tee,
)
from league.domain.results import Award, Comparison, ContestEntries, DuelReason, NetEntry, Side
from league.domain.sides import bestball_side, single_side, virtual_side


def is_on_time(entry: NetEntry, closed_at: datetime | None) -> bool:
    """A counted card at or before the close, or any card while the round is open."""
    return closed_at is None or entry.submitted_at <= closed_at


def duel_awards(
    contest: ContestEntries,
    references: Sequence[NetEntry],
    pairings: Sequence[Pairing],
    config: DuelConfig,
) -> tuple[Award, ...]:
    """Every award one duel contest produces (R9).

    In pairing order, then one for each card the pairings left without an award, in
    entry order. Every virtual side is drawn from references, which are on-time entries.
    """
    if not pairings:
        raise ValueError("a duel needs pairings")
    on_time = [entry for entry in contest.entries if is_on_time(entry, contest.closed_at)]
    awards: list[Award] = []
    for pairing in pairings:
        awards.extend(_pairing_awards(pairing, on_time, references, contest.tee, config))
    earned = {award.player_id for award in awards}
    # R9: an award decides who is swept, not a points total, so a player who lost where
    # points_loss is 0 is in this set and does not meet the virtual side as well.
    for entry in contest.entries:
        if entry.player_id not in earned:
            awards.extend(_alone_awards(entry, references, contest.tee, config))
    return tuple(awards)


def _declared_side(
    player_ids: Sequence[str], on_time: Sequence[NetEntry], config: DuelConfig
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
    pairing: Pairing,
    on_time: Sequence[NetEntry],
    references: Sequence[NetEntry],
    tee: Tee,
    config: DuelConfig,
) -> list[Award]:
    """One pairing under R8, with a virtual side for a side that is missing or absent."""
    a = _declared_side(pairing.a, on_time, config)
    b = _declared_side(pairing.b, on_time, config)
    if a is None and b is None:
        # R9: with nobody to play, the pairing gives nothing and each card is on its own.
        return []
    side_a = a if a is not None else virtual_side(references, pairing.b, tee, config.virtual_n)
    side_b = b if b is not None else virtual_side(references, pairing.a, tee, config.virtual_n)
    return _outcome_awards(side_a, side_b, tee, config)


def _alone_awards(
    entry: NetEntry, references: Sequence[NetEntry], tee: Tee, config: DuelConfig
) -> list[Award]:
    """A card from a player with no award meets the virtual side alone (R9).

    Late, or on time and in no pairing. The pool is the references, fixed before the sweep
    starts, so giving its player an award changes nobody else's.
    """
    side = single_side(entry)
    virtual = virtual_side(references, side.player_ids, tee, config.virtual_n)
    return _outcome_awards(side, virtual, tee, config)


def _side_awards(side: Side, reason: DuelReason, config: DuelConfig) -> list[Award]:
    """That side's points to each of its players. A virtual side has none, so earns none."""
    points = {
        "win": config.points_win,
        "draw": config.points_draw,
        "loss": config.points_loss,
    }[reason] * config.multiplier
    return [Award(player_id, config.key, points, reason) for player_id in side.player_ids]


def _outcome_awards(a: Side, b: Side, tee: Tee, config: DuelConfig) -> list[Award]:
    """What the two sides earned under R8, side a's players first."""
    result = compare(a, b, config.basis, tee)
    if result.winner is None:
        return _side_awards(a, "draw", config) + _side_awards(b, "draw", config)
    if result.winner is a:
        return _side_awards(a, "win", config) + _side_awards(b, "loss", config)
    return _side_awards(a, "loss", config) + _side_awards(b, "win", config)


def _on_time_sides(contest: ContestEntries) -> list[Side]:
    """Field and allplay rank on-time single sides only: late cards score only in duels."""
    return [single_side(entry) for entry in contest.entries if is_on_time(entry, contest.closed_at)]


def _against_field(side: Side, sides: Sequence[Side], basis: Basis, tee: Tee) -> list[Comparison]:
    """That side compared under R8 with every other side of the field."""
    return [compare(side, other, basis, tee) for other in sides if other is not side]


def field_awards(contest: ContestEntries, config: FieldConfig) -> tuple[Award, ...]:
    """Each on-time player's position_points (R9), in entry order.

    A side's position is one more than the sides that beat it under R8, so the direction
    of better stays in compare, and the sides it ties with share the positions after it.
    """
    sides = _on_time_sides(contest)
    awards: list[Award] = []
    for side in sides:
        results = _against_field(side, sides, config.basis, contest.tee)
        beaten_by = sum(
            1 for result in results if result.winner is not None and result.winner is not side
        )
        group = 1 + sum(1 for result in results if result.winner is None)
        # A slice past the end of the list is short, which scores the missing places 0.
        shared = config.position_points[beaten_by : beaten_by + group]
        points = sum(shared, Fraction(0)) / group * config.multiplier
        awards.append(Award(side.player_ids[0], config.key, points, "position"))
    return tuple(awards)


def allplay_awards(contest: ContestEntries, config: AllplayConfig) -> tuple[Award, ...]:
    """Each on-time player's record, scale * (wins + draws / 2) / (n - 1) (R9), in entry order."""
    sides = _on_time_sides(contest)
    if len(sides) <= 1:
        # With one card there is no one to play, and n - 1 is zero.
        return ()
    awards: list[Award] = []
    for side in sides:
        results = _against_field(side, sides, config.basis, contest.tee)
        wins = sum(1 for result in results if result.winner is side)
        draws = sum(1 for result in results if result.winner is None)
        record = config.scale * (wins + Fraction(draws, 2)) / (len(sides) - 1)
        awards.append(Award(side.player_ids[0], config.key, record * config.multiplier, "record"))
    return tuple(awards)


def teambonus_awards(
    entries: Sequence[NetEntry],
    closed_at: datetime | None,
    round_awards: Sequence[Award],
    teams: Mapping[str, str],
    config: TeamBonusConfig,
) -> tuple[Award, ...]:
    """The bonus to each on-time member of the team that won the source contest (R9).

    Takes no tee: nothing here is netted or compared. A team with no on-time card has
    nothing to sum and does not enter the ranking, so it cannot share away a bonus from
    a team that played. Teams level at the top share one bonus, exactly.
    """
    members = [
        entry.player_id
        for entry in entries
        if is_on_time(entry, closed_at) and entry.player_id in teams
    ]
    if not members:
        return ()
    sums = {teams[player_id]: Fraction(0) for player_id in members}
    for award in round_awards:
        if award.key == config.source and award.player_id in members:
            sums[teams[award.player_id]] += award.points
    best = max(sums.values())
    top = {team for team, total in sums.items() if total == best}
    share = config.bonus * config.multiplier / len(top)
    return tuple(
        Award(player_id, config.key, share, "bonus")
        for player_id in members
        if teams[player_id] in top
    )


def manual_awards(manual: Sequence[ManualAward]) -> tuple[Award, ...]:
    """What the admin gave by hand, as awards (R9): the points as they are, no multiplier."""
    return tuple(Award(award.player_id, award.key, award.points, "manual") for award in manual)
