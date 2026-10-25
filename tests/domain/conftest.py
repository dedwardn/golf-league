from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from fractions import Fraction

from league.domain.configs import DuelConfig, FieldConfig
from league.domain.facts import Card, IndexRule, RoundFacts, SeasonFacts, Tee
from league.domain.results import ContestEntries, NetCard, NetEntry

PARS = (4, 4, 3, 5, 4, 4, 3, 4, 5, 4, 4, 3, 5, 4, 4, 3, 4, 5)
STROKE_INDEXES = (1, 11, 15, 5, 3, 9, 17, 7, 13, 2, 12, 16, 6, 4, 10, 18, 8, 14)

# Par 72, rating 73.2, slope 131: the tee of the R1 worked example.
TEE = Tee(PARS, STROKE_INDEXES, course_rating_tenths=732, slope=131)

# Rating equal to par on slope 113, so R1 reduces to the index itself.
FLAT_TEE = Tee(PARS, STROKE_INDEXES, course_rating_tenths=720, slope=113)

SUBMITTED_AT = datetime(2026, 1, 5, 18, 0)


def a_card(
    scores: tuple[int, ...],
    card_id: str = "card-1",
    submitted_at: datetime = SUBMITTED_AT,
) -> Card:
    return Card(card_id, submitted_at, scores)


def an_index_rule(
    early_rate: int = 70,
    early_cards: int = 3,
    rate_down: int = 50,
    rate_up: int = 30,
) -> IndexRule:
    return IndexRule(early_rate, early_cards, rate_down, rate_up)


def net_par_except(changes: dict[int, int]) -> tuple[int, ...]:
    """Net par on every hole, with these hole numbers set to these net scores."""
    return tuple(changes.get(hole, par) for hole, par in enumerate(PARS, start=1))


def an_entry(
    scores: tuple[int, ...],
    competitor_id: str = "ann",
    card_id: str = "card-1",
    submitted_at: datetime = SUBMITTED_AT,
) -> NetEntry:
    return NetEntry(card_id, competitor_id, submitted_at, NetCard(scores))


CLOSED_AT = datetime(2026, 1, 5, 20, 0)
LATE = datetime(2026, 1, 6, 9, 0)


def net_total(total: int, competitor_id: str, submitted_at: datetime = CLOSED_AT) -> NetEntry:
    """An on-time entry whose net total is that, all of the difference on hole 1."""
    return an_entry(
        net_par_except({1: PARS[0] + total - sum(PARS)}),
        competitor_id=competitor_id,
        card_id=competitor_id,
        submitted_at=submitted_at,
    )


def a_contest(
    entries: Sequence[NetEntry], closed_at: datetime | None = CLOSED_AT
) -> ContestEntries:
    """What one contest reads: these entries on the R1 tee, against that close."""
    return ContestEntries(TEE, closed_at, tuple(entries))


def a_duel(key: str = "duel", reference_rounds: tuple[int, ...] = ()) -> DuelConfig:
    return DuelConfig(
        key,
        "total",
        points_win=Fraction(1),
        points_draw=Fraction(1, 2),
        points_loss=Fraction(0),
        side="single",
        reference_rounds=reference_rounds,
    )


def a_field(key: str = "field") -> FieldConfig:
    return FieldConfig(key, "total", (Fraction(1),))


def with_round(season: SeasonFacts, changed: RoundFacts) -> SeasonFacts:
    """The season with the round of that number replaced."""
    rounds = tuple(changed if old.number == changed.number else old for old in season.rounds)
    return replace(season, rounds=rounds)
