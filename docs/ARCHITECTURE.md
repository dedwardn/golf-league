# Architecture

This file is the authority on where code goes. If something does not fit, stop and ask. Do not invent a new place.

## Stack

Python 3.12, managed by uv. FastAPI with Jinja templates and HTMX, server-rendered, no JavaScript build. SQLite through SQLAlchemy 2 with Alembic. Pydantic only at the edges (config JSON, forms). One process, one container. Runtime dependencies are added by the build step that first needs them, never earlier.

## The one pipeline

```
facts (store)  ->  compute_season(facts)  ->  SeasonView  ->  templates
```

Services load facts, call `league.domain.season.compute_season`, and hand the result to the web layer. Writing works the other way: a service validates a new fact with a domain function and saves it. Derived values are never stored. There is no incremental state, no cache and no repair script. If a number is wrong, the fix is in a pure function and the next request is right.

## Layers

| Layer | Holds | May import |
|---|---|---|
| `league.domain` | Every rule in SPEC.md as pure functions over frozen dataclasses. No I/O, no clock, no randomness without a passed `rng_seed`. | Standard library only |
| `league.store` | Tables, migrations, functions that load and save facts, conversion between rows or JSON and domain dataclasses. | domain |
| `league.extract` | Scorecard image to draft card. | domain |
| `league.services` | One function per use case. Transactions, the clock, calls to store, domain and extract. | store, extract, domain |
| `league.web` | Routes, forms, templates, the link-token check. | services, domain types for display |

`uv run lint-imports` enforces the direction. `scripts/check_structure.py` enforces one home per public name and a 300-line limit per file.

## Domain module map

One concept, one module. The public API column is filled in by `/finish` as modules are built.

| Module | Owns | Rules | Public API |
|---|---|---|---|
| `domain/facts.py` | Input dataclasses and their shape checks: Tee, Card, IndexRule, StandingsRule, DuelConfig, FieldConfig, AllplayConfig, TeamBonusConfig, Pairing, ManualAward, RoundFacts, SeasonFacts, the Basis alias they name, season teams as a player-to-team mapping that rides on SeasonFacts from S9, and from S9 the ContestConfig union over the four configs | R13 shapes, R5 and R9 bounds | `Basis`, `Tee`, `Card`, `IndexRule`, `DuelConfig`, `FieldConfig`, `AllplayConfig`, `TeamBonusConfig`, `Pairing`, `ManualAward` |
| `domain/results.py` | Output dataclasses: NetCard, NetEntry, Side, Comparison, Award, StandingsRow, RoundView, SeasonView |  | `NetCard`, `NetEntry`, `Side`, `Comparison`, `Award`, `DuelReason`, `Reason` |
| `domain/rounding.py` | Half-up rounding over exact arithmetic, used by every rule that rounds | Arithmetic | `round_half_up` |
| `domain/strokes.py` | Playing handicap, stroke allocation, net card, stableford points | R1 R2 R3 | `playing_handicap`, `allocate_strokes`, `net_card`, `stableford_points` |
| `domain/index.py` | Differential, index update, replay of a player's cards | R4 R5 R6 | `differential_tenths`, `next_index_tenths`, `index_by_card_tenths` |
| `domain/sides.py` | Building single, bestball and virtual sides | R7 | `single_side`, `bestball_side`, `virtual_side` |
| `domain/compare.py` | Comparing two sides on a basis | R8 | `compare` |
| `domain/contests.py` | Turning one contest's config, sides and pairings, or the awards of another contest, into awards, and the admin's manual awards as they are | R9 | `duel_awards`, `field_awards`, `allplay_awards`, `teambonus_awards`, `manual_awards` |
| `domain/standings.py` | Season and segment tables from awards | R10 | |
| `domain/pairing.py` | Pairing proposals | R11 | |
| `domain/access.py` | What a viewer may see, whether a card is accepted, what is locked | R12, R13 acceptance, R14 | |
| `domain/season.py` | `compute_season`: the pipeline that calls the modules above in order | | |

## Where does it go

| You are about to write | It belongs in |
|---|---|
| Anything that mentions strokes, holes, points, handicap, ranking | `domain`, in the module that owns the rule |
| A new format or league mechanic | First as contest or standings **config**. New code only if the four contest kinds cannot express it, and then as a new step in BUILD_PLAN.md |
| A SQL query or a table | `store` |
| "Now", a transaction, a sequence of load, decide, save | `services` |
| Parsing a form, choosing a template, a redirect | `web` |
| A call to a vision model | `extract` |
| A helper used by one function | Inside that function's module, private, directly above its caller |
| A helper you think two modules need | Stop. It probably belongs to one of them and the other should call it. The exception is a helper that implements the arithmetic rule rather than a numbered rule, which lives in `rounding.py` |

## Conventions

- Names come from the glossary in SPEC.md. No synonyms: it is `index`, never `hcp` or `handicap_index`. It is `card`, never `score` or `scorecard`.
- Frozen dataclasses with full type hints. No dicts as records, meaning no dict standing in for a dataclass; a mapping used as a lookup, such as player id to season team, is an index and is fine. No inheritance. No classes that only hold functions.
- A result dataclass carries what a rule produced and the identity of what produced it, never the inputs the rule consumed: no tee and no index on a net card, no contest config on a side. Inputs are arguments to the function that computed the result, and stop there. A result that names which of its inputs won, such as the winning side of a comparison, is naming the answer, not keeping the input.
- Functions take what they need and return a value. No mutation of arguments, no module-level state.
- Errors: domain functions raise `ValueError` with a plain message for impossible input. No custom exception hierarchy until a caller needs to tell two errors apart.
- Time is passed in. Only `services` reads the clock.
- Ids are plain `str`. One-decimal quantities (index, course rating, differential) are integers in tenths throughout the domain, with a `_tenths` suffix on the field or parameter, and become a formatted string once, in the view objects, so templates do no arithmetic. That keeps every input to R1 and R4 an integer, so there is no float to convert exactly and no `Fraction(str(x))` waiting for someone who writes `Fraction(x)`. Points are `Fraction` everywhere, in awards and in the config that sets them (D14).
- A parameter may share a name with the function that computes it (`playing_handicap`, `differential_tenths`). The name reads correctly at the call site and the glossary owns the public name. If a function ever needs both, rename the parameter inside that function, never the function.
- A bound on one dataclass's own fields lives in `facts.py` beside that dataclass. A bound that needs two facts together, or a whole collection, lives with the rule module that can see both: an empty pairing list and a single side naming two players are R9 bounds that only `contests.py` can check.
- A dataclass carries the fields some code reads now. SPEC stays the authority on what a contest or a round *has*; the dataclass grows to match as each step's code catches up, because a field defined before anything reads it is dead weight the gate flags. A test may assert a field where this step's own logic decides its value, never to keep an unread field alive.
- A constant moves out of a rule module only when keeping it there would make another module import that one for a reason unrelated to what it owns. An import that rides on a dependency the modules already have is not that.
- Tests mirror modules: `tests/domain/test_strokes.py`. Test names cite the rule: `test_r2_plus_handicap_gives_strokes_back`. A module that holds several kinds of one rule gets one test file per kind, so `contests.py` has `test_contests_duel.py` and its siblings while the module itself stays whole. The 300-line limit is not extended to tests: the split follows the rule boundary, not a line count.
- Comments explain why, never what. No commented-out code, no TODOs without a BUILD_PLAN step id.

## What went wrong in v0.1, as rules

1. The playing handicap formula existed in both `scoring_utils.py` and the tournament engine. Rule: one public name, one module, enforced by `check_structure.py`.
2. Standings, pairing state and handicaps were stored and drifted, which needed `repair_hcp_data.py` and several "calculate on the fly" fixes. Rule: derived values are never stored.
3. Each format had its own processing function with copied logic. Rule: formats are config over four contest kinds that share `sides` and `compare`.
4. Documents described work as complete that was not. Rule: step reports say what exists, where, and what was left out.
