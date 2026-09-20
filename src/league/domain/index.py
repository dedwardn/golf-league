"""Differential, index update and replay of a player's cards (R4, R5, R6)."""

from collections.abc import Sequence
from fractions import Fraction

from league.domain.facts import Card, IndexRule, Tee
from league.domain.rounding import round_half_up
from league.domain.strokes import SLOPE_BASE, TENTHS, allocate_strokes, playing_handicap

CAP_OVER_PAR = 2
MIN_INDEX_TENTHS = -50
MAX_INDEX_TENTHS = 540


def differential_tenths(card: Card, tee: Tee, index_tenths: int) -> int:
    """The card's capped total rebased onto slope 113, in tenths (R4).

    The strokes that set each hole's cap are R2's, at allowance 100.
    """
    strokes = allocate_strokes(playing_handicap(index_tenths, tee, 100), tee)
    capped = sum(
        min(gross, par + CAP_OVER_PAR + given)
        for gross, par, given in zip(card.scores, tee.pars, strokes, strict=True)
    )
    over_rating = TENTHS * capped - tee.course_rating_tenths
    return round_half_up(Fraction(SLOPE_BASE * over_rating, tee.slope))


def next_index_tenths(
    old_tenths: int, differential_tenths: int, rule: IndexRule, use_early_rate: bool
) -> int:
    """The index after this card: old moved toward the differential at the rule's rate (R5)."""
    if use_early_rate:
        rate = rule.early_rate
    else:
        rate = rule.rate_down if differential_tenths < old_tenths else rule.rate_up
    moved = round_half_up(old_tenths + Fraction(rate * (differential_tenths - old_tenths), 100))
    return max(MIN_INDEX_TENTHS, min(MAX_INDEX_TENTHS, moved))


def index_by_card_tenths(
    seed_index_tenths: int,
    provisional: bool,
    cards_with_tees: Sequence[tuple[Card, Tee]],
    rule: IndexRule,
) -> dict[str, int]:
    """Card id to the index that card was played off, for one player's counted cards (R6)."""
    ordered = sorted(cards_with_tees, key=lambda pair: (pair[0].submitted_at, pair[0].card_id))
    used: dict[str, int] = {}
    index_tenths = seed_index_tenths
    for played, (card, tee) in enumerate(ordered):
        if card.card_id in used:
            raise ValueError(f"card id {card.card_id!r} appears twice in one player's cards")
        used[card.card_id] = index_tenths
        index_tenths = next_index_tenths(
            index_tenths,
            differential_tenths(card, tee, index_tenths),
            rule,
            provisional and played < rule.early_cards,
        )
    return used
