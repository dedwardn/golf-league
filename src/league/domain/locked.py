"""One open round before playing (SPEC section 7), for a viewer from whom R12 hides it: who has
a score and who is waiting, per season team.

It calls access.py and teams.py and holds no rule of its own. A viewer without a card sees only
who has one (R12), so no score, card or result is on it.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from league.domain.access import accepts_card, holds_card, sees_round
from league.domain.facts import RoundHeading, SeasonFacts
from league.domain.results import SeasonView
from league.domain.teams import team_members

_Status = Literal["score_in", "one_of_two", "not_yet"]


@dataclass(frozen=True)
class LockedTeam:
    """One season team's row: whether it has a score (R17), or one of its two cards is in."""

    team_id: str
    status: _Status
    mine: bool


@dataclass(frozen=True)
class LockedRound:
    """The round before playing: every season team in team id order, and whether the round
    takes the viewer's card, so Register card shows."""

    number: int
    closes_at: datetime
    teams: tuple[LockedTeam, ...]
    takes_card: bool

    @property
    def with_score(self) -> int:
        return sum(team.status == "score_in" for team in self.teams)


def _status(scored: bool, cards: int) -> _Status:
    """A shared-ball team's players hold its team card together, so it is never one of two."""
    if scored:
        return "score_in"
    return "one_of_two" if cards == 1 else "not_yet"


def locked_round(
    facts: SeasonFacts, view: SeasonView, heading: RoundHeading, viewer_id: str, now: datetime
) -> LockedRound | None:
    """The open round of the heading for a viewer R12 hides it from.

    None in an individual season, whose screen is S21's, and for a viewer who sees the round,
    who reads its result instead. `view` is compute_season's, unfiltered, since who has a score
    is for everyone to see (R12).
    """
    if facts.mode != "team":
        return None
    round_ = {round_.number: round_ for round_ in facts.rounds}[heading.number]
    if sees_round(viewer_id, round_, facts.teams, now):
        return None
    scored = view.round(heading.number).awards.card_holders
    viewer_team = facts.teams.get(viewer_id)
    teams = tuple(
        LockedTeam(
            team_id,
            _status(
                team_id in scored,
                sum(holds_card(player_id, round_, facts.teams) for player_id in players),
            ),
            team_id == viewer_team,
        )
        for team_id, players in sorted(team_members(facts.teams).items())
    )
    return LockedRound(
        heading.number, heading.closes_at, teams, accepts_card(viewer_id, round_, facts, now)
    )
