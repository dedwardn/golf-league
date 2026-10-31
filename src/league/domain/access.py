"""What a player may see (R12) and which competitor they are (R15), whether a card is accepted
(R13), what is locked (R14, R15), and whether a round may open (R14) or reopen (R13).

Only R14's opening gate reads a draft round: acceptance never sees one, so refusing a card for a
draft round is the caller's. A voided card never reaches the domain, so the void itself is the
caller's too. After a void the holder has no counted card here, so a new one is accepted. The
admin always sees everything and does not ask R12.
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


def takes_team_card(round_: RoundFacts) -> bool:
    """R15: a shared-ball round takes one team card per team, and no card of a player's own."""
    return isinstance(round_.format, ScrambleFormat | GreensomeFormat | FoursomeFormat)


def _holds_card(player_id: str, round_: RoundFacts, teams: Mapping[str, str]) -> bool:
    """Whether the counted card a player hands in for a round is in (R15).

    It is their own, or in a shared-ball round their team's team card. A viewer may be a league
    player outside this season, who is in no team and so holds no card.
    """
    if takes_team_card(round_):
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


def competitor_of(player_id: str, facts: SeasonFacts) -> str | None:
    """Whose row is that player's: their team's in a team season, or None for one outside it.

    In an individual season it is their own, whatever season team a teambonus reads (R15),
    and None without a seed index, since only a seeded player has a row (R10).
    """
    if facts.mode == "team":
        return facts.teams.get(player_id)
    return player_id if player_id in facts.seed_index_tenths else None


def seed_index_locked(facts: SeasonFacts) -> bool:
    """R15: a team season's seed indexes are locked while any round is closed.

    A correction would rewrite every round already played. No rule locks a seed index in an
    individual season.
    """
    return facts.mode == "team" and any(round_.closed_at is not None for round_ in facts.rounds)


def tee_locked(rounds: Iterable[RoundFacts]) -> bool:
    """R14: a tee is locked once a card or a team card exists on it.

    `rounds` is every round, of any season, that uses the tee. A voided card never reaches the
    domain, so it locks nothing.
    """
    return any(round_.cards or round_.team_cards for round_ in rounds)


def pairings_published(round_: RoundFacts) -> bool:
    """R14: every duel contest of the round has its published pairings, so the round may open.

    An empty list is not published, since R9 makes a duel without pairings an error.
    """
    return all(
        round_.pairings.get(contest.key) for contest in round_.contests if contest.kind == "duel"
    )


def may_reopen(round_: RoundFacts) -> bool:
    """R13: a closed round reopens only while it has no late card or late team card.

    Reopening clears closed_at, which would turn a late card into an on-time one.
    """
    closed_at = round_.closed_at
    if closed_at is None:
        return False
    held = (*round_.cards.values(), *round_.team_cards.values())
    return all(card.submitted_at <= closed_at for card in held)
