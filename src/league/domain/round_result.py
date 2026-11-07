"""One round's result for one viewer in a team season (SPEC section 7): the viewer's team and
its net, every team with a score ranked by its allplay record, and the team's round total and
place.

It calls access.py, teams.py, standings.py and rounding.py and holds no rule of its own: each
team's score and record are compute_season's, read here and never recomputed. The net is the
score on the stableford basis read as strokes (decision 6): each hole counts no worse than net
double bogey.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction

from league.domain.access import sees_round, takes_team_card
from league.domain.configs import FormatConfig
from league.domain.facts import Card, RoundFacts, SeasonFacts
from league.domain.results import Record, RoundAwards, SeasonView, StandingsRow, points_text
from league.domain.rounding import round_half_up
from league.domain.standings import round_total, standings
from league.domain.teams import capped_team_net, team_handicaps, team_members


@dataclass(frozen=True)
class ResultPlayer:
    """One player of the viewer's team in an own-ball round: their gross, None without a card,
    and their strokes."""

    player_id: str
    gross: int | None
    playing_handicap: int


@dataclass(frozen=True)
class ResultTeam:
    """The viewer's team in the round: its format, its net and whose strokes it plays off (R16).

    `net` is None for a team without a score (R17). An own-ball round has `players`, the viewer
    first, and a shared-ball round has the team card's gross, None without one, and the team's
    playing handicap instead.
    """

    team_id: str
    format: str
    net: int | None
    players: tuple[ResultPlayer, ...]
    team_gross: int | None
    team_playing_handicap: int | None


@dataclass(frozen=True)
class RankedTeam:
    """One team with a score: its net, the other teams with a score it beats, a level one
    counting half, and that share as its bar's width in whole percent."""

    team_id: str
    net: int
    beaten: Fraction
    bar_percent: int
    mine: bool


@dataclass(frozen=True)
class ResultAllplay:
    """Every team with a score ranked by its allplay record, level ones in team id order, none
    while fewer than two teams have a score, and the season teams without one, in team id order."""

    ranked: tuple[RankedTeam, ...]
    without_score: tuple[str, ...]

    @property
    def others(self) -> int:
        return len(self.ranked) - 1

    @property
    def beaten_text(self) -> str | None:
        """How many teams the viewer's team beats, as "3" or "1.5", or None without its score."""
        beaten = next((team.beaten for team in self.ranked if team.mine), None)
        if beaten is None:
            return None
        return str(beaten.numerator) if beaten.denominator == 1 else points_text(beaten)

    @property
    def without_score_text(self) -> str | None:
        """The fine line, as "blue and gold have no score this round."."""
        if not self.without_score:
            return None
        *rest, last = self.without_score
        teams = f"{', '.join(rest)} and {last}" if rest else last
        return f"{teams} have no score this round."


@dataclass(frozen=True)
class RoundResult:
    """The round result for one viewer.

    `team` and `points`, the team's round total (R10), are None for a viewer outside the season,
    and `points` for a team without one. `after` is the team's row of the season table with the
    round added, None while it is open, since no table holds an open round, and `before` the row
    without it, None too when no closed round comes before it.
    """

    number: int
    course: str
    tee_name: str
    team: ResultTeam | None
    allplay: ResultAllplay
    points: Fraction | None
    before: StandingsRow | None
    after: StandingsRow | None

    @property
    def points_text(self) -> str:
        return "\N{EN DASH}" if self.points is None else points_text(self.points)


def _gross(card: Card | None) -> int | None:
    return None if card is None else sum(card.scores)


def _team(
    round_: RoundFacts, config: FormatConfig, facts: SeasonFacts, viewer_id: str, net: int | None
) -> ResultTeam:
    """The viewer's team block, the viewer first, as on home."""
    team_id = facts.teams[viewer_id]
    a, b = team_members(facts.teams)[team_id]
    players = (viewer_id, b if a == viewer_id else a)
    seeds = facts.seed_index_tenths
    handicaps = team_handicaps((seeds[players[0]], seeds[players[1]]), round_.tee, config)
    if takes_team_card(round_):
        (handicap,) = handicaps
        gross = _gross(round_.team_cards.get(team_id))
        return ResultTeam(team_id, config.format, net, (), gross, handicap)
    rows = tuple(
        ResultPlayer(player_id, _gross(round_.cards.get(player_id)), handicap)
        for player_id, handicap in zip(players, handicaps, strict=True)
    )
    return ResultTeam(team_id, config.format, net, rows, None, None)


def _ranked(
    records: Sequence[Record], nets: Mapping[str, int], viewer_team: str | None
) -> tuple[RankedTeam, ...]:
    """The records best first, each with its team's net and its share of the others as a bar."""
    return tuple(
        RankedTeam(
            record.competitor_id,
            nets[record.competitor_id],
            record.beaten,
            round_half_up(100 * record.beaten / (len(records) - 1)),
            record.competitor_id == viewer_team,
        )
        for record in sorted(records, key=lambda record: (-record.beaten, record.competitor_id))
    )


def _row(
    rounds: list[RoundAwards], team_id: str, competitors: Sequence[str], facts: SeasonFacts
) -> StandingsRow | None:
    """The team's row of the season table over those closed rounds, or None without one."""
    if not rounds:
        return None
    rows = standings(rounds, competitors, facts.standings_rule)
    return next(row for row in rows if row.competitor_id == team_id)


def round_result(
    facts: SeasonFacts, view: SeasonView, number: int, viewer_id: str, now: datetime
) -> RoundResult | None:
    """The season's round of that number as the viewer reads its result.

    None in an individual season, whose screen is S21's, for a round not in the facts, and for a
    viewer R12 hides it from. `view` is compute_season's, unfiltered, whose scores already read
    R17's on-time rule.
    """
    round_ = next((round_ for round_ in facts.rounds if round_.number == number), None)
    if (
        facts.mode != "team"
        or round_ is None
        or not sees_round(viewer_id, round_, facts.teams, now)
    ):
        return None
    # SeasonFacts refuses a round of a team season without a format (R15).
    config = round_.format
    assert config is not None
    tee = round_.tee
    round_view = view.round(number)
    nets = {
        entry.competitor_id: capped_team_net(entry.net, config, tee) for entry in round_view.scores
    }
    competitors = tuple(row.competitor_id for row in view.standings)
    team_id = facts.teams.get(viewer_id)
    allplay = ResultAllplay(
        _ranked(round_view.records, nets, team_id),
        tuple(sorted(set(competitors) - set(round_view.awards.card_holders))),
    )
    if team_id is None:
        return RoundResult(number, tee.course, tee.name, None, allplay, None, None, None)
    closed = [
        closed_view.awards
        for closed_view, closed_round in zip(view.rounds, facts.rounds, strict=True)
        if closed_round.closed_at is not None and closed_round.number < number
    ]
    is_open = round_.closed_at is None
    return RoundResult(
        number,
        tee.course,
        tee.name,
        _team(round_, config, facts, viewer_id, nets.get(team_id)),
        allplay,
        round_total(team_id, round_view.awards),
        None if is_open else _row(closed, team_id, competitors, facts),
        None if is_open else _row([*closed, round_view.awards], team_id, competitors, facts),
    )
