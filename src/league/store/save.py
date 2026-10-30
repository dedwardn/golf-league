"""One fact written, or replaced in place, on the connection its service hands it. The service
commits, not the store.

Every JSON column goes through the adapter load reads it with, so a fact saved is the fact
loaded. A key or CHECK the fact breaks raises the database's IntegrityError as it is.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Connection, Update, insert, update

from league.domain.facts import Card, IndexRule, ManualAward, RoundFacts, StandingsRule, Tee
from league.store.schema import (
    CONTESTS_JSON,
    FORMAT_JSON,
    HOLES_JSON,
    INDEX_RULE_JSON,
    PAIRINGS_JSON,
    STANDINGS_RULE_JSON,
    cards,
    manual_awards,
    players,
    rounds,
    season_players,
    seasons,
    tees,
)


def save_player(connection: Connection, player_id: str, link_token: str) -> None:
    connection.execute(insert(players).values(player_id=player_id, link_token=link_token))


def update_link_token(connection: Connection, player_id: str, link_token: str) -> bool:
    """Whether the player had a row to update."""
    query = update(players).where(players.c.player_id == player_id)
    return connection.execute(query.values(link_token=link_token)).rowcount == 1


def _tee_values(tee: Tee) -> dict[str, Any]:
    return {
        "pars": HOLES_JSON.dump_json(tee.pars).decode(),
        "stroke_indexes": HOLES_JSON.dump_json(tee.stroke_indexes).decode(),
        "course_rating_tenths": tee.course_rating_tenths,
        "slope": tee.slope,
    }


def save_tee(connection: Connection, tee_id: str, tee: Tee) -> None:
    connection.execute(insert(tees).values(tee_id=tee_id, **_tee_values(tee)))


def update_tee(connection: Connection, tee_id: str, tee: Tee) -> None:
    connection.execute(update(tees).where(tees.c.tee_id == tee_id).values(**_tee_values(tee)))


def save_season(
    connection: Connection,
    season_id: str,
    mode: str,
    index_rule: IndexRule,
    standings_rule: StandingsRule,
) -> None:
    connection.execute(
        insert(seasons).values(
            season_id=season_id,
            mode=mode,
            index_rule=INDEX_RULE_JSON.dump_json(index_rule).decode(),
            standings_rule=STANDINGS_RULE_JSON.dump_json(standings_rule).decode(),
        )
    )


def save_seeded_player(
    connection: Connection,
    season_id: str,
    player_id: str,
    seed_index_tenths: int,
    provisional: bool,
) -> None:
    """The player's seed index and provisional flag for the season, in no season team yet."""
    connection.execute(
        insert(season_players).values(
            season_id=season_id,
            player_id=player_id,
            seed_index_tenths=seed_index_tenths,
            provisional=provisional,
        )
    )


def update_seed_index(
    connection: Connection, season_id: str, player_id: str, seed_index_tenths: int
) -> bool:
    """Whether the player was seeded in the season, and so had a row to update."""
    result = connection.execute(
        update(season_players)
        .where(season_players.c.season_id == season_id, season_players.c.player_id == player_id)
        .values(seed_index_tenths=seed_index_tenths)
    )
    return result.rowcount == 1


def save_season_team(
    connection: Connection, season_id: str, team_id: str, player_ids: tuple[str, ...]
) -> None:
    """The team written onto its players' seeded rows, so they are seeded first.

    R15's two players to a team is checked on load, by SeasonFacts.
    """
    connection.execute(
        update(season_players)
        .where(
            season_players.c.season_id == season_id,
            season_players.c.player_id.in_(player_ids),
        )
        .values(team_id=team_id)
    )


def _config_values(round_: RoundFacts, tee_id: str) -> dict[str, Any]:
    """What the admin sets up on a round and may change while it is a draft (R14)."""
    return {
        "tee_id": tee_id,
        "contests": CONTESTS_JSON.dump_json(round_.contests).decode(),
        "format": None if round_.format is None else FORMAT_JSON.dump_json(round_.format).decode(),
        "late_until": round_.late_until,
    }


def save_round(
    connection: Connection, season_id: str, round_: RoundFacts, tee_id: str, state: str
) -> None:
    """The round's own fields, on the tee tee_id names. round_.tee is not read.

    Its cards, team cards and manual awards are facts of their own, each with its own save.
    """
    connection.execute(
        insert(rounds).values(
            season_id=season_id,
            number=round_.number,
            state=state,
            pairings=PAIRINGS_JSON.dump_json(round_.pairings).decode(),
            closed_at=round_.closed_at,
            **_config_values(round_, tee_id),
        )
    )


def _round(season_id: str, number: int) -> Update:
    return update(rounds).where(rounds.c.season_id == season_id, rounds.c.number == number)


def update_round(connection: Connection, season_id: str, round_: RoundFacts, tee_id: str) -> None:
    """The round's tee, contests, format and late_until replaced in place.

    Its state, closed_at and pairings are left as they are: pairings are published on their own.
    """
    connection.execute(_round(season_id, round_.number).values(**_config_values(round_, tee_id)))


def update_round_state(
    connection: Connection, season_id: str, number: int, state: str, closed_at: datetime | None
) -> None:
    """The round's state and closed_at, which the database keeps in step (R13)."""
    connection.execute(_round(season_id, number).values(state=state, closed_at=closed_at))


def save_window(
    connection: Connection, season_id: str, number: int, opens_at: datetime, closes_at: datetime
) -> None:
    """The round's window written onto its row. It is informational, so RoundFacts has none."""
    connection.execute(_round(season_id, number).values(opens_at=opens_at, closes_at=closes_at))


def _card_row(season_id: str, round_number: int, card: Card) -> dict[str, Any]:
    """A counted card's row without its holder, a player or a team."""
    return {
        "season_id": season_id,
        "card_id": card.card_id,
        "round_number": round_number,
        "submitted_at": card.submitted_at,
        "scores": HOLES_JSON.dump_json(card.scores).decode(),
        "voided": False,
    }


def save_card(
    connection: Connection, season_id: str, round_number: int, player_id: str, card: Card
) -> None:
    row = _card_row(season_id, round_number, card)
    connection.execute(insert(cards).values(**row, player_id=player_id))


def save_team_card(
    connection: Connection, season_id: str, round_number: int, team_id: str, card: Card
) -> None:
    row = _card_row(season_id, round_number, card)
    connection.execute(insert(cards).values(**row, team_id=team_id))


def _card(season_id: str, card_id: str) -> Update:
    return update(cards).where(cards.c.season_id == season_id, cards.c.card_id == card_id)


def update_card_scores(connection: Connection, season_id: str, card: Card) -> None:
    """The card's hole scores replaced in place. Its submitted_at and its holder are left as they
    are, so a correction moves no card in R6's order and gives no round a new kind of card.
    """
    scores = HOLES_JSON.dump_json(card.scores).decode()
    connection.execute(_card(season_id, card.card_id).values(scores=scores))


def update_card_voided(connection: Connection, season_id: str, card_id: str) -> None:
    """The card's row stays, no longer counted, which leaves its holder free to hand in another."""
    connection.execute(_card(season_id, card_id).values(voided=True))


def save_manual_award(
    connection: Connection, season_id: str, round_number: int, award: ManualAward
) -> None:
    """Appended after the round's earlier awards, in the order the admin gives them."""
    connection.execute(
        insert(manual_awards).values(
            season_id=season_id,
            round_number=round_number,
            competitor_id=award.competitor_id,
            key=award.key,
            points=str(award.points),
        )
    )
