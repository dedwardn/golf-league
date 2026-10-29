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
| `domain/facts.py` | Input dataclasses and their shape checks: Tee, Card, IndexRule, StandingsRule, Segment, Pairing, ManualAward, RoundFacts, SeasonFacts, season teams as a player-to-team mapping that rides on SeasonFacts from S9, where from T2 a Card is one player's, or in a shared-ball round one team's, and from T3 a season's mode and a round's format and team cards, and from S10 a round's `late_until` | R13 and R15 shapes, R5, R7, R9 and R10 bounds | `Tee`, `Card`, `IndexRule`, `StandingsRule`, `Segment`, `Pairing`, `ManualAward`, `RoundFacts`, `SeasonFacts` |
| `domain/configs.py` | How a round is scored, as config, with the bounds on it: DuelConfig, FieldConfig, AllplayConfig, TeamBonusConfig, the ContestConfig union over them, the Basis alias they name, and from T2 one format config per format, with the FormatConfig union over them from T3 | R9 and R16 bounds | `Basis`, `DuelConfig`, `FieldConfig`, `AllplayConfig`, `TeamBonusConfig`, `ContestConfig`, `BestballFormat`, `CombinedFormat`, `ScrambleFormat`, `GreensomeFormat`, `FoursomeFormat`, `FormatConfig` |
| `domain/results.py` | Output dataclasses: NetCard, NetEntry, Side, Comparison, Award, RoundAwards, StandingsRow, RoundView, SegmentView, SeasonView. Also ContestEntries, the argument one contest reads: its entries with the tee and closed_at they are read against, so the rule on result dataclasses does not apply to it. |  | `NetCard`, `NetEntry`, `Side`, `Comparison`, `Award`, `RoundAwards`, `StandingsRow`, `DuelReason`, `Reason`, `ContestEntries`, `RoundView`, `SegmentView`, `SeasonView` |
| `domain/rounding.py` | Half-up rounding over exact arithmetic, used by every rule that rounds | Arithmetic | `round_half_up` |
| `domain/strokes.py` | Course handicap, playing handicap, stroke allocation, net card, stableford points | R1 R2 R3, and R16's course handicap | `course_handicap`, `playing_handicap`, `allocate_strokes`, `net_card`, `stableford_points` |
| `domain/index.py` | Differential, index update, replay of a player's cards | R4 R5 R6 | `differential_tenths`, `next_index_tenths`, `index_by_card_tenths` |
| `domain/sides.py` | Building single, bestball and virtual sides | R7 | `single_side`, `bestball_side`, `virtual_side` |
| `domain/compare.py` | Comparing two sides on a basis | R8 | `compare` |
| `domain/contests.py` | Turning one contest's config, sides and pairings, or the awards of another contest, into awards, and the admin's manual awards as they are | R9 | `duel_awards`, `field_awards`, `allplay_awards`, `teambonus_awards`, `manual_awards`, `is_on_time` |
| `domain/standings.py` | Season and segment tables from awards, round winners from net cards, and a team season's round winners from round totals | R10, and R15's round winners | `standings`, `round_winners`, `team_round_winners` |
| `domain/teams.py` | A team's playing handicap and its score for a round, per format | R16 R17 | `team_playing_handicap`, `own_ball_score` |
| `domain/pairing.py` | Pairing proposals | R11 | `swiss_pairings`, `high_low_pairings`, `random_pairings` |
| `domain/access.py` | What a viewer may see, whether a card is accepted and whether a round takes team cards, what is locked | R12, R13 acceptance, R14's tee lock, R15's team cards and seed index lock | `accepts_card`, `sees_round`, `takes_team_card`, `seed_index_locked`, `tee_locked` |
| `domain/season.py` | `compute_season`: the pipeline that calls the modules above in order | | `compute_season` |

## Store module map

The store holds no rule of its own: a fact's bounds are checked by its domain dataclass on load, R13's uniqueness rules are keys, and a CHECK holds the shape of what no dataclass holds, a round's state and whether a card is a player's or a team's. The public API column is filled in by `/finish`.

| Module | Owns | Public API |
|---|---|---|
| `store/schema.py` | The tables, one per fact, whose keys make a card id and a round number unique in their season and a link token unique among players, and whose partial unique indexes allow one counted card per player or team per round (R13), the pydantic adapter for each JSON column, which load and save both use so a round trip has one serialisation, and `migrate`, which brings a database to the latest migration | `metadata` and its tables, `migrate`, `CONTESTS_JSON`, `FORMAT_JSON`, `INDEX_RULE_JSON`, `STANDINGS_RULE_JSON`, `PAIRINGS_JSON`, `HOLES_JSON` |
| `store/load.py` | One season's rows turned into `SeasonFacts`, with draft rounds and voided cards left out and JSON validated through pydantic into the domain dataclasses, and the player a link token names | `load_season_facts`, `load_player_id` |
| `store/save.py` | One fact written as one row on the connection its service hands it, without a commit of its own, with its JSON through the adapters load reads with, and a season team written onto its players' seeded rows | `save_player`, `save_tee`, `save_season`, `save_seeded_player`, `save_season_team`, `save_round`, `save_card`, `save_team_card`, `save_manual_award` |
| `store/migrations/` | Alembic's environment and its revisions, each spelled out rather than built from the tables. Until S18 there is no database to migrate, so a schema change edits S11's one revision; from S18 each schema change is a revision of its own | |

## Services module map

A use case is one function. It opens its own connection on the engine it is handed, in a transaction when it saves, loads facts through the store, asks the domain, and saves. The public API column is filled in by `/finish`.

| Module | Owns | Public API |
|---|---|---|
| `services/play.py` | What a player does: the player a link token names, a card submitted as the player's own or, in a shared-ball round, as their team's team card (R13, R15), and the season view a player sees under R12, beside the admin's, which shows every round | `player_for_link_token`, `Submission`, `submit_card`, `season_view`, `admin_season_view` |

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
- Errors: domain functions raise `ValueError` with a plain message for impossible input. No custom exception hierarchy until a caller needs to tell two errors apart. A key missing between two inputs one caller builds together, such as a duel's key in its round's `pairings`, is that caller's bug: the lookup's own `KeyError` is left to raise.
- Time is passed in. Only `services` reads the clock. Datetimes are naive UTC in the domain and the store: services convert the clock to UTC, and the web layer shows local time.
- Ids are plain `str`. One-decimal quantities (index, course rating, differential) are integers in tenths throughout the domain, with a `_tenths` suffix on the field or parameter, and become a formatted string once, in the view objects, so templates do no arithmetic. That keeps every input to R1 and R4 an integer, so there is no float to convert exactly and no `Fraction(str(x))` waiting for someone who writes `Fraction(x)`. Points are `Fraction` everywhere, in awards and in the config that sets them (D14).
- A parameter may share a name with the function that computes it (`playing_handicap`, `differential_tenths`). The name reads correctly at the call site and the glossary owns the public name. If a function ever needs both, rename the parameter inside that function, never the function.
- A bound on one dataclass's own fields lives beside that dataclass, in `facts.py` or `configs.py`. A bound that needs two facts together, or a whole collection, lives with the rule module that can see both: an empty pairing list and a single side naming two players are R9 bounds that `contests.py` checks. A container's own fields include what it holds: `RoundFacts` checks that a teambonus `source` names a duel contest of its round, and `SeasonFacts` that a reference round is a round of the season on the same tee, because no rule module sees a whole round or season and `season.py` holds no rule.
- A dataclass carries the fields some code reads now. SPEC stays the authority on what a contest or a round *has*; the dataclass grows to match as each step's code catches up, because a field defined before anything reads it is dead weight the gate flags. A test may assert a field where this step's own logic decides its value, never to keep an unread field alive.
- A constant moves out of a rule module only when keeping it there would make another module import that one for a reason unrelated to what it owns. An import that rides on a dependency the modules already have is not that.
- Tests mirror modules: `tests/domain/test_strokes.py`. Test names cite the rule: `test_r2_plus_handicap_gives_strokes_back`. A module that holds several kinds of one rule gets one test file per kind, so `contests.py` has `test_contests_duel.py` and its siblings while the module itself stays whole. The 300-line limit is not extended to tests: the split follows the rule boundary, not a line count.
- Comments explain why, never what. No commented-out code, no TODOs without a BUILD_PLAN step id.

## What went wrong in v0.1, as rules

1. The playing handicap formula existed in both `scoring_utils.py` and the tournament engine. Rule: one public name, one module, enforced by `check_structure.py`.
2. Standings, pairing state and handicaps were stored and drifted, which needed `repair_hcp_data.py` and several "calculate on the fly" fixes. Rule: derived values are never stored.
3. Each format had its own processing function with copied logic. Rule: formats are config over four contest kinds that share `sides` and `compare`.
4. Documents described work as complete that was not. Rule: step reports say what exists, where, and what was left out.
