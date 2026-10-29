"""S11: the tables for the facts.

Spelled out rather than built from the tables, so this migration keeps building what it built
when the tables change. Until S18 there is no database to migrate, so S13 and S14 extend it.
"""

import sqlalchemy as sa
from alembic import op

revision = "s11"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("player_id", sa.String, primary_key=True),
        sa.Column("link_token", sa.String, nullable=False, unique=True),
    )
    op.create_table(
        "tees",
        sa.Column("tee_id", sa.String, primary_key=True),
        sa.Column("pars", sa.Text, nullable=False),
        sa.Column("stroke_indexes", sa.Text, nullable=False),
        sa.Column("course_rating_tenths", sa.Integer, nullable=False),
        sa.Column("slope", sa.Integer, nullable=False),
    )
    op.create_table(
        "seasons",
        sa.Column("season_id", sa.String, primary_key=True),
        sa.Column("mode", sa.String, nullable=False),
        sa.Column("index_rule", sa.Text, nullable=False),
        sa.Column("standings_rule", sa.Text, nullable=False),
    )
    op.create_table(
        "season_players",
        sa.Column("season_id", sa.String, sa.ForeignKey("seasons.season_id"), primary_key=True),
        sa.Column("player_id", sa.String, sa.ForeignKey("players.player_id"), primary_key=True),
        sa.Column("seed_index_tenths", sa.Integer, nullable=False),
        sa.Column("provisional", sa.Boolean, nullable=False),
        sa.Column("team_id", sa.String),
    )
    op.create_table(
        "rounds",
        sa.Column("season_id", sa.String, sa.ForeignKey("seasons.season_id"), primary_key=True),
        sa.Column("number", sa.Integer, primary_key=True),
        sa.Column("tee_id", sa.String, sa.ForeignKey("tees.tee_id"), nullable=False),
        sa.Column("state", sa.String, nullable=False),
        sa.Column("contests", sa.Text, nullable=False),
        sa.Column("pairings", sa.Text, nullable=False),
        sa.Column("format", sa.Text),
        sa.Column("closed_at", sa.DateTime),
        sa.Column("late_until", sa.DateTime),
        sa.Column("opens_at", sa.DateTime),
        sa.Column("closes_at", sa.DateTime),
        sa.CheckConstraint("state IN ('draft', 'open', 'closed')", name="round_state"),
    )
    op.create_table(
        "cards",
        sa.Column("season_id", sa.String, primary_key=True),
        sa.Column("card_id", sa.String, primary_key=True),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("player_id", sa.String),
        sa.Column("team_id", sa.String),
        sa.Column("submitted_at", sa.DateTime, nullable=False),
        sa.Column("scores", sa.Text, nullable=False),
        sa.Column("voided", sa.Boolean, nullable=False),
        sa.ForeignKeyConstraint(
            ["season_id", "round_number"], ["rounds.season_id", "rounds.number"]
        ),
        sa.ForeignKeyConstraint(
            ["season_id", "player_id"], ["season_players.season_id", "season_players.player_id"]
        ),
        sa.CheckConstraint("(player_id IS NULL) <> (team_id IS NULL)", name="card_player_or_team"),
    )
    for holder in ("player", "team"):
        op.create_index(
            f"one_counted_card_per_{holder}",
            "cards",
            ["season_id", "round_number", f"{holder}_id"],
            unique=True,
            sqlite_where=sa.text("NOT voided"),
        )
    op.create_table(
        "manual_awards",
        sa.Column("manual_award_id", sa.Integer, primary_key=True),
        sa.Column("season_id", sa.String, nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("competitor_id", sa.String, nullable=False),
        sa.Column("key", sa.String, nullable=False),
        sa.Column("points", sa.String, nullable=False),
        sa.ForeignKeyConstraint(
            ["season_id", "round_number"], ["rounds.season_id", "rounds.number"]
        ),
    )
