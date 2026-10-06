# League

An async season engine for a private golf league played on simulators. Small on purpose. The owner values a tight, readable codebase above speed and above features.

## Read before you act

- `docs/ARCHITECTURE.md`: where code goes. It is the authority. If something does not fit, stop and ask.
- `docs/SPEC.md`: what the system does, as numbered rules (R1, R2, ...) with a glossary. Use its names exactly.
- `docs/BUILD_PLAN.md`: the steps. Work on one step, the one the owner names.
- `docs/DECISIONS.md`: settled questions. Do not reopen them. Raise a new question if one blocks you.

## How work happens

1. The owner runs `/step Sx`. You reply with a plan and write nothing.
2. After approval you write the tests from the spec's worked examples first, then the code. You touch only the files in the approved plan. If you discover you need another file, stop and say so.
3. The owner runs `/finish Sx`. You run the gate and write the step report.
4. The owner runs `/audit` and decides about the findings. A finding about a file in `docs/`, `CLAUDE.md`, `pyproject.toml`, `scripts/` or `.claude/` is reported and never applied: the reviewer cannot see why that wording is there. `docs/steps/` is the exception, since a step report is your own output and a mistake in it is yours to correct. The owner commits.

`/run-step Sx` does 1 to 4 in one session. The `architect` agent reviews the plan and the audit findings in the owner's place, except for what it sends to the owner. The owner still approves the plan, answers owner questions and says when to commit.

One step per session. If the owner asks for something outside the current step, say that it is outside and ask whether to park it in BUILD_PLAN.md.

## Commands

- `./scripts/check.sh` is the only gate: format, lint, types, layer contracts, dead code, structure, tests with coverage. A step is not done until it passes.
- `uv run pytest tests/domain/test_strokes.py -q` for one file while working.
- `uv add <package>` only in a step whose plan names the package. It prompts the owner.

## Hard rules

- Before writing a function, search for an existing one that does the job. State in your plan what you found. One public name lives in one module.
- Rules of golf and league rules live in `league.domain` only, as pure functions over frozen dataclasses. No I/O, no clock, no database there.
- Never store, cache or patch a derived value. Everything derived comes from `compute_season(facts)`.
- A new format is config first. New code for a format needs a BUILD_PLAN step.
- No speculative code: no parameter, option, flag, class, abstraction or error path that the current step's spec does not need. No compatibility shims. Delete, do not deprecate.
- Never weaken the gate to pass it: no `noqa`, no `type: ignore`, no `pragma: no cover`, no skipped tests, no edits to `pyproject.toml`, `scripts/` or `.claude/` without the owner asking for it.
- When the spec is ambiguous or seems wrong, ask. Do not guess and do not silently fix it.
- Report honestly. Say what exists, where, what you left out and what you are unsure about. Never describe planned work as done.

## Style

Python 3.12, full type hints, pyright strict on `src`. Functions under 30 statements, files under 300 lines. Absolute imports. Comments explain why, not what. Test names cite the rule: `test_r2_plus_handicap_gives_strokes_back`.
