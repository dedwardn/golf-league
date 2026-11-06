"""What a player does: find themself by link token, hand in a card, see the season (R12, R13, R15).

`now` is passed in, in naive UTC, so a test sets the time a card arrives and a round is seen.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Engine

from league.domain.access import accepts_card, competitor_of, sees_round, takes_team_card
from league.domain.bay import BayRound, bay_round
from league.domain.entry import CardEntry, card_entry
from league.domain.facts import Card
from league.domain.home import HomeView, home_rounds
from league.domain.results import SeasonView
from league.domain.season import compute_season
from league.store.load import load_player_id, load_round_headings, load_season_facts
from league.store.save import save_card, save_team_card


def player_for_link_token(engine: Engine, link_token: str) -> str | None:
    """The player whose link token this is, or None for a token nobody holds."""
    with engine.connect() as connection:
        return load_player_id(connection, link_token)


@dataclass(frozen=True)
class Submission:
    """The 18 gross scores a player hands in for one round of a season.

    Before they are handed in they are what the player has typed so far, none before the first
    check of the card, and a score is None where the hole was left empty or holds no whole number.
    """

    season_id: str
    round_number: int
    player_id: str
    scores: tuple[int | None, ...]


def submit_card(engine: Engine, submission: Submission, now: datetime) -> None:
    """Store the card the player hands in now, or raise ValueError when the round refuses it.

    The card is the player's own, or in a shared-ball round their team's team card (R15), and is
    stored only when access.py accepts it (R13). A draft round is not in the season's facts, so
    it refuses the card as a round that does not exist does. The id only has to be unique in
    the season and fixed once stored (R6, R13). A hole with no score leaves the card short, so
    Card refuses it rather than store a score nobody typed.
    """
    scores = tuple(score for score in submission.scores if score is not None)
    card = Card(uuid4().hex, now, scores)
    with engine.begin() as connection:
        facts = load_season_facts(connection, submission.season_id)
        round_ = next(
            (round_ for round_ in facts.rounds if round_.number == submission.round_number), None
        )
        if round_ is None or not accepts_card(submission.player_id, round_, facts, now):
            raise ValueError(f"round {submission.round_number} does not take this card")
        if takes_team_card(round_):
            team_id = facts.teams[submission.player_id]
            save_team_card(connection, submission.season_id, round_.number, team_id, card)
        else:
            save_card(connection, submission.season_id, round_.number, submission.player_id, card)


def season_view(engine: Engine, season_id: str, viewer_id: str, now: datetime) -> SeasonView:
    """The season as the player sees it: only the rounds R12 shows them, and whose row is theirs.

    Standings and segments are the same for every viewer (R12).
    """
    with engine.connect() as connection:
        facts = load_season_facts(connection, season_id)
    view = compute_season(facts)
    rounds = tuple(
        round_view
        for round_view, round_ in zip(view.rounds, facts.rounds, strict=True)
        if sees_round(viewer_id, round_, facts.teams, now)
    )
    return replace(view, rounds=rounds, viewer_competitor=competitor_of(viewer_id, facts))


def home_view(engine: Engine, season_id: str, viewer_id: str, now: datetime) -> HomeView:
    """A player's home: their open rounds, and their row of the table every viewer reads.

    No round's result is on it, so nothing here asks R12: who has a card is for everyone to see.
    """
    with engine.connect() as connection:
        facts = load_season_facts(connection, season_id)
        headings = load_round_headings(connection, season_id)
    view = compute_season(facts)
    competitor = competitor_of(viewer_id, facts)
    return HomeView(
        home_rounds(facts, view, headings, viewer_id, now),
        next((row for row in view.standings if row.competitor_id == competitor), None),
        len(view.standings),
        facts.mode == "team",
    )


def bay_view(engine: Engine, season_id: str, number: int) -> BayRound | None:
    """How to set up the bay for the season's open round of that number, or None.

    It takes no viewer: the screen holds no result and nothing of the viewer's, so R12 has
    nothing to hide. A draft round is not in the season's facts, so it has no bay.
    """
    with engine.connect() as connection:
        return bay_round(load_season_facts(connection, season_id), number)


def card_entry_view(engine: Engine, submission: Submission, now: datetime) -> CardEntry | None:
    """Check the card for the player's round with the scores they typed, or None.

    None when the round does not take their card now (R13, R15). A draft round is not in the
    season's facts, so it has no entry.
    """
    with engine.connect() as connection:
        facts = load_season_facts(connection, submission.season_id)
    return card_entry(facts, submission.round_number, submission.player_id, now, submission.scores)


def admin_season_view(engine: Engine, season_id: str) -> SeasonView:
    """The season with every round, since the admin always sees (R12)."""
    with engine.connect() as connection:
        return compute_season(load_season_facts(connection, season_id))
