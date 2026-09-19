"""Derived results. Nothing here is ever stored."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NetCard:
    scores: tuple[int, ...]

    @property
    def total(self) -> int:
        return sum(self.scores)
