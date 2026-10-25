"""What a player may see (R12), whether a card is accepted (R13), and what is locked (R14, R15).

Neither a draft round nor a voided card reaches the domain, so refusing a card for a draft
round, and the void itself, are the caller's. After a void the holder has no counted card here,
so a new one is accepted. The admin always sees everything and does not ask R12.
"""

from collections.abc import Iterable, Mapping
from datetime import datetime

from league.domain.configs import FoursomeFormat, GreensomeFormat, ScrambleFormat
from league.domain.facts import RoundFacts, SeasonFacts


def _takes_cards(round_: RoundFacts, now: datetime) -> bool:
    """R13: open, or closed with late_until set and now at or before it."""
    if round_.closed_at is None:
        return True
    return round_.late_until is not None and now <= round_.late_until


def _holds_card(player_id: str, round_: RoundFacts, teams: Mapping[str, str]) -> bool:
    """Whether the counted card a player hands in for a round is in (R15).

    It is their own, or in a shared-ball round their team's team card. A viewer may be a league
    player outside this season, who is in no team and so holds no card.
    """
    if isinstance(round_.format, ScrambleFormat | GreensomeFormat | FoursomeFormat):
        team_id = teams.get(player_id)
        return team_id is not None and team_id in round_.team_cards
    return player_id in round_.cards


def accepts_card(player_id: str, round_: RoundFacts, facts: SeasonFacts, now: datetime) -> bool:
    """R13 and R15: whether the round takes the card this player hands in now.

    Only a player with a seed index for the season hands one in, since every card is played
    off it. The card is their own, or in a shared-ball round their team's team card, and its
    holder has one counted card per round.
    """
    if player_id not in facts.seed_index_tenths:
        return False
    return _takes_cards(round_, now) and not _holds_card(player_id, round_, facts.teams)


def sees_round(viewer_id: str, round_: RoundFacts, teams: Mapping[str, str], now: datetime) -> bool:
    """R12: whether a player sees a round's cards and results.

    Once the card they hand in is in, or once the round takes no more cards: closed, with
    late_until unset or past. Until then a late card never meets a virtual side they have seen.
    """
    return _holds_card(viewer_id, round_, teams) or not _takes_cards(round_, now)


def seed_index_locked(facts: SeasonFacts) -> bool:
    """R15: a team season's seed indexes lock once round one closes.

    A later correction would rewrite every round already played. No rule locks a seed index
    in an individual season.
    """
    return facts.mode == "team" and any(
        round_.number == 1 and round_.closed_at is not None for round_ in facts.rounds
    )


def tee_locked(rounds: Iterable[RoundFacts]) -> bool:
    """R14: a tee is locked once a card or a team card exists on it.

    `rounds` is every round, of any season, that uses the tee. A voided card never reaches the
    domain, so it locks nothing.
    """
    return any(round_.cards or round_.team_cards for round_ in rounds)
