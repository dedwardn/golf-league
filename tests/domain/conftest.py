from datetime import datetime

from league.domain.facts import Card, IndexRule, Tee

PARS = (4, 4, 3, 5, 4, 4, 3, 4, 5, 4, 4, 3, 5, 4, 4, 3, 4, 5)
STROKE_INDEXES = (1, 11, 15, 5, 3, 9, 17, 7, 13, 2, 12, 16, 6, 4, 10, 18, 8, 14)

# Par 72, rating 73.2, slope 131: the tee of the R1 worked example.
TEE = Tee(PARS, STROKE_INDEXES, course_rating_tenths=732, slope=131)

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
