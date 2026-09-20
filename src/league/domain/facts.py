"""Input facts and the shape checks of R13."""

from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Literal

HOLES = 18
MIN_PAR = 3
MAX_PAR = 6
MIN_RATE = 0
MAX_RATE = 100
MIN_VIRTUAL_N = 1

Basis = Literal["holes", "total", "stableford"]


@dataclass(frozen=True)
class Tee:
    pars: tuple[int, ...]
    stroke_indexes: tuple[int, ...]
    course_rating_tenths: int
    slope: int

    def __post_init__(self) -> None:
        if len(self.pars) != HOLES:
            raise ValueError(f"a tee has {HOLES} pars, got {len(self.pars)}")
        if any(par < MIN_PAR or par > MAX_PAR for par in self.pars):
            raise ValueError(f"every par is {MIN_PAR} to {MAX_PAR}")
        if len(self.stroke_indexes) != HOLES:
            raise ValueError(f"a tee has {HOLES} stroke indexes, got {len(self.stroke_indexes)}")
        if sorted(self.stroke_indexes) != list(range(1, HOLES + 1)):
            raise ValueError(f"stroke indexes are 1 to {HOLES}, once each")

    @property
    def par_total(self) -> int:
        return sum(self.pars)


@dataclass(frozen=True)
class Card:
    """One player's 18 gross hole scores for one round."""

    card_id: str
    submitted_at: datetime
    scores: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.scores) != HOLES:
            raise ValueError(f"a card has {HOLES} scores, got {len(self.scores)}")
        if any(score < 1 for score in self.scores):
            raise ValueError("every score is 1 or more")


@dataclass(frozen=True)
class IndexRule:
    """How fast an index follows a differential (R5). The rates are whole percents."""

    early_rate: int
    early_cards: int
    rate_down: int
    rate_up: int

    def __post_init__(self) -> None:
        rates = (self.early_rate, self.rate_down, self.rate_up)
        if any(rate < MIN_RATE or rate > MAX_RATE for rate in rates):
            raise ValueError(f"every rate is a whole percent from {MIN_RATE} to {MAX_RATE}")
        if self.early_cards < 0:
            raise ValueError("early_cards is 0 or more")


@dataclass(frozen=True)
class Pairing:
    """The one or two sides that meet in a duel (R9), each named by its players."""

    a: tuple[str, ...]
    b: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.a:
            raise ValueError("a pairing has at least one side")


@dataclass(frozen=True)
class ContestConfig:
    """One contest's config (R9). Points are exact, so they are Fractions (D14)."""

    key: str
    basis: Basis
    points_win: Fraction
    points_draw: Fraction
    points_loss: Fraction
    side: Literal["single", "bestball"]
    multiplier: int = 1
    virtual_n: int = 4

    def __post_init__(self) -> None:
        if self.virtual_n < MIN_VIRTUAL_N:
            raise ValueError(f"virtual_n is {MIN_VIRTUAL_N} or more")
