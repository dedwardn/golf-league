"""Temporary databases for the store and services tests, built only from the save functions."""

from pathlib import Path

from sqlalchemy import Connection, Engine

from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.facts import RoundFacts, SeasonFacts
from league.services.runtime import open_database
from league.store.load import load_season_facts
from league.store.save import (
    save_card,
    save_manual_award,
    save_player,
    save_round,
    save_season,
    save_season_team,
    save_seeded_player,
    save_team_card,
    save_tee,
)


def a_database(tmp_path: Path) -> Engine:
    """A migrated SQLite file that enforces its foreign keys, as the app opens it."""
    return open_database(tmp_path / "league.db")


def save_whole_round(
    connection: Connection, season_id: str, round_: RoundFacts, state: str | None = None
) -> None:
    """The round on a tee of its own, with its cards, team cards and manual awards."""
    tee_id = f"{season_id}-r{round_.number}"
    save_tee(connection, tee_id, round_.tee)
    if state is None:
        state = "open" if round_.closed_at is None else "closed"
    save_round(connection, season_id, round_, tee_id, state)
    for player_id, card in round_.cards.items():
        save_card(connection, season_id, round_.number, player_id, card)
    for team_id, card in round_.team_cards.items():
        save_team_card(connection, season_id, round_.number, team_id, card)
    for award in round_.manual:
        save_manual_award(connection, season_id, round_.number, award)


def save_whole_season(connection: Connection, season_id: str, facts: SeasonFacts) -> None:
    """Every fact of the season but its players, whom several seasons share."""
    save_season(connection, season_id, facts.mode, facts.index_rule, facts.standings_rule)
    for player_id, seed in facts.seed_index_tenths.items():
        provisional = player_id in facts.provisional
        save_seeded_player(connection, season_id, player_id, seed, provisional)
    for team_id in set(facts.teams.values()):
        members = tuple(player for player, team in facts.teams.items() if team == team_id)
        save_season_team(connection, season_id, team_id, members)
    for round_ in facts.rounds:
        save_whole_round(connection, season_id, round_)


def golden_database(tmp_path: Path) -> Engine:
    """Both golden seasons in one database, so each load also shows it reads only its own."""
    engine = a_database(tmp_path)
    with engine.begin() as connection:
        for player_id in {*S9B.seed_index_tenths, *T3.seed_index_tenths}:
            save_player(connection, player_id, f"{player_id}-link")
        save_whole_season(connection, "s9b", S9B)
        save_whole_season(connection, "t3", T3)
    return engine


def load(engine: Engine, season_id: str) -> SeasonFacts:
    with engine.connect() as connection:
        return load_season_facts(connection, season_id)
