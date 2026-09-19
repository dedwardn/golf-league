#!/usr/bin/env bash
# The single quality gate. A step is not done until this passes.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run lint-imports
uv run vulture
uv run python scripts/check_structure.py
uv run pytest
