# Build plan

One step per session. One step per commit. A step starts with `/step Sx` and ends with `/finish Sx`, then `/audit`, then the owner commits. Steps are done in order. A step is split when it carries more than one idea, not when it crosses a line count. Roughly 300 changed lines is a prompt to stop and ask whether it is still one idea, not a limit: a split that leaves a step with no behaviour to test is the wrong split.

Every step inherits these acceptance criteria: `./scripts/check.sh` passes, each worked example in the named rules has a test, the step report exists, nothing outside the listed modules changed. Dataclasses are added to `facts.py` and `results.py` by the step that first needs them, and only the fields that step needs.

| Step | Adds | Status |
|---|---|---|
| S0 | Guardrails: tooling, layers, checks, Claude Code setup | done |
| S1 | Strokes: playing handicap, allocation, net card | done |
| S2 | Index: differential, update, replay | done |
| S3 | Sides and compare | done |
| S4 | Duel contests: virtual sides, late cards, multiplier | todo |
| S5 | Field and allplay contests | todo |
| S6 | Teambonus and manual awards | todo |
| S7 | Standings | todo |
| S8 | Pairing proposals | todo |
| S9 | Season pipeline with the golden season test | todo |
| S10 | Access: visibility, card acceptance, locking | todo |
| S11 | Store, read side: schema, migrations, load facts | todo |
| S12 | Store, write side: save each fact | todo |
| S13 | Services for play: submit, view | todo |
| S14 | Services for admin: set up, run and correct a season | todo |
| S15 | Web foundation: link tokens, player home, standings | todo |
| S16 | Web for play: card entry and round page | todo |
| S17 | Web for admin | todo |
| S18 | Deploy and backup | todo |
| | **Season can start here** | |
| S19 | Extract: card from Trackman app screenshot | todo |
| S20 | Share: result image and round recap | todo |

Later steps are written only when a season needs them: boxes, knockout from cards, season team table, joker rounds, finals starting strokes, late cards in field contests.

## S1 Strokes

Modules: `domain/facts.py` (`Tee`, `Card`, with the shape checks of R13), `domain/results.py` (`NetCard`), `domain/strokes.py`. Rules R1, R2, R3 and the arithmetic rule.
Public API sketch: `playing_handicap(index_tenths, tee, allowance) -> int`, `allocate_strokes(playing_handicap, tee) -> tuple[int, ...]`, `net_card(card, tee, playing_handicap) -> NetCard`.
Accept: every example in R1, R2 and R3, an invalid tee, an invalid card, and an exact half rounding up rather than to even (index 4.5 on a slope-113 tee whose rating equals par gives 5, where Python's `round` would give 4).
Not in this step: differentials, anything about rounds or players.

## S2 Index

Modules: `domain/rounding.py` (new, `round_half_up` moved out of `strokes.py`), `domain/facts.py` (add `IndexRule`, and the `card_id` and `submitted_at` that R6 and R13 need on `Card`), `domain/index.py`. Rules R4, R5, R6.
Public API sketch: `differential_tenths(card, tee, index_tenths) -> int`, `next_index_tenths(old_tenths, differential_tenths, rule, use_early_rate) -> int`, `index_by_card_tenths(seed_index_tenths, provisional, cards_with_tees, rule) -> dict[str, int]` where `cards_with_tees` is a sequence of `(Card, Tee)` for one player.
Accept: the R4 and R5 examples, clamping at both ends, the early rate ending after `early_cards`, replay order by `submitted_at` then card id, leaving a card out changes later indexes.
Not in this step: choosing seed indexes, history from old seasons.

## S3 Sides and compare

Modules: `domain/results.py` (add `NetEntry`, `Side`, `Comparison`), `domain/sides.py`, `domain/compare.py`. Rules R7, R8.
Accept: best ball with one member missing, a missing side, the R7 examples, fewer than `virtual_n` cards, a tie for the last place settled by the lower card id, exclusion of the opposing players' cards, an empty reference set, the R8 example, a draw on each basis.
Not in this step: pairings, awards.

## S4 Duel contests

Modules: `domain/facts.py` (add `ContestConfig` with the common and duel fields, `Pairing`, and `Basis` moved here from `compare.py`), `domain/results.py` (add `Award`), `domain/contests.py`. Rule R9 duel. The function receives the round's counted cards netted at the contest's allowance, `closed_at`, pairings and the contest config.
Accept: win, draw and loss for single and bestball sides, a bestball member without an on-time card gets nothing, missing side, single-sided pairing, late card meets the virtual side and changes nobody else, both sides missing, multiplier, a late bestball member who earned nothing meets the virtual side alone.
Watch: `basis` is a `ContestConfig` field, so `Basis` belongs in `facts.py` and `compare.py` imports it; `facts.py` never imports a rule module. `ContestConfig` bounds `virtual_n` at 1 or more, because a slice with 0 quietly gives net par and a negative value quietly keeps every card but the worst. A missing side arrives in two shapes: `bestball_side` returns `None`, while a missing single side is the caller having no entry at all, so settle emptiness once per side before building it.
Not in this step: other contest kinds.

## S5 Field and allplay contests

Modules: `domain/contests.py`, `domain/facts.py` (extend `ContestConfig`). Rule R9 field and allplay.
Accept: tied positions share points, positions beyond the list, the allplay example, allplay with one card, late cards ignored, basis holes rejected for field.

## S6 Teambonus and manual awards

Modules: `domain/contests.py`, `domain/facts.py` (extend `ContestConfig`, add `ManualAward`, season teams as a mapping of player to team). Rule R9 teambonus and manual awards.
Accept: a winning team, level teams, a player without a team, a member without an on-time card, awards from late cards not counted in the sum, manual awards passed through without multiplier.

## S7 Standings

Modules: `domain/facts.py` (add `StandingsRule`), `domain/results.py` (add `StandingsRow`), `domain/standings.py`. Rule R10.
Accept: plain sum, best N with fewer than N rounds played, a negative manual award, segments with their own best N, tie order, open rounds excluded.

## S8 Pairing proposals

Module: `domain/pairing.py`. Rule R11.
Accept: round 1 ordered by index, no rematch while an unmet unpaired player exists, least recent rematch otherwise, odd player rotation, high_low sides, random sides reproducible from `rng_seed`, odd player and odd side in teams.

## S9 Season pipeline

Modules: `domain/facts.py` (add `RoundFacts`, `SeasonFacts`), `domain/results.py` (add `RoundView`, `SeasonView`), `domain/season.py`. This step resolves `reference_rounds` to entries, so it owns R7's rule that a reference round must use this round's tee: it is the only place rounds and their tees both exist. `ContestConfig` gains `allowance` and `reference_rounds` here, in the step that reads them.
Accept: one hand-built season of 6 players and 4 rounds that uses every contest kind, a late card, a best ball round and a manual award, checked against hand-computed awards and standings, and a reference round on another tee is an error. The fixture lives in `tests/domain/fixtures/` and is agreed with the owner before coding.
Watch: R7 nets a card at the contest's allowance, so entries are built per contest, not once per round. A pipeline that caches one set of entries per round is wrong the moment two contests differ in allowance.

## S10 Access

Module: `domain/access.py`. Rules R12, R13 acceptance, R14 locking.
Accept: a player before and after their own card, after close, the admin, a second card, a late card with and without `late_until`, a new card after a void.

## S11 Store, read side

Adds dependencies: sqlalchemy, alembic, pydantic. Modules under `league/store`. Tables for the facts in SPEC section 4 only. Contest, index and standings config stored as JSON and validated on load. `load_season_facts(season_id) -> SeasonFacts` leaves out voided cards.
Accept: the S9 fixture inserted into a temporary database loads into identical `SeasonFacts`.

## S12 Store, write side

One save function per fact. No updates of derived values, because there are none.
Accept: each save function round-trips through `load_season_facts`.

## S13 Services for play

Modules under `league/services`. Use cases: find the player for a link token, submit a card, season view for a viewer (R12 applied).
Accept: each use case tested against a temporary database, with the clock passed in.

## S14 Services for admin

Use cases: create player with link token and sim names, tee, season with rules and seed indexes, season teams, round. Open and close a round. Propose and publish pairings. Add a manual award. Correct and void a card.
Accept: as S13. Split in two if the plan exceeds the budget.

## S15 to S17 Web

Adds dependencies: fastapi, uvicorn, jinja2, python-multipart. Each route calls one service. Templates contain no arithmetic. Mobile first. S15: app, link-token cookie, player home, standings. S16: card entry with 18 inputs and a confirm screen, round page. S17: admin pages for everything in S14, drawn from `docs/design/`.
Accept: route tests with the test client. The owner clicks through on a phone before `/finish`.

## S18 Deploy and backup

One Dockerfile, SQLite on a persistent volume in an EU region, nightly copy of the database file off the machine, a one-page runbook. The hosting choice is made at the start of this step and recorded in DECISIONS.md.

## S19 Extract

Adds dependency: anthropic. `extract.read_card(image_bytes) -> DraftCard` with per-hole scores and, when visible, pars and stroke indexes. The player always confirms or corrects the draft before it becomes a card. Before this step the owner collects 20 real screenshots as the test set, and the step starts by measuring accuracy on them.

## S20 Share

A round recap as text and one result image per round for the group chat. Format decided at the start of the step.
