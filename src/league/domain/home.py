"""One viewer's open rounds as home reads them (SPEC section 7), and the time left in a round.

It calls the modules that own the rules and holds no rule of its own. A team season plays every
card off the seed index (R15), so these are the strokes its rounds are scored with.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from league.domain.access import holds_card
from league.domain.configs import BestballFormat, CombinedFormat
from league.domain.facts import RoundFacts, RoundHeading, SeasonFacts
from league.domain.results import HomePlayer, HomeRound, HomeTeam, SeasonView
from league.domain.strokes import playing_handicap
from league.domain.teams import team_members, team_playing_handicap

_DAY = timedelta(days=1)
_HOUR = timedelta(hours=1)


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
    if isinstance(config, BestballFormat | CombinedFormat):
        players = tuple(
            HomePlayer(
                player_id,
                playing_handicap(seeds[player_id], round_.tee, config.allowance),
                holds_card(player_id, round_, facts.teams),
            )
            for player_id in (viewer_id, partner_id)
        )
        return HomeTeam(config.format, players, None)
    handicap = team_playing_handicap((seeds[viewer_id], seeds[partner_id]), round_.tee, config)
    return HomeTeam(config.format, (), handicap)


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
    holders = {
        round_view.awards.number: round_view.awards.card_holders for round_view in view.rounds
    }
    return tuple(
        HomeRound(
            heading.number,
            rounds[heading.number].tee.course,
            rounds[heading.number].tee.name,
            heading.closes_at,
            time_left(heading.closes_at, now),
            len(holders[heading.number]),
            holds_card(viewer_id, rounds[heading.number], facts.teams),
            _home_team(rounds[heading.number], facts, viewer_id),
        )
        for heading in headings
    )
