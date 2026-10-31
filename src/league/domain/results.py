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
    """One round as a standings table reads it (R10): which round, and what it awarded."""

    number: int
    awards: tuple[Award, ...]


@dataclass(frozen=True)
class StandingsRow:
    """One competitor's line in one table (R10). Competitors level on points share a position."""

    position: int
    competitor_id: str
    points: Fraction

    @property
    def points_text(self) -> str:
        """Points to one decimal, half up, for a screen. Order and positions read `points`."""
        tenths = round_half_up(self.points * 10)
        whole, tenth = divmod(abs(tenths), 10)
        return f"{'-' if tenths < 0 else ''}{whole}.{tenth}"


@dataclass(frozen=True)
class RoundView:
    """One round as a screen reads it: its awards and its winners (R10, or R15 in a team season).

    `winners` is empty while the round is open, and for a closed round with no on-time card
    (R10) or, in a team season, no award from a contest (R15).
    """

    awards: RoundAwards
    winners: tuple[str, ...]


@dataclass(frozen=True)
class SegmentView:
    """One segment's table (R10), under the name the standings rule gives it."""

    name: str
    rows: tuple[StandingsRow, ...]


@dataclass(frozen=True)
class SeasonView:
    """Everything compute_season derives: each round, the season table and each segment's."""

    rounds: tuple[RoundView, ...]
    standings: tuple[StandingsRow, ...]
    segments: tuple[SegmentView, ...]
