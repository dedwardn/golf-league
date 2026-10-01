"""Season and segment tables from awards (R10).

A table is one view of the same awards: the season's rounds, or one segment's, each with
its own optional best_n. The rounds passed in are the closed ones, because R10 counts
closed rounds only and which rounds are closed is a fact the caller holds, not something a
table carries. Points stay exact, so two players who should be level compare equal and
share a position (D14).
"""

from collections.abc import Sequence
from fractions import Fraction

from league.domain.facts import Segment, StandingsRule
from league.domain.results import RoundAwards, StandingsRow


def _selected(
    rounds: Sequence[RoundAwards], rule: StandingsRule, segment: Segment | None
) -> tuple[Sequence[RoundAwards], int | None]:
    """The rounds one table covers, and the best_n that table counts them with."""
    if segment is None:
        return rounds, rule.best_n
    in_range = [
        round_awards
        for round_awards in rounds
        if segment.first_round <= round_awards.number <= segment.last_round
    ]
    return in_range, segment.best_n


def _round_total(player_id: str, round_awards: RoundAwards) -> Fraction | None:
    """That player's contest awards in one round, or None when they hold none.

    None rather than zero: best N chooses among the rounds a player scored in, so a round
    they did not score in must not displace a worse one they did.
    """
    contest = [
        award.points
        for award in round_awards.awards
        if award.player_id == player_id and award.reason != "manual"
    ]
    if not contest:
        return None
    return sum(contest, Fraction(0))


def _manual_points(player_id: str, rounds: Sequence[RoundAwards]) -> Fraction:
    """Every manual award of the table's rounds, in full: best N forgives golf, not a penalty."""
    return sum(
        (
            award.points
            for round_awards in rounds
            for award in round_awards.awards
            if award.player_id == player_id and award.reason == "manual"
        ),
        Fraction(0),
    )


def _points(player_id: str, rounds: Sequence[RoundAwards], best_n: int | None) -> Fraction:
    """One player's points in one table (R10)."""
    totals = [
        total
        for total in (_round_total(player_id, round_awards) for round_awards in rounds)
        if total is not None
    ]
    if best_n is not None:
        totals = sorted(totals, reverse=True)[:best_n]
    return sum(totals, Fraction(0)) + _manual_points(player_id, rounds)


def _positioned(ranked: Sequence[tuple[str, Fraction]]) -> tuple[StandingsRow, ...]:
    """Rows in order, where players level on points share a position and skip the next."""
    rows: list[StandingsRow] = []
    for place, (player_id, points) in enumerate(ranked, start=1):
        level = bool(rows) and rows[-1].points == points
        rows.append(StandingsRow(rows[-1].position if level else place, player_id, points))
    return tuple(rows)


def standings(
    rounds: Sequence[RoundAwards],
    seeded_player_ids: Sequence[str],
    rule: StandingsRule,
    segment: Segment | None = None,
) -> tuple[StandingsRow, ...]:
    """The season table over those closed rounds, or that segment's, one row per player (R10).

    Ordered by points, then by player id so the table comes out the same every time. The
    rows of a shared position carry no order of merit, so a screen may sort them as it likes.
    """
    selected, best_n = _selected(rounds, rule, segment)
    points = {player_id: _points(player_id, selected, best_n) for player_id in seeded_player_ids}
    return _positioned(sorted(points.items(), key=lambda row: (-row[1], row[0])))
