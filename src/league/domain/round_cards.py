"""One round's Cards card on the admin's round screen (SPEC section 7): who holds a card in the
round, and each counted card or team card with its id, which correcting and voiding name it by.

It calls access.py and teams.py and holds no rule of its own.
"""

from dataclasses import dataclass

from league.domain.access import takes_team_card
from league.domain.facts import Card, SeasonFacts
from league.domain.teams import team_members


@dataclass(frozen=True)
class RoundCard:
    """One row: a player in an own-ball round, a team in a shared-ball one, and its counted card
    or team card, or None while it has none."""

    holder: str
    card: Card | None

    @property
    def gross(self) -> int | None:
        return None if self.card is None else sum(self.card.scores)


def round_cards(facts: SeasonFacts, number: int) -> tuple[RoundCard, ...]:
    """The rows of the season's open or closed round of that number, its teams in team id order
    and each team's players together in player id order (R15).

    No row for a round not in the facts, a draft among them, and none in an individual season,
    whose card list is S21's.
    """
    round_ = facts.round(number)
    if facts.mode != "team" or round_ is None:
        return ()
    teams = sorted(team_members(facts.teams).items())
    if takes_team_card(round_):
        return tuple(RoundCard(team_id, round_.team_cards.get(team_id)) for team_id, _ in teams)
    return tuple(
        RoundCard(player_id, round_.cards.get(player_id))
        for _, players in teams
        for player_id in players
    )


def card_row(rows: tuple[RoundCard, ...], card_id: str) -> RoundCard | None:
    """The row that holds the counted card or team card of that id, or None when no row does."""
    return next((row for row in rows if row.card and row.card.card_id == card_id), None)
