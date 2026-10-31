"""Derived results. Nothing here is ever stored."""

from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Literal

from league.domain.facts import Tee
from league.domain.rounding import round_half_up


@dataclass(frozen=True)
class NetCard:
    scores: tuple[int, ...]

    @property
    def total(self) -> int:
        return sum(self.scores)


@dataclass(frozen=True)
class NetEntry:
    """One competitor's net card, with what identifies the card it was computed from."""

    card_id: str
    competitor_id: str
    submitted_at: datetime
    net: NetCard


@dataclass(frozen=True)
class ContestEntries:
    """What one card-reading contest reads: the bundle, not a result.

    The entries are netted at that contest's allowance, `tee` is the tee they were netted on
    and `closed_at` decides which of them are on time (None while the round is open).
    """

    tee: Tee
    closed_at: datetime | None
    entries: tuple[NetEntry, ...]


@dataclass(frozen=True)
class Side:
    """What a duel compares (R7): the competitors who earn its points, and the net card.

    A virtual side has no competitors, because nobody earns its points.
    """

    competitor_ids: tuple[str, ...]
    net: NetCard


@dataclass(frozen=True)
class Comparison:
    """How one comparison came out (R8). A draw has no winner and a margin of 0."""

    winner: Side | None
    margin: int


DuelReason = Literal["win", "draw", "loss"]
Reason = DuelReason | Literal["position", "record", "bonus", "manual"]


@dataclass(frozen=True)
class Award:
    """Points one competitor was given, with the outcome that earned them (R9).

    `key` names what gave them: a contest's key, or the admin's label on a manual award.
    """

    competitor_id: str
    key: str
    points: Fraction
    reason: Reason


@dataclass(frozen=True)
class RoundAwards:
    """One round as a standings table reads it (R10): which round, what it awarded, who played.

    `card_holders` are the competitors with a counted card in the round, or in a team season
    the teams with a score (R17). Ids only: a table counts them and never reads a card.
    """

    number: int
    awards: tuple[Award, ...]
    card_holders: tuple[str, ...]


def points_text(points: Fraction) -> str:
    """Points to one decimal, half up, for a screen. Order and positions read the exact points."""
    tenths = round_half_up(points * 10)
    whole, tenth = divmod(abs(tenths), 10)
    return f"{'-' if tenths < 0 else ''}{whole}.{tenth}"


@dataclass(frozen=True)
class RoundTotal:
    """One round total on one table (R10), and whether that table's best N dropped it."""

    points: Fraction
    dropped: bool

    @property
    def points_text(self) -> str:
        return points_text(self.points)


_ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}
_TEENS = range(11, 14)


def _ordinal(position: int) -> str:
    """1st, 2nd, 3rd, 4th, where the teens all take th."""
    suffix = _ORDINAL_SUFFIXES.get(position % 10, "th")
    return f"{position}{'th' if position % 100 in _TEENS else suffix}"


@dataclass(frozen=True)
class Gap:
    """How far a row is behind the place above it, and that place's position.

    The points are the exact difference, so the shown gap can differ by a tenth from the
    difference of the two shown points.
    """

    points: Fraction
    position: int

    @property
    def text(self) -> str:
        return f"{points_text(self.points)} to {_ordinal(self.position)}"


@dataclass(frozen=True)
class StandingsRow:
    """One competitor's line in one table (R10). Competitors level on points share a position.

    `counted_cards` covers the table's rounds. `round_totals` holds them in round order, leaving
    out a round without a contest award. The row at the top has no `gap`.
    """

    position: int
    competitor_id: str
    points: Fraction
    counted_cards: int
    round_totals: tuple[RoundTotal, ...]
    gap: Gap | None

    @property
    def points_text(self) -> str:
        return points_text(self.points)


@dataclass(frozen=True)
class RoundView:
    """One round as a screen reads it: its awards and its winners (R10, or R15 in a team season).

    `winners` is empty while the round is open, and for a closed round with no on-time card
    (R10) or, in a team season, no award from a contest (R15). `winning_total` is what won the
    round, such as "70 net" or in a team season "3.0 points", and None when nobody did.
    """

    awards: RoundAwards
    winners: tuple[str, ...]
    winning_total: str | None


@dataclass(frozen=True)
class SegmentView:
    """One segment's table (R10), under the name and with the best_n the standings rule gives it."""

    name: str
    rows: tuple[StandingsRow, ...]
    best_n: int | None


@dataclass(frozen=True)
class SeasonView:
    """Each round, the season table with its best_n, each segment's, and whose row is the viewer's.

    compute_season sees no viewer, so `viewer_competitor` is None until a service shapes the
    view for one, and stays None for a viewer who is no competitor.
    """

    rounds: tuple[RoundView, ...]
    standings: tuple[StandingsRow, ...]
    segments: tuple[SegmentView, ...]
    best_n: int | None
    viewer_competitor: str | None
