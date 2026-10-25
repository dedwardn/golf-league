"""Input facts and the shape checks of R13."""

from collections.abc import Mapping
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
MIN_BEST_N = 1
MIN_ROUND = 1
MIN_ALLOWANCE = 0
MAX_ALLOWANCE = 100

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


def _check_best_n(best_n: int | None) -> None:
    """R10's bound on a table's best_n, which a rule and each of its segments share."""
    if best_n is not None and best_n < MIN_BEST_N:
        raise ValueError(f"best_n is {MIN_BEST_N} or more")


@dataclass(frozen=True)
class Segment:
    """A named, inclusive range of rounds with its own optional best_n (R10)."""

    name: str
    first_round: int
    last_round: int
    best_n: int | None = None

    def __post_init__(self) -> None:
        if self.first_round < MIN_ROUND:
            raise ValueError(f"a segment's first round is {MIN_ROUND} or more")
        if self.last_round < self.first_round:
            raise ValueError("a segment's last round is no earlier than its first")
        _check_best_n(self.best_n)


@dataclass(frozen=True)
class StandingsRule:
    """How a table sums round totals (R10): all of them, or the best best_n of them."""

    best_n: int | None = None
    segments: tuple[Segment, ...] = ()

    def __post_init__(self) -> None:
        _check_best_n(self.best_n)
        names = [segment.name for segment in self.segments]
        if len(set(names)) != len(names):
            raise ValueError("segment names are unique in the season")


@dataclass(frozen=True)
class Pairing:
    """The one or two sides that meet in a duel (R9), each named by its players."""

    a: tuple[str, ...]
    b: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.a:
            raise ValueError("a pairing has at least one side")


def _check_allowance(allowance: int) -> None:
    """R9's bound on the allowance of every contest that reads cards."""
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
class ManualAward:
    """Points the admin gave one competitor in one round by hand (R9).

    `key` is the admin's label for the award, such as longest-drive, not an identifier:
    one adjustment handed to two competitors in a round is one label on two awards.
    """

    competitor_id: str
    key: str
    points: Fraction


@dataclass(frozen=True)
class RoundFacts:
    """One round as the pipeline reads it.

    `cards` maps each player id to their one counted card (R13), and `pairings` each duel
    contest's key to its published pairings. `closed_at` is None while the round is open.
    """

    number: int
    tee: Tee
    contests: tuple[ContestConfig, ...]
    cards: Mapping[str, Card]
    pairings: Mapping[str, tuple[Pairing, ...]]
    manual: tuple[ManualAward, ...]
    closed_at: datetime | None

    def __post_init__(self) -> None:
        keys = [contest.key for contest in self.contests]
        if len(set(keys)) != len(keys):
            raise ValueError("a contest key is unique in its round")
        duels = {contest.key for contest in self.contests if contest.kind == "duel"}
        if any(
            contest.kind == "teambonus" and contest.source not in duels for contest in self.contests
        ):
            raise ValueError("a teambonus source names a duel contest of its round")


def _check_reference_rounds(round_: RoundFacts, tees: Mapping[int, Tee]) -> None:
    """R7: a duel's reference rounds are distinct rounds of the season, none later than its own.

    A later round would go on changing a closed round's virtual side as its cards arrive.
    """
    for contest in round_.contests:
        if contest.kind != "duel":
            continue
        if len(set(contest.reference_rounds)) != len(contest.reference_rounds):
            raise ValueError("a duel's reference rounds are distinct")
        for number in contest.reference_rounds:
            if number not in tees:
                raise ValueError(f"reference round {number} is no round of the season")
            if number > round_.number:
                raise ValueError(f"reference round {number} is later than round {round_.number}")
            # A virtual side meets its opponent hole by hole, so its cards share their tee.
            if tees[number] != round_.tee:
                raise ValueError(f"reference round {number} is on another tee")


@dataclass(frozen=True)
class SeasonFacts:
    """One season's facts: its open and closed rounds and what every table is built from.

    A draft round has no cards and is not here. `seed_index_tenths` names every seeded player.
    """

    rounds: tuple[RoundFacts, ...]
    seed_index_tenths: Mapping[str, int]
    provisional: frozenset[str]
    index_rule: IndexRule
    standings_rule: StandingsRule
    teams: Mapping[str, str]

    def __post_init__(self) -> None:
        numbers = [round_.number for round_ in self.rounds]
        if len(set(numbers)) != len(numbers):
            raise ValueError("a round's number is unique in its season")
        tees = {round_.number: round_.tee for round_ in self.rounds}
        for round_ in self.rounds:
            _check_reference_rounds(round_, tees)
