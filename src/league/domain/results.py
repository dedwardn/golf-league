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
Reason = DuelReason | Literal["position", "record"]


@dataclass(frozen=True)
class Award:
    """Points one contest gave one player, with the outcome that earned them (R9)."""

    player_id: str
    contest_key: str
    points: Fraction
    reason: Reason
