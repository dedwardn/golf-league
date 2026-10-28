"""Alembic's environment: it runs on the connection migrate hands it, so no alembic.ini."""

from alembic import context

context.configure(connection=context.config.attributes["connection"])
with context.begin_transaction():
    context.run_migrations()
