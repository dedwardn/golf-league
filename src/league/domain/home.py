"""One viewer's open rounds as home reads them (SPEC section 7), and the time left in a round.

It calls the modules that own the rules and holds no rule of its own. A team season plays every
card off the seed index (R15), so these are the strokes its rounds are scored with.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from league.domain.access import holds_card, takes_team_card
from league.domain.facts import RoundFacts, RoundHeading, SeasonFacts
from league.domain.results import SeasonView, StandingsRow
from league.domain.teams import team_handicaps, team_members

_DAY = timedelta(days=1)
_HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class HomePlayer:
    """One player of the viewer's team in an own-ball round: their strokes and their card."""

    player_id: str
    playing_handicap: int
    card_in: bool


@dataclass(frozen=True)
class HomeTeam:
    """The viewer's team in one round: its format, and whose strokes it plays off (R16).

    An own-ball round has `players`, the viewer first, and no `team_playing_handicap`. A
    shared-ball round has the reverse.
    """

    format: str
    players: tuple[HomePlayer, ...]
    team_playing_handicap: int | None


@dataclass(frozen=True)
class HomeRound:
    """One open round on a viewer's home (SPEC section 7).

    `card_holders` counts the round's, and `card_in` is whether the card the viewer hands in
    is in. `team` is None in an individual season and for a viewer outside the season.
    """

    number: int
    course: str
    tee_name: str
    closes_at: datetime
    time_left: str
    card_holders: int
    card_in: bool
    team: HomeTeam | None


@dataclass(frozen=True)
class HomeView:
    """A viewer's home: their open rounds and their row of the season table, None without one.

    `competitors` is what a round's `card_holders` is out of.
    """

    rounds: tuple[HomeRound, ...]
    row: StandingsRow | None
    competitors: int
    team_season: bool


def _units_left(count: int, unit: str) -> str:
    return f"{count} {unit}{'' if count == 1 else 's'} left"


def time_left(closes_at: datetime, now: datetime) -> str:
    """The time until the planned close, floored.

    The window is informational, so a round past it stays open until the admin closes it.
    """
    left = closes_at - now
    if left <= timedelta(0):
        return "Closing soon"
    if left >= _DAY:
        return _units_left(left // _DAY, "day")
    if left >= _HOUR:
        return _units_left(left // _HOUR, "hour")
    return "Under an hour left"


def _home_team(round_: RoundFacts, facts: SeasonFacts, viewer_id: str) -> HomeTeam | None:
    """The viewer's team in the round, or None in an individual season or outside the season."""
    team_id = facts.teams.get(viewer_id)
    if facts.mode != "team" or team_id is None:
        return None
    # SeasonFacts refuses a round of a team season without a format (R15).
    config = round_.format
    assert config is not None
    a, b = team_members(facts.teams)[team_id]
    partner_id = b if a == viewer_id else a
    seeds = facts.seed_index_tenths
    handicaps = team_handicaps((seeds[viewer_id], seeds[partner_id]), round_.tee, config)
    if takes_team_card(round_):
        (handicap,) = handicaps
        return HomeTeam(config.format, (), handicap)
    players = tuple(
        HomePlayer(player_id, handicap, holds_card(player_id, round_, facts.teams))
        for player_id, handicap in zip((viewer_id, partner_id), handicaps, strict=True)
    )
    return HomeTeam(config.format, players, None)


def home_rounds(
    facts: SeasonFacts,
    view: SeasonView,
    headings: Sequence[RoundHeading],
    viewer_id: str,
    now: datetime,
) -> tuple[HomeRound, ...]:
    """One block per heading, each read against its own round.

    Which rounds, and in what order, is the caller's. `view` is compute_season's, unfiltered:
    R12 lets a viewer without a card see who has one, so a round hidden from them keeps its count.
    """
    rounds = {round_.number: round_ for round_ in facts.rounds}
    return tuple(
        HomeRound(
            heading.number,
            rounds[heading.number].tee.course,
            rounds[heading.number].tee.name,
            heading.closes_at,
            time_left(heading.closes_at, now),
            len(view.round(heading.number).awards.card_holders),
            holds_card(viewer_id, rounds[heading.number], facts.teams),
            _home_team(rounds[heading.number], facts, viewer_id),
        )
        for heading in headings
    )
