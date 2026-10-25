"""Pairing proposals (R11).

A proposal is not a fact: the admin edits it and publishing is what makes it one. So
nothing here reads a round, and the history a swiss proposal rests on is the published
pairings the caller hands in.

Swiss and teams share one pairing pass, which works over sides rather than players: a
swiss side is one player, a team side is one or two. They differ in which side plays
alone, and in that the team kinds pass no history, because sides are new each round, so
nobody has met and no side has played alone.
"""

from collections.abc import Mapping, Sequence
from fractions import Fraction
from random import Random

from league.domain.facts import Pairing
from league.domain.results import StandingsRow


def _ranked(standings: Sequence[StandingsRow], index_tenths: Mapping[str, int]) -> tuple[str, ...]:
    """Players best first: the standings order, a shared position broken by index then id."""
    ordered = sorted(
        standings,
        key=lambda row: (row.position, index_tenths[row.competitor_id], row.competitor_id),
    )
    return tuple(row.competitor_id for row in ordered)


def _met(history: Sequence[Sequence[Pairing]]) -> dict[frozenset[str], int]:
    """How recently each pair of players met, as the position of the round they last did.

    Every player of one side met every player of the other, so a best ball pairing is four
    meetings. A single-sided pairing has no opposite side and so is no meeting at all.
    """
    met: dict[frozenset[str], int] = {}
    for place, pairings in enumerate(history):
        for pairing in pairings:
            for player_id in pairing.a:
                for other_id in pairing.b:
                    met[frozenset((player_id, other_id))] = place
    return met


def _single_counts(history: Sequence[Sequence[Pairing]]) -> dict[str, int]:
    """How many published single-sided pairings each player has had this season.

    A player who met the virtual side under R9 was in no pairing, so they are not here.
    """
    counts: dict[str, int] = {}
    for pairings in history:
        for pairing in pairings:
            if not pairing.b:
                for player_id in pairing.a:
                    counts[player_id] = counts.get(player_id, 0) + 1
    return counts


def _swiss_alone(order: Sequence[str], counts: Mapping[str, int]) -> int | None:
    """Which player plays alone: fewest single-sided pairings, lowest-ranked of those.

    Settled before anything is paired, so the rotation decides it rather than whoever the
    pass from the top happens to leave over.
    """
    if len(order) % 2 == 0:
        return None
    return min(range(len(order)), key=lambda place: (counts.get(order[place], 0), -place))


def _team_alone(sides: Sequence[tuple[str, ...]]) -> int | None:
    """Which side plays alone: the one-member side if there is one, else the lowest-ranked.

    Like meets like. A two-player side's best ball beats a single virtual card, and a lone
    player facing a best ball of two is behind by as much, so an odd count puts the lone
    player against the virtual card and leaves the two-player sides to each other.
    """
    if len(sides) % 2 == 0:
        return None
    lone = [place for place, side in enumerate(sides) if len(side) == 1]
    return lone[0] if lone else len(sides) - 1


def _opponent(
    side: tuple[str, ...],
    pool: Sequence[tuple[str, ...]],
    met: Mapping[frozenset[str], int],
) -> int:
    """Who `side` meets: the highest-ranked it has not met, else the least recently met.

    Of those last met in the same round, as both players of a best ball side were, the
    highest-ranked, which is what ordering the pool best first already gives.
    """
    for place, other in enumerate(pool):
        if frozenset(side + other) not in met:
            return place
    return min(range(len(pool)), key=lambda place: (met[frozenset(side + pool[place])], place))


def _pair_from_the_top(
    sides: Sequence[tuple[str, ...]],
    met: Mapping[frozenset[str], int],
    alone: int | None,
) -> tuple[Pairing, ...]:
    """Sides, best first, paired from the top, with the one that plays alone taken out first."""
    pool = list(sides)
    single = pool.pop(alone) if alone is not None else None
    pairings: list[Pairing] = []
    while pool:
        side = pool.pop(0)
        pairings.append(Pairing(side, pool.pop(_opponent(side, pool, met))))
    if single is not None:
        pairings.append(Pairing(single))
    return tuple(pairings)


def _side_order(
    sides: Sequence[tuple[str, ...]],
    order: Sequence[str],
    standings: Sequence[StandingsRow],
) -> list[tuple[str, ...]]:
    """Sides best first by combined points, those level ordered by their best member."""
    points = {row.competitor_id: row.points for row in standings}
    rank = {player_id: place for place, player_id in enumerate(order)}
    return sorted(
        sides,
        key=lambda side: (
            -sum((points[player_id] for player_id in side), Fraction(0)),
            min(rank[player_id] for player_id in side),
        ),
    )


def _inward(order: Sequence[str]) -> list[tuple[str, ...]]:
    """Highest with lowest and so on inward, the middle player alone when odd."""
    sides: list[tuple[str, ...]] = [
        (order[place], order[-1 - place]) for place in range(len(order) // 2)
    ]
    if len(order) % 2:
        sides.append((order[len(order) // 2],))
    return sides


def _team_pairings(
    sides: Sequence[tuple[str, ...]],
    order: Sequence[str],
    standings: Sequence[StandingsRow],
) -> tuple[Pairing, ...]:
    """Sides, however they were formed, ordered by combined points and then paired (R11)."""
    ranked = _side_order(sides, order, standings)
    return _pair_from_the_top(ranked, {}, _team_alone(ranked))


def swiss_pairings(
    standings: Sequence[StandingsRow],
    index_tenths: Mapping[str, int],
    history: Sequence[Sequence[Pairing]],
) -> tuple[Pairing, ...]:
    """A swiss proposal of single sides for every player in `standings` (R11).

    `history` is this season's published pairings: one inner sequence per earlier round,
    oldest round first, holding every pairing of that round's duel contests together. Its
    position is all that is read, because R11 asks which meeting was the least recent, not
    which round number it fell in.
    """
    order = _ranked(standings, index_tenths)
    return _pair_from_the_top(
        [(player_id,) for player_id in order],
        _met(history),
        _swiss_alone(order, _single_counts(history)),
    )


def high_low_pairings(
    standings: Sequence[StandingsRow], index_tenths: Mapping[str, int]
) -> tuple[Pairing, ...]:
    """A team proposal whose sides join the highest-ranked with the lowest-ranked (R11)."""
    order = _ranked(standings, index_tenths)
    return _team_pairings(_inward(order), order, standings)


def random_pairings(
    standings: Sequence[StandingsRow], index_tenths: Mapping[str, int], rng_seed: int
) -> tuple[Pairing, ...]:
    """A team proposal whose sides are consecutive pairs of a seeded shuffle (R11)."""
    order = _ranked(standings, index_tenths)
    shuffled = list(order)
    Random(rng_seed).shuffle(shuffled)
    pairs = [tuple(shuffled[place : place + 2]) for place in range(0, len(shuffled), 2)]
    return _team_pairings(pairs, order, standings)
