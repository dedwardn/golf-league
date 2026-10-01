"""Derived results. Nothing here is ever stored."""

from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Literal


@dataclass(frozen=True)
class NetCard:
    scores: tuple[int, ...]

    @property
    def total(self) -> int:
        return sum(self.scores)


@dataclass(frozen=True)
class NetEntry:
    """One player's net card, with what identifies the card it was computed from."""

    card_id: str
    player_id: str
    submitted_at: datetime
    net: NetCard


@dataclass(frozen=True)
class Side:
    """What a duel compares (R7): the players who earn its points, and the net card.

    A virtual side has no players, because nobody earns its points.
    """

    player_ids: tuple[str, ...]
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
    """Points one player was given, with the outcome that earned them (R9).

    `key` names what gave them: a contest's key, or the admin's label on a manual award.
    """

    player_id: str
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
    """One player's line in one table (R10). Players level on points share a position."""

    position: int
    player_id: str
    points: Fraction
