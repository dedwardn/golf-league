"""The tables that hold the facts (SPEC section 4), and migrate, which builds them.

Configs, 18-hole tuples and pairings are JSON text, always read whole and checked on load by
the domain dataclass they become. Each JSON column has one pydantic adapter, which writes it and
reads it back. R13's uniqueness rules are keys and indexes, not code.
"""

from collections.abc import Mapping
from typing import Annotated

from alembic import command
from alembic.config import Config
from pydantic import Field, TypeAdapter
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
)

from league.domain.configs import ContestConfig, FormatConfig
from league.domain.facts import IndexRule, Pairing, StandingsRule

# Each union is read by its tag, so a config that lost its tag is refused rather than taken for
# the first member it happens to fit.
CONTESTS_JSON: TypeAdapter[tuple[ContestConfig, ...]] = TypeAdapter(
    tuple[Annotated[ContestConfig, Field(discriminator="kind")], ...]
)
FORMAT_JSON: TypeAdapter[FormatConfig] = TypeAdapter(
    Annotated[FormatConfig, Field(discriminator="format")]
)
INDEX_RULE_JSON = TypeAdapter(IndexRule)
STANDINGS_RULE_JSON = TypeAdapter(StandingsRule)
PAIRINGS_JSON = TypeAdapter(Mapping[str, tuple[Pairing, ...]])
HOLES_JSON = TypeAdapter(tuple[int, ...])

metadata = MetaData()

players = Table(
    "players",
    metadata,
    Column("player_id", String, primary_key=True),
    Column("link_token", String, nullable=False, unique=True),
)

tees = Table(
    "tees",
    metadata,
    Column("tee_id", String, primary_key=True),
    Column("pars", Text, nullable=False),
    Column("stroke_indexes", Text, nullable=False),
    Column("course_rating_tenths", Integer, nullable=False),
    Column("slope", Integer, nullable=False),
)

seasons = Table(
    "seasons",
    metadata,
    Column("season_id", String, primary_key=True),
    Column("mode", String, nullable=False),
    Column("index_rule", Text, nullable=False),
    Column("standings_rule", Text, nullable=False),
)

# A season team rides on the seeded player, since R13 takes cards from seeded players only.
season_players = Table(
    "season_players",
    metadata,
    Column("season_id", String, ForeignKey("seasons.season_id"), primary_key=True),
    Column("player_id", String, ForeignKey("players.player_id"), primary_key=True),
    Column("seed_index_tenths", Integer, nullable=False),
    Column("provisional", Boolean, nullable=False),
    Column("team_id", String),
)

rounds = Table(
    "rounds",
    metadata,
    Column("season_id", String, ForeignKey("seasons.season_id"), primary_key=True),
    Column("number", Integer, primary_key=True),
    Column("tee_id", String, ForeignKey("tees.tee_id"), nullable=False),
    Column("state", String, nullable=False),
    Column("contests", Text, nullable=False),
    Column("pairings", Text, nullable=False),
    Column("format", Text),
    Column("closed_at", DateTime),
    Column("late_until", DateTime),
    # The window is informational (SPEC glossary), so the domain never reads it.
    Column("opens_at", DateTime),
    Column("closes_at", DateTime),
    CheckConstraint("state IN ('draft', 'open', 'closed')", name="round_state"),
    CheckConstraint("(state = 'closed') = (closed_at IS NOT NULL)", name="round_closed_at"),
)

# A card is a player's or, in a shared-ball round, a team's: one table, since the domain has one
# Card. The partial indexes allow one counted card per player or team per round (R13, R15).
cards = Table(
    "cards",
    metadata,
    Column("season_id", String, primary_key=True),
    Column("card_id", String, primary_key=True),
    Column("round_number", Integer, nullable=False),
    Column("player_id", String),
    Column("team_id", String),
    Column("submitted_at", DateTime, nullable=False),
    Column("scores", Text, nullable=False),
    Column("voided", Boolean, nullable=False),
    ForeignKeyConstraint(["season_id", "round_number"], ["rounds.season_id", "rounds.number"]),
    ForeignKeyConstraint(
        ["season_id", "player_id"], ["season_players.season_id", "season_players.player_id"]
    ),
    CheckConstraint("(player_id IS NULL) <> (team_id IS NULL)", name="card_player_or_team"),
    Index(
        "one_counted_card_per_player",
        "season_id",
        "round_number",
        "player_id",
        unique=True,
        sqlite_where=text("NOT voided"),
    ),
    Index(
        "one_counted_card_per_team",
        "season_id",
        "round_number",
        "team_id",
        unique=True,
        sqlite_where=text("NOT voided"),
    ),
)

# The id keeps the order the admin gave the awards in. Points are str(Fraction), exact (D14).
manual_awards = Table(
    "manual_awards",
    metadata,
    Column("manual_award_id", Integer, primary_key=True),
    Column("season_id", String, nullable=False),
    Column("round_number", Integer, nullable=False),
    Column("competitor_id", String, nullable=False),
    Column("key", String, nullable=False),
    Column("points", String, nullable=False),
    ForeignKeyConstraint(["season_id", "round_number"], ["rounds.season_id", "rounds.number"]),
)


def migrate(connection: Connection) -> None:
    """Bring the database on that connection to the latest migration."""
    config = Config()
    config.set_main_option("script_location", "league.store:migrations")
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
