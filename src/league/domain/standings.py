"""Season and segment tables from awards, and a round's winners from net entries (R10).

In a team season a round's winners come from round totals instead (R15).

A table is one view of the same awards: the season's rounds, or one segment's, each with
its own optional best_n. The rounds passed in are the closed ones, because R10 counts
closed rounds only and which rounds are closed is a fact the caller holds, not something a
table carries. Points stay exact, so two competitors who should be level compare equal and
share a position (D14).
"""

from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction

from league.domain.facts import Segment, StandingsRule
from league.domain.results import Gap, NetEntry, RoundAwards, RoundTotal, StandingsRow


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


def _round_totals(
    competitor_id: str, rounds: Sequence[RoundAwards], best_n: int | None
) -> tuple[RoundTotal, ...]:
    """One competitor's round totals in round order, those best N leaves out marked dropped."""
    totals = [
        total
        for total in (_round_total(competitor_id, round_awards) for round_awards in rounds)
        if total is not None
    ]
    # The sort is stable, so of equal totals the earlier round is the one kept.
    kept = set(sorted(range(len(totals)), key=lambda at: -totals[at])[:best_n])
    return tuple(RoundTotal(total, at not in kept) for at, total in enumerate(totals))


def _points(
    competitor_id: str, rounds: Sequence[RoundAwards], round_totals: Iterable[RoundTotal]
) -> Fraction:
    """One competitor's points in one table (R10): what best N kept, then every manual award."""
    kept = sum((total.points for total in round_totals if not total.dropped), Fraction(0))
    return kept + _manual_points(competitor_id, rounds)


def _place(above: StandingsRow | None, place: int, points: Fraction) -> tuple[int, Gap | None]:
    """A row's position and gap, from the row above it and its place in the order.

    Competitors level on points share a position, so they share the place above it too.
    """
    if above is None:
        return place, None
    if above.points == points:
        return above.position, above.gap
    return place, Gap(above.points - points, above.position)


def _positioned(
    ranked: Sequence[tuple[str, Fraction]],
    rounds: Sequence[RoundAwards],
    round_totals: Mapping[str, tuple[RoundTotal, ...]],
) -> tuple[StandingsRow, ...]:
    """Rows in order, where competitors level on points share a position and skip the next."""
    rows: list[StandingsRow] = []
    for place, (competitor_id, points) in enumerate(ranked, start=1):
        position, gap = _place(rows[-1] if rows else None, place, points)
        counted = sum(competitor_id in round_awards.card_holders for round_awards in rounds)
        rows.append(
            StandingsRow(position, competitor_id, points, counted, round_totals[competitor_id], gap)
        )
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
    round_totals = {
        competitor_id: _round_totals(competitor_id, selected, best_n)
        for competitor_id in competitor_ids
    }
    points = {
        competitor_id: _points(competitor_id, selected, round_totals[competitor_id])
        for competitor_id in competitor_ids
    }
    ranked = sorted(points.items(), key=lambda row: (-row[1], row[0]))
    return _positioned(ranked, selected, round_totals)


def winning_net_total(entries: Sequence[NetEntry]) -> int | None:
    """The lowest net total among these entries, or None without one (R10)."""
    return min((entry.net.total for entry in entries), default=None)


def round_winners(entries: Sequence[NetEntry]) -> tuple[str, ...]:
    """The competitors with the lowest net total among these entries, or none (R10).

    The caller passes one closed round's on-time entries netted at full playing handicap.
    Sorted by competitor id so a tie reads the same every time.
    """
    lowest = winning_net_total(entries)
    return tuple(sorted(entry.competitor_id for entry in entries if entry.net.total == lowest))


def _contest_totals(round_awards: RoundAwards) -> dict[str, Fraction]:
    """Each competitor's round total. One who holds only a manual award has none."""
    return {
        competitor_id: total
        for competitor_id in {award.competitor_id for award in round_awards.awards}
        if (total := _round_total(competitor_id, round_awards)) is not None
    }


def winning_round_total(round_awards: RoundAwards) -> Fraction | None:
    """The highest round total in a team season's round, or None without one (R15)."""
    return max(_contest_totals(round_awards).values(), default=None)


def team_round_winners(round_awards: RoundAwards) -> tuple[str, ...]:
    """The competitors with the highest round total in a team season's round, or none (R15).

    The caller passes a closed round. A team that holds only a manual award has no round
    total, so it is no winner. Sorted by competitor id so a tie reads the same every time.
    """
    highest = winning_round_total(round_awards)
    totals = _contest_totals(round_awards)
    return tuple(sorted(competitor for competitor, total in totals.items() if total == highest))
