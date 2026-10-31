"""Input facts and the shape checks of R13 and R15."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction

from league.domain.configs import ContestConfig, FormatConfig

HOLES = 18
MIN_PAR = 3
MAX_PAR = 6
MIN_RATE = 0
MAX_RATE = 100
MIN_BEST_N = 1
MIN_ROUND = 1
TEAM_SIZE = 2
MODES = ("individual", "team")


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
    """One player's, or in a shared-ball round one team's, 18 gross hole scores for one round."""

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
    In a team season `format` says how a team's score is made (R17), and in a shared-ball
    round `team_cards` maps each team id to its one counted team card. The format carries
    the allowance there, so a contest's own is not read (R15). `late_until`, when set, is how
    long a closed round still accepts a late card (R13): acceptance and visibility read it, and
    compute_season does not.
    """

    number: int
    tee: Tee
    contests: tuple[ContestConfig, ...]
    cards: Mapping[str, Card]
    pairings: Mapping[str, tuple[Pairing, ...]]
    manual: tuple[ManualAward, ...]
    closed_at: datetime | None
    format: FormatConfig | None = None
    team_cards: Mapping[str, Card] = field(default_factory=dict[str, Card])
    late_until: datetime | None = None

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


def _check_team_season(facts: "SeasonFacts") -> None:
    """R15: every seeded player in a team of two, every round with a format, field or allplay.

    No team's id is a seeded player's id, which keeps the two kinds of id apart on a screen.
    """
    for player_id in facts.seed_index_tenths:
        if player_id not in facts.teams:
            raise ValueError(f"seeded player {player_id} is in no team")
    if any(size != TEAM_SIZE for size in Counter(facts.teams.values()).values()):
        raise ValueError("every team of a team season has two players")
    if not facts.seed_index_tenths.keys().isdisjoint(facts.teams.values()):
        raise ValueError("no team's id is a seeded player's id")
    for round_ in facts.rounds:
        if round_.format is None:
            raise ValueError(f"round {round_.number} of a team season has no format")
        if any(contest.kind not in ("field", "allplay") for contest in round_.contests):
            raise ValueError("a team season's contests are field or allplay")


def _check_manual_awards(facts: "SeasonFacts") -> None:
    """R9: a manual award names a competitor of the season, or no table would ever show it."""
    team = facts.mode == "team"
    competitors = set(facts.teams.values()) if team else set(facts.seed_index_tenths)
    for round_ in facts.rounds:
        for award in round_.manual:
            if award.competitor_id not in competitors:
                raise ValueError(
                    f"manual award {award.key} in round {round_.number} names no competitor"
                )


@dataclass(frozen=True)
class SeasonFacts:
    """One season's facts: its open and closed rounds and what every table is built from.

    A draft round has no cards and is not here. `seed_index_tenths` names every seeded player.
    In a team season `teams` makes the competitors (R15). `mode` is a plain str with a run-time
    check rather than a Literal, because it arrives from storage, where no type reaches.
    """

    rounds: tuple[RoundFacts, ...]
    seed_index_tenths: Mapping[str, int]
    provisional: frozenset[str]
    index_rule: IndexRule
    standings_rule: StandingsRule
    teams: Mapping[str, str]
    mode: str = "individual"

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError("a season's mode is individual or team")
        numbers = [round_.number for round_ in self.rounds]
        if len(set(numbers)) != len(numbers):
            raise ValueError("a round's number is unique in its season")
        tees = {round_.number: round_.tee for round_ in self.rounds}
        for round_ in self.rounds:
            _check_reference_rounds(round_, tees)
        if self.mode == "team":
            _check_team_season(self)
        _check_manual_awards(self)
