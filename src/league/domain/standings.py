"""Season and segment tables from awards, and a round's winners from net entries (R10).

A table is one view of the same awards: the season's rounds, or one segment's, each with
its own optional best_n. The rounds passed in are the closed ones, because R10 counts
closed rounds only and which rounds are closed is a fact the caller holds, not something a
table carries. Points stay exact, so two competitors who should be level compare equal and
share a position (D14).
"""

from collections.abc import Sequence
from fractions import Fraction

from league.domain.facts import Segment, StandingsRule
from league.domain.results import NetEntry, RoundAwards, StandingsRow


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


def _round_total(competitor_id: str, round_awards: RoundAwards) -> Fraction | None:
    """That competitor's contest awards in one round, or None when they hold none.

    None rather than zero: best N chooses among the rounds a competitor scored in, so a round
    they did not score in must not displace a worse one they did.
    """
    contest = [
        award.points
        for award in round_awards.awards
        if award.competitor_id == competitor_id and award.reason != "manual"
    ]
    if not contest:
        return None
    return sum(contest, Fraction(0))


def _manual_points(competitor_id: str, rounds: Sequence[RoundAwards]) -> Fraction:
    """Every manual award of the table's rounds, in full: best N forgives golf, not a penalty."""
    return sum(
        (
            award.points
            for round_awards in rounds
            for award in round_awards.awards
            if award.competitor_id == competitor_id and award.reason == "manual"
        ),
        Fraction(0),
    )


def _points(competitor_id: str, rounds: Sequence[RoundAwards], best_n: int | None) -> Fraction:
    """One competitor's points in one table (R10)."""
    totals = [
        total
        for total in (_round_total(competitor_id, round_awards) for round_awards in rounds)
        if total is not None
    ]
    if best_n is not None:
        totals = sorted(totals, reverse=True)[:best_n]
    return sum(totals, Fraction(0)) + _manual_points(competitor_id, rounds)


def _positioned(ranked: Sequence[tuple[str, Fraction]]) -> tuple[StandingsRow, ...]:
    """Rows in order, where competitors level on points share a position and skip the next."""
    rows: list[StandingsRow] = []
    for place, (competitor_id, points) in enumerate(ranked, start=1):
        level = bool(rows) and rows[-1].points == points
        rows.append(StandingsRow(rows[-1].position if level else place, competitor_id, points))
    return tuple(rows)


def standings(
    rounds: Sequence[RoundAwards],
    competitor_ids: Sequence[str],
    rule: StandingsRule,
    segment: Segment | None = None,
) -> tuple[StandingsRow, ...]:
    """The season table over those closed rounds, or that segment's, one row per competitor (R10).

    Ordered by points, then by competitor id so the table comes out the same every time. The
    rows of a shared position carry no order of merit, so a screen may sort them as it likes.
    """
    selected, best_n = _selected(rounds, rule, segment)
    points = {
        competitor_id: _points(competitor_id, selected, best_n) for competitor_id in competitor_ids
    }
    return _positioned(sorted(points.items(), key=lambda row: (-row[1], row[0])))


def round_winners(entries: Sequence[NetEntry]) -> tuple[str, ...]:
    """The competitors with the lowest net total among these entries, or none (R10).

    The caller passes one closed round's on-time entries netted at full playing handicap.
    Sorted by competitor id so a tie reads the same every time.
    """
    if not entries:
        return ()
    lowest = min(entry.net.total for entry in entries)
    return tuple(sorted(entry.competitor_id for entry in entries if entry.net.total == lowest))
