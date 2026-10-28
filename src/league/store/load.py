"""One season's rows turned into SeasonFacts, with every JSON column checked on the way in.

Pydantic validates the JSON straight into the domain dataclasses, whose own checks then run, so
loading adds no bound of its own.
"""

from collections import defaultdict
from fractions import Fraction
from typing import Annotated

from pydantic import Field, TypeAdapter
from sqlalchemy import Connection, select

from league.domain.configs import ContestConfig, FormatConfig
from league.domain.facts import (
    Card,
    IndexRule,
    ManualAward,
    Pairing,
    RoundFacts,
    SeasonFacts,
    StandingsRule,
    Tee,
)
from league.store.schema import cards, manual_awards, rounds, season_players, seasons, tees

# Each union is read by its tag, so a config that lost its tag is refused rather than taken for
# the first member it happens to fit.
_CONTESTS: TypeAdapter[tuple[ContestConfig, ...]] = TypeAdapter(
    tuple[Annotated[ContestConfig, Field(discriminator="kind")], ...]
)
_FORMAT: TypeAdapter[FormatConfig] = TypeAdapter(
    Annotated[FormatConfig, Field(discriminator="format")]
)
_INDEX_RULE = TypeAdapter(IndexRule)
_STANDINGS_RULE = TypeAdapter(StandingsRule)
_PAIRINGS = TypeAdapter(dict[str, tuple[Pairing, ...]])
_HOLES = TypeAdapter(tuple[int, ...])

_CardsByRound = dict[int, dict[str, Card]]


def _counted_cards(connection: Connection, season_id: str) -> tuple[_CardsByRound, _CardsByRound]:
    """Each round's counted cards by player, and its counted team cards by team."""
    by_player: defaultdict[int, dict[str, Card]] = defaultdict(dict)
    by_team: defaultdict[int, dict[str, Card]] = defaultdict(dict)
    rows = connection.execute(
        select(cards).where(cards.c.season_id == season_id, cards.c.voided.is_(False))
    )
    for row in rows:
        card = Card(row.card_id, row.submitted_at, _HOLES.validate_json(row.scores))
        if row.player_id is None:
            by_team[row.round_number][row.team_id] = card
        else:
            by_player[row.round_number][row.player_id] = card
    return by_player, by_team


def _manual_awards(connection: Connection, season_id: str) -> dict[int, tuple[ManualAward, ...]]:
    by_round: defaultdict[int, list[ManualAward]] = defaultdict(list)
    rows = connection.execute(
        select(manual_awards)
        .where(manual_awards.c.season_id == season_id)
        .order_by(manual_awards.c.manual_award_id)
    )
    for row in rows:
        award = ManualAward(row.competitor_id, row.key, Fraction(row.points))
        by_round[row.round_number].append(award)
    return {number: tuple(awards) for number, awards in by_round.items()}


def _rounds(connection: Connection, season_id: str) -> tuple[RoundFacts, ...]:
    """The season's open and closed rounds in number order. A draft round has no cards."""
    by_player, by_team = _counted_cards(connection, season_id)
    manual = _manual_awards(connection, season_id)
    rows = connection.execute(
        select(
            rounds, tees.c.pars, tees.c.stroke_indexes, tees.c.course_rating_tenths, tees.c.slope
        )
        .join(tees, rounds.c.tee_id == tees.c.tee_id)
        .where(rounds.c.season_id == season_id, rounds.c.state != "draft")
        .order_by(rounds.c.number)
    )
    return tuple(
        RoundFacts(
            number=row.number,
            tee=Tee(
                _HOLES.validate_json(row.pars),
                _HOLES.validate_json(row.stroke_indexes),
                row.course_rating_tenths,
                row.slope,
            ),
            contests=_CONTESTS.validate_json(row.contests),
            cards=by_player.get(row.number, {}),
            pairings=_PAIRINGS.validate_json(row.pairings),
            manual=manual.get(row.number, ()),
            closed_at=row.closed_at,
            format=None if row.format is None else _FORMAT.validate_json(row.format),
            team_cards=by_team.get(row.number, {}),
            late_until=row.late_until,
        )
        for row in rows
    )


def load_season_facts(connection: Connection, season_id: str) -> SeasonFacts:
    """The season as compute_season reads it: open and closed rounds, counted cards only."""
    season = connection.execute(select(seasons).where(seasons.c.season_id == season_id)).one()
    players = connection.execute(
        select(season_players).where(season_players.c.season_id == season_id)
    ).all()
    return SeasonFacts(
        rounds=_rounds(connection, season_id),
        seed_index_tenths={row.player_id: row.seed_index_tenths for row in players},
        provisional=frozenset(row.player_id for row in players if row.provisional),
        index_rule=_INDEX_RULE.validate_json(season.index_rule),
        standings_rule=_STANDINGS_RULE.validate_json(season.standings_rule),
        teams={row.player_id: row.team_id for row in players if row.team_id is not None},
        mode=season.mode,
    )
