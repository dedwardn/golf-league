"""What the admin sets up before play: players, tees, a season, and its rounds as drafts.

A new fact arrives as the domain dataclass it becomes, or is built into one before anything is
saved, so the domain's checks refuse it with ValueError and nothing is stored.
"""

import secrets
from dataclasses import dataclass, replace
from datetime import datetime

from sqlalchemy import Engine

from league.domain.access import seed_index_locked, tee_locked
from league.domain.configs import ContestConfig, FormatConfig
from league.domain.facts import RoundFacts, SeasonFacts, Tee
from league.store.load import load_rounds_on_tee, load_season_facts, load_tee
from league.store.save import (
    save_player,
    save_round,
    save_season,
    save_season_team,
    save_seeded_player,
    save_tee,
    save_window,
    update_link_token,
    update_seed_index,
    update_tee,
)


def _new_link_token() -> str:
    return secrets.token_urlsafe(16)


def create_player(engine: Engine, player_id: str) -> str:
    """Store the player with a fresh link token, and return the token for the admin to send.

    The id is the name the admin types, and the name the screens show.
    """
    link_token = _new_link_token()
    with engine.begin() as connection:
        save_player(connection, player_id, link_token)
    return link_token


def replace_link_token(engine: Engine, player_id: str) -> str:
    """Give the player a fresh link token and return it. The old one finds nobody from now on.

    ValueError for a player who does not exist, rather than a token that finds nobody.
    """
    link_token = _new_link_token()
    with engine.begin() as connection:
        if not update_link_token(connection, player_id, link_token):
            raise ValueError(f"no player {player_id}")
    return link_token


def create_tee(engine: Engine, tee_id: str, tee: Tee) -> None:
    with engine.begin() as connection:
        save_tee(connection, tee_id, tee)


def change_tee(engine: Engine, tee_id: str, tee: Tee) -> None:
    """Replace the tee, or raise ValueError once a card or team card is on it (R14).

    Old rounds keep the numbers they were scored with, so a tee that is wrong by then is a new tee.
    """
    with engine.begin() as connection:
        if tee_locked(load_rounds_on_tee(connection, tee_id)):
            raise ValueError(f"tee {tee_id} has a card on it")
        update_tee(connection, tee_id, tee)


def create_season(engine: Engine, season_id: str, facts: SeasonFacts) -> None:
    """Store the season's mode, rules, seeded players and season teams in one transaction.

    `facts.rounds` is not read: each round is created on its own, with create_round. SeasonFacts
    checks R15's teams on construction, but not that a team's players are seeded, and a team is
    written onto its players' seeded rows, so an unseeded one would be dropped without a word.
    """
    unseeded = sorted(set(facts.teams) - set(facts.seed_index_tenths))
    if unseeded:
        raise ValueError(f"season team players {', '.join(unseeded)} have no seed index")
    with engine.begin() as connection:
        save_season(connection, season_id, facts.mode, facts.index_rule, facts.standings_rule)
        for player_id, seed_index_tenths in facts.seed_index_tenths.items():
            provisional = player_id in facts.provisional
            save_seeded_player(connection, season_id, player_id, seed_index_tenths, provisional)
        for team_id in set(facts.teams.values()):
            members = tuple(player for player, team in facts.teams.items() if team == team_id)
            save_season_team(connection, season_id, team_id, members)


def correct_seed_index(
    engine: Engine, season_id: str, player_id: str, seed_index_tenths: int
) -> None:
    """Replace the player's seed index, or raise ValueError once R15 locks it.

    ValueError too for a player not seeded in the season: a correction that quietly changed
    nothing would leave a wrong seed under every card of the season.
    """
    with engine.begin() as connection:
        if seed_index_locked(load_season_facts(connection, season_id)):
            raise ValueError(f"the seed indexes of season {season_id} are locked")
        if not update_seed_index(connection, season_id, player_id, seed_index_tenths):
            raise ValueError(f"player {player_id} has no seed index in season {season_id}")


@dataclass(frozen=True)
class RoundSetup:
    """A new round as the admin sets it up, on the tee tee_id names.

    The window is informational: what counts is the round's state and closed_at. `format` is
    a team season's (R17) and `late_until` an individual season's (SPEC decision 4).
    """

    season_id: str
    number: int
    tee_id: str
    opens_at: datetime
    closes_at: datetime
    contests: tuple[ContestConfig, ...]
    format: FormatConfig | None = None
    late_until: datetime | None = None


def _check_mode(setup: RoundSetup, mode: str) -> None:
    """A round holds only what R15 reads in its season's mode."""
    # SPEC decision 4: a team season has no late window, since a missed round is the one dropped.
    if mode == "team" and setup.late_until is not None:
        raise ValueError("a team season's round takes no late cards")
    # SPEC's glossary gives a format to a team season only, and D16 rules out team cards
    # in an individual season, which takes_team_card would otherwise read from a format.
    if mode == "individual" and setup.format is not None:
        raise ValueError("an individual season's round has no format")


def create_round(engine: Engine, setup: RoundSetup) -> None:
    """Store the round as a draft with its window, or raise ValueError when it does not fit.

    It has no pairings until they are published (S21). The round is checked inside its season,
    as it will be once it opens, so SeasonFacts refuses a team round without a format or with a
    contest other than field or allplay, a number an open or closed round has, and a reference
    round that is not an open or closed round on its tee. A number a draft round has is refused
    by the database's key.
    """
    with engine.begin() as connection:
        facts = load_season_facts(connection, setup.season_id)
        _check_mode(setup, facts.mode)
        round_ = RoundFacts(
            number=setup.number,
            tee=load_tee(connection, setup.tee_id),
            contests=setup.contests,
            cards={},
            pairings={},
            manual=(),
            closed_at=None,
            format=setup.format,
            late_until=setup.late_until,
        )
        # Built for its checks only, which refuse a round that does not fit its season.
        replace(facts, rounds=(*facts.rounds, round_))
        save_round(connection, setup.season_id, round_, setup.tee_id, "draft")
        save_window(connection, setup.season_id, setup.number, setup.opens_at, setup.closes_at)
