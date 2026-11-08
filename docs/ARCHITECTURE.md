# Architecture

This file is the authority on where code goes. If something does not fit, stop and ask. Do not invent a new place.

## Stack

Python 3.12, managed by uv. FastAPI with Jinja templates and HTMX, server-rendered, no JavaScript build. One kind of script is allowed: a screen's template may carry a short inline script that only moves focus, enables and disables a control, or reloads a page the browser restored from its back-forward cache, so the server answers it again. It does no arithmetic on what the screen shows and no validation, so the server judges every request as if no script ran. Check the card's is the first: it moves to the next hole as a score is typed, disables Submit card after any edit and once the form is sent, so a double tap sends one card, and reloads the screen when the browser restores it after Back. Add a course and tee's is the second: a par moves focus to the next hole's par once one digit is typed, hole 9 to hole 10, and a par's text is selected when it takes focus, while a stroke index does not jump. SQLite through SQLAlchemy 2 with Alembic. Pydantic only at the edges (config JSON, forms). One process, one container. Runtime dependencies are added by the build step that first needs them, never earlier.

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
| `league.web` | Routes, forms, templates, the link-token check and the admin cookie check. | services, domain types for display or for a form to be read into, such as `Tee`, a domain function that makes a display string, such as `tenths_text`, and domain constants a form is read against, such as `HOLES` |

`uv run lint-imports` enforces the direction. `scripts/check_structure.py` enforces one home per public name and a 300-line limit per file.

## Domain module map

One concept, one module. The public API column is filled in by `/finish` as modules are built.

| Module | Owns | Rules | Public API |
|---|---|---|---|
| `domain/facts.py` | Input dataclasses and their shape checks: Tee, Card, IndexRule, StandingsRule, Segment, Pairing, ManualAward, RoundFacts, SeasonFacts, season teams as a player-to-team mapping that rides on SeasonFacts from S9, where from T2 a Card is one player's, or in a shared-ball round one team's, and from T3 a season's mode and a round's format and team cards, and from S10 a round's `late_until`, and from S15c RoundHeading, an open round's number and `closes_at`, which home reads and RoundFacts does not carry, and from S15d2 BaySetting, one line of a season's bay settings, which SeasonFacts carries for the bay screen and `compute_season` does not read | R13 and R15 shapes, R5, R7, R9 and R10 bounds | `Tee`, `Card`, `IndexRule`, `StandingsRule`, `Segment`, `Pairing`, `ManualAward`, `RoundFacts`, `RoundHeading`, `SeasonFacts`, `BaySetting` |
| `domain/configs.py` | How a round is scored, as config, with the bounds on it: DuelConfig, FieldConfig, AllplayConfig, TeamBonusConfig, the ContestConfig union over them, the Basis alias they name, and from T2 one format config per format, with the FormatConfig union over them from T3 | R9 and R16 bounds | `Basis`, `DuelConfig`, `FieldConfig`, `AllplayConfig`, `TeamBonusConfig`, `ContestConfig`, `BestballFormat`, `CombinedFormat`, `ScrambleFormat`, `GreensomeFormat`, `FoursomeFormat`, `FormatConfig` |
| `domain/results.py` | Output dataclasses of the rules and `compute_season`: NetCard, NetEntry, Side, Comparison, Award, RoundAwards, RoundTotal, Gap, StandingsRow, RoundView, SegmentView, SeasonView with its round of one number, through which each screen reads a round's awards and, in a team season, each team's score on the stableford basis and the round's allplay records, which the round result reads, Record, one competitor's allplay record as the others it beats with a draw counting half, and `points_text`, the one string for points to one decimal, over `shown_tenths`, the tenths a screen shows, which a gap also reads, and `tenths_text`, the one string for a one-decimal quantity held in tenths, which `points_text` and a tee's course rating read. `RoundAwards` names the competitors a table counts the round for: those with a counted card, or in a team season the teams with a score under R17, as identity and never the cards. A table's view says the `best_n` it was counted with, as it says its name, because its screen prints it and no rule reads it back. Also ContestEntries, the argument one contest reads: its entries with the tee and closed_at they are read against, so the rule on result dataclasses does not apply to it. |  | `NetCard`, `NetEntry`, `Side`, `Comparison`, `Award`, `RoundAwards`, `RoundTotal`, `Gap`, `StandingsRow`, `shown_tenths`, `points_text`, `tenths_text`, `DuelReason`, `Reason`, `ContestEntries`, `Record`, `RoundView`, `SegmentView`, `SeasonView` with `SeasonView.round` |
| `domain/rounding.py` | Half-up rounding over exact arithmetic, used by every rule that rounds | Arithmetic | `round_half_up` |
| `domain/strokes.py` | Course handicap, playing handicap, stroke allocation, net card, stableford points, and a net card with each hole no worse than net double bogey, which ranks as the points do | R1 R2 R3, R16's course handicap and decision 6's cap | `course_handicap`, `playing_handicap`, `allocate_strokes`, `net_card`, `stableford_points`, `capped_net` |
| `domain/index.py` | Differential, index update, replay of a player's cards | R4 R5 R6 | `differential_tenths`, `next_index_tenths`, `index_by_card_tenths` |
| `domain/sides.py` | Building single, bestball and virtual sides | R7 | `single_side`, `bestball_side`, `virtual_side` |
| `domain/compare.py` | Comparing two sides on a basis | R8 | `compare` |
| `domain/contests.py` | Turning one contest's config, sides and pairings, or the awards of another contest, into awards, an allplay contest's records, which its awards are scaled from, and the admin's manual awards as they are | R9 | `duel_awards`, `field_awards`, `allplay_awards`, `allplay_records`, `teambonus_awards`, `manual_awards`, `is_on_time` |
| `domain/standings.py` | Season and segment tables from awards, with each row's counted cards, round totals, dropped rounds and gap, a competitor's round total in one round, which a round's result reads, round winners and the winning net total from net cards, and a team season's round winners and winning round total from round totals | R10, and R15's round winners | `standings`, `round_total`, `round_winners`, `team_round_winners`, `winning_net_total`, `winning_round_total` |
| `domain/teams.py` | A team's players, the strokes it plays off and its score for a round, per format, and its score on the stableford basis read as strokes, each player's hole no worse than net double bogey | R16 R17 | `team_members`, `team_playing_handicap`, `team_handicaps`, `own_ball_score`, `capped_team_net` |
| `domain/pairing.py` | Pairing proposals | R11 | `swiss_pairings`, `high_low_pairings`, `random_pairings` |
| `domain/access.py` | What a viewer may see and which competitor they are, whether a card is accepted, whether a player's card is in and whether a round takes team cards, what is locked, whether a round's duel pairings let it open, and whether a closed round may reopen | R12, R13 acceptance and reopen, R14's tee lock and duel pairings gate, R15's competitor, team cards and seed index lock | `accepts_card`, `holds_card`, `sees_round`, `competitor_of`, `takes_team_card`, `seed_index_locked`, `tee_locked`, `pairings_published`, `may_reopen` |
| `domain/team_rounds.py` | A team season's rounds: each team's score per contest as an entry whose competitor is the team, field and allplay over those entries, each round's winners, and for the round result each team's score on the stableford basis and the round's allplay records. It calls the modules above and holds no rule of its own | | `team_rounds` |
| `domain/season.py` | `compute_season`: the pipeline that calls the modules above in order | | `compute_season` |
| `domain/home.py` | One viewer's open rounds as home reads them, and the time left until a round's `closes_at`, with home's views, HomePlayer, HomeTeam, HomeRound and HomeView, which say a round's course, tee name, `closes_at` and format, and whether the season is a team season, because the screen prints them and no rule reads them back. It calls `access.py` and `teams.py` and holds no rule of its own | | `time_left`, `home_rounds`, `HomePlayer`, `HomeTeam`, `HomeRound`, `HomeView` |
| `domain/bay.py` | One open round's Set up the bay screen as BayMenu and BayRound: its format, its tee, and the season's bay settings split into the Game lines and each other menu, which the screen prints and no rule reads back. It calls `access.py` and holds no rule of its own | | `bay_round`, `BayMenu`, `BayRound` |
| `domain/entry.py` | One round's card entry for one viewer, as CardEntry: the round's number, its tee's course, name, pars and par, the scores typed with their out, in and total, and the holes in error, whose score is missing, not a whole number or outside R13's bound, with the warn line naming them, while the round takes the viewer's card, and CardIn, which has no fields and says the viewer's card, or their team's team card, is already in, so the route opens the round page instead. It calls `access.py`, reads R13's bound from `facts.py` and holds no rule of its own | | `CardEntry`, `CardIn`, `card_entry` |
| `domain/locked.py` | One open round's Round before playing for a viewer from whom R12 hides it, as LockedRound and LockedTeam: the round's number and `closes_at`, which the screen prints and no rule reads back, each season team in team id order with its one status, a score under R17, one of its two cards in, or not yet, the viewer's team marked, and whether the round takes the viewer's card. It calls `access.py` and `teams.py` and holds no rule of its own | | `LockedRound`, `LockedTeam`, `locked_round` |
| `domain/round_result.py` | One round's result for one viewer in a team season, as RoundResult with ResultTeam, ResultPlayer, ResultAllplay and RankedTeam: the round's number, course and tee name, the viewer's team with its format and its net, the season view's stableford score read as strokes, each player's gross and playing handicap or the team card's gross and team playing handicap, every team with a score ranked by its allplay record from the season view with how many of the others each beats, none while fewer than two teams have a score, the teams without one, and the team's round total with its position before and after the round and its gap, which the screen prints and no rule reads back. It calls `access.py`, `teams.py`, `standings.py` and `rounding.py` and holds no rule of its own | | `round_result`, `RoundResult`, `ResultTeam`, `ResultPlayer`, `ResultAllplay`, `RankedTeam` |

## Store module map

The store holds no rule of its own: a fact's bounds are checked by its domain dataclass on load, R13's uniqueness rules are keys, and a CHECK holds the shape of what no dataclass holds, a round's state, that a round has a `closed_at` exactly when it is closed, and whether a card is a player's or a team's. The public API column is filled in by `/finish`.

| Module | Owns | Public API |
|---|---|---|
| `store/schema.py` | The tables, one per fact, whose keys make a card id and a round number unique in their season, a link token unique among players and a tee's course and name unique together, and whose partial unique indexes allow one counted card per player or team per round (R13), the pydantic adapter for each JSON column, which load and save both use so a round trip has one serialisation, `migrate`, which brings a database to the latest migration, and `open_engine`, the SQLite engine with foreign keys on for every connection | `metadata` and its tables, `migrate`, `open_engine`, `CONTESTS_JSON`, `FORMAT_JSON`, `INDEX_RULE_JSON`, `STANDINGS_RULE_JSON`, `PAIRINGS_JSON`, `HOLES_JSON`, `BAY_SETTINGS_JSON` |
| `store/load.py` | One season's rows turned into `SeasonFacts`, with draft rounds and voided cards left out and JSON validated through pydantic into the domain dataclasses, the player a link token names, a tee by its course and name, or None when no tee has them, every open and closed round of any season on a tee with its counted cards, for R14's tee lock, a season's round of one number in one state, for changing, opening, closing and reopening it, and the headings of its open rounds, for home | `load_season_facts`, `load_player_id`, `load_tee`, `load_rounds_on_tee`, `load_round`, `load_round_headings` |
| `store/save.py` | One fact written as one row on the connection its service hands it, without a commit of its own, with its JSON through the adapters load reads with, a season team and a round's window written onto the rows they belong to, a stored tee, seed index, link token or draft round replaced in place, a round's state and `closed_at` changed when it opens, closes or reopens, and a stored card's scores or its void written in place | `save_player`, `update_link_token`, `save_tee`, `update_tee`, `save_season`, `save_seeded_player`, `update_seed_index`, `save_season_team`, `save_round`, `update_round`, `update_round_state`, `save_window`, `save_card`, `save_team_card`, `update_card_scores`, `update_card_voided`, `save_manual_award` |
| `store/migrations/` | Alembic's environment and its revisions, each spelled out rather than built from the tables. Until S18 there is no database to migrate, so a schema change edits S11's one revision; from S18 each schema change is a revision of its own | |

## Services module map

A use case is one function. It opens its own connection on the engine it is handed, in a transaction when it saves, loads facts through the store, asks the domain, and saves. The public API column is filled in by `/finish`.

| Module | Owns | Public API |
|---|---|---|
| `services/play.py` | What a player does: the player a link token names, a card submitted as the player's own or, in a shared-ball round, as their team's team card (R13, R15), refused in the owner's words once that card is in, the season view a player sees under R12, beside the admin's, which shows every round, a player's home, one open round's bay screen, one round's card entry for the player whose card it takes, one round's page for a viewer, which is the open round before playing while R12 hides it from them and otherwise its result, and the round the Round tab opens, the oldest open round or else the latest closed one | `player_for_link_token`, `Submission`, `submit_card`, `season_view`, `home_view`, `bay_view`, `card_entry_view`, `round_page_view`, `round_tab`, `admin_season_view` |
| `services/setup.py` | What the admin sets up before play: a player with a fresh link token and its replacement, a tee unless one of its course and name is stored, the stored tee of a course and name, and its change while no card is on it (R14), a season with its bay settings, seeded players and season teams in one transaction (R15), a seed index corrected until R15 locks it, and a round on a stored tee created as a draft with its window (R13) and changed while it is a draft (R14) | `create_player`, `replace_link_token`, `create_tee`, `stored_tee`, `change_tee`, `create_season`, `correct_seed_index`, `RoundSetup`, `create_round`, `change_round` |
| `services/run.py` | What the admin does to run a round: open a draft round once each duel contest's pairings are published (R14), close an open round, recording `closed_at`, undo a close while the round has no late card (R13), add a manual award (R9), and correct or void a counted card or team card (R13) | `open_round`, `close_round`, `reopen_round`, `add_manual_award`, `correct_card`, `void_card` |
| `services/clock.py` | The one read of the clock, in naive UTC, on its own so that reading it imports no database | `utc_now` |
| `services/runtime.py` | What the app takes from the world rather than a use case: the engine on a database file, brought to the latest migration, since web imports no store | `open_database` |

## Web module map

A route checks the link-token cookie, or on an admin page the admin cookie, calls one use case and chooses a template. The one exception is a write whose screen shows its own errors: the route first calls the use case that builds that screen, and calls the write unless the screen shows an error. Submit card is the first. web imports no sqlalchemy: the engine comes from `services/runtime.py` and stays on `app.state`. The public API column is filled in by `/finish`.

| Module | Owns | Public API |
|---|---|---|
| `web/app.py` | The app on the database file, season and admin token its environment names, its player routes and the admin's from `web/admin.py`, a stored time as local time, and the link-token cookie, which holds the token and is looked up on every request so a replaced link stops working at once | `create_app` |
| `web/shared.py` | What the player's routes and the admin's both use: the notice screen for a refusal, and the lifetime of the cookies they set | `notice`, `COOKIE_MAX_AGE` |
| `web/admin.py` | The admin's link and the admin cookie, which holds the admin token and is checked against the secret the deployment names on every request, so a changed secret stops the old link at once, and the admin's tee routes with the tee form they read and fill | `admin_router` |
| `web/templates/` | One Jinja template per screen, built from `docs/design/`, `notice.html`, the one screen for every refusal a player meets and for an admin page that cannot be opened, which follows `home.html`'s blocks and `tokens.css` as `bay.html` does, and `formats.html`, which is no screen and holds each format's name, line and game type for the screens that import it | |
| `web/static/app.css` | The copy of `docs/design/tokens.css` | |

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
- A screen's views live in that screen's domain module, such as `home.py`, `bay.py` or `entry.py`, beside what builds them, and `results.py` holds what the rules and `compute_season` produce.
- Functions take what they need and return a value. No mutation of arguments, no module-level state.
- Errors: domain functions raise `ValueError` with a plain message for impossible input. No custom exception hierarchy until a caller needs to tell two errors apart. A key missing between two inputs one caller builds together, such as a duel's key in its round's `pairings`, is that caller's bug: the lookup's own `KeyError` is left to raise.
- Time is passed in. Only `services` reads the clock. Datetimes are naive UTC in the domain and the store: services convert the clock to UTC, and the web layer shows local time, Europe/Oslo.
- Ids are plain `str`. A tee's id is two of them, its course and its name: a caller holding the tee passes the `Tee`, and a caller that only names it passes both. One-decimal quantities (index, course rating, differential) are integers in tenths throughout the domain, with a `_tenths` suffix on the field or parameter, and become a formatted string once, in the view objects, so templates do no arithmetic. That keeps every input to R1 and R4 an integer, so there is no float to convert exactly and no `Fraction(str(x))` waiting for someone who writes `Fraction(x)`. Points are `Fraction` everywhere, in awards and in the config that sets them (D14), and become a string to one decimal, half up, once, in the view objects.
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
