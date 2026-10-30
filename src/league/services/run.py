"""What the admin does to run a round: open it, close it, and undo a close (R13, R14).

`now` is passed in, in naive UTC, so a test sets the time a round closes.
"""

from datetime import datetime

from sqlalchemy import Engine

from league.domain.access import may_reopen, pairings_published
from league.store.load import load_round
from league.store.save import update_round_state


def open_round(engine: Engine, season_id: str, number: int) -> None:
    """Open a draft round, or raise ValueError (R13, R14).

    A round with a duel contest opens only once that contest's pairings are published. Its config
    is locked from now on.
    """
    with engine.begin() as connection:
        draft = load_round(connection, season_id, number, "draft")
        if draft is None:
            raise ValueError(f"round {number} of season {season_id} is not a draft")
        if not pairings_published(draft):
            raise ValueError(f"round {number} of season {season_id} has unpublished pairings")
        update_round_state(connection, season_id, number, "open", None)


def close_round(engine: Engine, season_id: str, number: int, now: datetime) -> None:
    """Close an open round, recording now as its closed_at, or raise ValueError (R13)."""
    with engine.begin() as connection:
        if load_round(connection, season_id, number, "open") is None:
            raise ValueError(f"round {number} of season {season_id} is not open")
        update_round_state(connection, season_id, number, "closed", now)


def reopen_round(engine: Engine, season_id: str, number: int) -> None:
    """Undo a close, clearing closed_at, or raise ValueError (R13).

    Only a closed round with no late card or team card reopens, so no card changes standing.
    It is open again, not draft, so its config stays locked (R14).
    """
    with engine.begin() as connection:
        round_ = load_round(connection, season_id, number, "closed")
        if round_ is None or not may_reopen(round_):
            raise ValueError(f"round {number} of season {season_id} does not reopen")
        update_round_state(connection, season_id, number, "open", None)
