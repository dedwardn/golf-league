"""What the admin does to run a round: open it, close it, undo a close (R13, R14), and put it
right with a manual award (R9) or a corrected or voided card (R13).

`now` is passed in, in naive UTC, so a test sets the time a round closes.
"""

from dataclasses import replace
from datetime import datetime

from sqlalchemy import Engine

from league.domain.access import may_reopen, pairings_published
from league.domain.facts import Card, ManualAward, SeasonFacts
from league.store.load import load_round, load_season_facts
from league.store.save import (
    save_manual_award,
    update_card_scores,
    update_card_voided,
    update_round_state,
)


def open_round(engine: Engine, season_id: str, number: int) -> None:
    """Open a draft round, or raise ValueError (R13, R14).

    A round with a duel contest opens only once that contest's pairings are published. Its config
    is locked from now on.
    """
    with engine.begin() as connection:
        draft = load_round(connection, season_id, number, "draft")
        if draft is None:
            raise ValueError(f"round {number} of season {season_id} is not a draft")
        if not pairings_published(draft):
            raise ValueError(f"round {number} of season {season_id} has unpublished pairings")
        update_round_state(connection, season_id, number, "open", None)


def close_round(engine: Engine, season_id: str, number: int, now: datetime) -> None:
    """Close an open round, recording now as its closed_at, or raise ValueError (R13)."""
    with engine.begin() as connection:
        if load_round(connection, season_id, number, "open") is None:
            raise ValueError(f"round {number} of season {season_id} is not open")
        update_round_state(connection, season_id, number, "closed", now)


def reopen_round(engine: Engine, season_id: str, number: int) -> None:
    """Undo a close, clearing closed_at, or raise ValueError (R13).

    Only a closed round with no late card or team card reopens, so no card changes standing.
    It is open again, not draft, so its config stays locked (R14).
    """
    with engine.begin() as connection:
        round_ = load_round(connection, season_id, number, "closed")
        if round_ is None or not may_reopen(round_):
            raise ValueError(f"round {number} of season {season_id} does not reopen")
        update_round_state(connection, season_id, number, "open", None)


def add_manual_award(engine: Engine, season_id: str, round_number: int, award: ManualAward) -> None:
    """Add the award after the round's earlier ones, or raise ValueError (R9).

    Only an open or closed round takes one: a draft is not in the season's facts, so it refuses
    the award as a round that does not exist does.
    """
    with engine.begin() as connection:
        facts = load_season_facts(connection, season_id)
        if round_number not in {round_.number for round_ in facts.rounds}:
            raise ValueError(f"season {season_id} has no open or closed round {round_number}")
        rounds = tuple(
            replace(round_, manual=(*round_.manual, award))
            if round_.number == round_number
            else round_
            for round_ in facts.rounds
        )
        # Built for its checks only, which refuse an award naming no competitor of the season.
        replace(facts, rounds=rounds)
        save_manual_award(connection, season_id, round_number, award)


def _counted_card(facts: SeasonFacts, card_id: str) -> Card:
    """The card or team card of that id, or ValueError. A voided card is not in the facts."""
    for round_ in facts.rounds:
        for card in (*round_.cards.values(), *round_.team_cards.values()):
            if card.card_id == card_id:
                return card
    raise ValueError(f"the season has no counted card {card_id}")


def correct_card(engine: Engine, season_id: str, card_id: str, scores: tuple[int, ...]) -> None:
    """Replace a counted card's hole scores, or raise ValueError (R13).

    It stays the same player's or team's card with the same submitted_at, so a correction never
    gives a shared-ball round a card of a player's own (R15), and an on-time card stays on time.
    """
    with engine.begin() as connection:
        card = _counted_card(load_season_facts(connection, season_id), card_id)
        update_card_scores(connection, season_id, replace(card, scores=scores))


def void_card(engine: Engine, season_id: str, card_id: str) -> None:
    """Void a counted card, or raise ValueError (R13).

    Its holder may then hand in a new one, if the round still takes cards.
    """
    with engine.begin() as connection:
        _counted_card(load_season_facts(connection, season_id), card_id)
        update_card_voided(connection, season_id, card_id)
