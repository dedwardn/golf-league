"""How a round is scored, as config, and R9's and R16's bounds on it."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

MIN_VIRTUAL_N = 1
MIN_ALLOWANCE = 0
MAX_ALLOWANCE = 100

Basis = Literal["holes", "total", "stableford"]


def _check_allowance(allowance: int) -> None:
    """R9's bound on the allowance of every contest that reads cards, and R16's on a format's."""
    if allowance < MIN_ALLOWANCE or allowance > MAX_ALLOWANCE:
        raise ValueError(f"allowance is a whole percent from {MIN_ALLOWANCE} to {MAX_ALLOWANCE}")


@dataclass(frozen=True)
class DuelConfig:
    """One duel contest's config (R9). Points are exact, so they are Fractions (D14)."""

    key: str
    basis: Basis
    points_win: Fraction
    points_draw: Fraction
    points_loss: Fraction
    side: Literal["single", "bestball"]
    multiplier: int = 1
    virtual_n: int = 4
    allowance: int = 100
    # The round numbers a virtual side is drawn from (R7). Empty means this round.
    reference_rounds: tuple[int, ...] = ()
    kind: Literal["duel"] = "duel"

    def __post_init__(self) -> None:
        if self.virtual_n < MIN_VIRTUAL_N:
            raise ValueError(f"virtual_n is {MIN_VIRTUAL_N} or more")
        _check_allowance(self.allowance)


@dataclass(frozen=True)
class FieldConfig:
    """One field contest's config (R9): points by position, first place first."""

    key: str
    basis: Basis
    position_points: tuple[Fraction, ...]
    multiplier: int = 1
    allowance: int = 100
    kind: Literal["field"] = "field"

    def __post_init__(self) -> None:
        # Holes is a basis for two sides meeting, and has no order over a whole field.
        if self.basis == "holes":
            raise ValueError("a field ranks on total or stableford")
        _check_allowance(self.allowance)


@dataclass(frozen=True)
class AllplayConfig:
    """One allplay contest's config (R9): scale is what a clean sweep of the field earns."""

    key: str
    basis: Basis
    scale: Fraction
    multiplier: int = 1
    allowance: int = 100
    kind: Literal["allplay"] = "allplay"

    def __post_init__(self) -> None:
        _check_allowance(self.allowance)


@dataclass(frozen=True)
class TeamBonusConfig:
    """One teambonus contest's config (R9): `source` is a duel contest of the same round.

    A teambonus reads that contest's awards rather than cards, so it nets nothing and
    compares nothing, and has neither an allowance nor a basis.
    """

    key: str
    source: str
    bonus: Fraction
    multiplier: int = 1
    kind: Literal["teambonus"] = "teambonus"


ContestConfig = DuelConfig | FieldConfig | AllplayConfig | TeamBonusConfig


@dataclass(frozen=True)
class BestballFormat:
    """Each player plays off their own playing handicap at `allowance` (R16)."""

    allowance: int = 85
    format: Literal["bestball"] = "bestball"

    def __post_init__(self) -> None:
        _check_allowance(self.allowance)


@dataclass(frozen=True)
class CombinedFormat:
    """Each player plays off their own playing handicap at `allowance` (R16)."""

    allowance: int = 100
    format: Literal["combined"] = "combined"

    def __post_init__(self) -> None:
        _check_allowance(self.allowance)


@dataclass(frozen=True)
class ScrambleFormat:
    """`low` weighs the lower course handicap and `high` the higher (R16)."""

    low: int = 35
    high: int = 15
    format: Literal["scramble"] = "scramble"

    def __post_init__(self) -> None:
        _check_allowance(self.low)
        _check_allowance(self.high)


@dataclass(frozen=True)
class GreensomeFormat:
    """`low` weighs the lower course handicap and `high` the higher, as in scramble (R16)."""

    low: int = 60
    high: int = 40
    format: Literal["greensome"] = "greensome"

    def __post_init__(self) -> None:
        _check_allowance(self.low)
        _check_allowance(self.high)


@dataclass(frozen=True)
class FoursomeFormat:
    """`allowance` is taken of the two course handicaps summed (R16)."""

    allowance: int = 50
    format: Literal["foursome"] = "foursome"

    def __post_init__(self) -> None:
        _check_allowance(self.allowance)
