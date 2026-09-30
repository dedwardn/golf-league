# Build plan

One step per session. One step per commit. A step starts with `/step Sx` and ends with `/finish Sx`, then `/audit`, then the owner commits. Steps are done in order. A step is split when it carries more than one idea, not when it crosses a line count. Roughly 300 changed lines is a prompt to stop and ask whether it is still one idea, not a limit: a split that leaves a step with no behaviour to test is the wrong split.

Every step inherits these acceptance criteria: `./scripts/check.sh` passes, each worked example in the named rules has a test, the step report exists, nothing outside the listed modules changed. Dataclasses are added to `facts.py` and `results.py` by the step that first needs them, and only the fields that step needs.

| Step | Adds | Status |
|---|---|---|
| S0 | Guardrails: tooling, layers, checks, Claude Code setup | done |
| S1 | Strokes: playing handicap, allocation, net card | done |
| S2 | Index: differential, update, replay | done |
| S3 | Sides and compare | done |
| S4 | Duel contests: virtual sides, late cards, multiplier | done |
| S5 | Field and allplay contests | done |
| S6 | Teambonus and manual awards | done |
| S6b | The virtual side for any player without an award | done |
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

Modules: `domain/contests.py`, `domain/facts.py` (rename `ContestConfig` to `DuelConfig`, add `FieldConfig` and `AllplayConfig`), `domain/results.py` (widen `Reason`). Rule R9 field and allplay.
Accept: tied positions share points, positions beyond the list, the allplay example, allplay with one card, late cards ignored, basis holes rejected for field, and an allplay share equal to exactly one third.
Watch: one frozen config per kind, so no contest carries a field that means nothing to it and no rule function narrows an Optional to satisfy the type checker. S11 already stores config as JSON, so three shapes cost the store nothing.

## S6 Teambonus and manual awards

Modules: `domain/contests.py`, `domain/facts.py` (add `TeamBonusConfig` and `ManualAward`, season teams as a mapping of player to team). Rule R9 teambonus and manual awards.
First, with no other change in the same commit: split `tests/domain/test_contests.py` into one file per contest kind. It is already 288 lines and R9 has four kinds.
Accept: a winning team, level teams, a player without a team, a member without an on-time card, awards from late cards not counted in the sum, manual awards passed through without multiplier.
The glossary now names the reason a teambonus award and a manual award carry.

## S6b The virtual side for any player without an award

Modules: `domain/contests.py`. Rule R9 duel, as amended. The sweep runs over every counted card whose player has no award in this contest, not only the late ones, and the `earned` set returns as the guard that stops a player earning twice.
Accept: a player who was in no pairing when the round opened earns from the virtual side, a late card still does, a player who lost a pairing is not swept a second time even where `points_loss` is 0, a pairing with both sides missing still leaves each card to the virtual side, and a duel with no pairings at all is an error.
That last one belongs here because this step creates the hazard: until now an unpublished pairing list produced no awards, which is visibly nothing. After the sweep widens it would award every player against a virtual side built from the field, which reads as a result rather than as a round the admin forgot to publish.
This step reverses S4's audit finding 4, which deleted the `earned` set as unreachable. That reasoning was sound only while the sweep was late-only. The step report retracts it in writing, and rewrites the comment on `test_r9_teambonus_two_teams_that_played_and_earned_nothing_share_the_bonus`, whose season case stops being reachable here while its contract still holds.
Not in this step: pairings, the admin screens, anything in S7.

## S7 Standings

Modules: `domain/facts.py` (add `StandingsRule`), `domain/results.py` (add `StandingsRow`), `domain/standings.py`. Rule R10.
Accept: plain sum, best N with fewer than N rounds played, a round the player did not score in never counted as a zero, a manual award kept when best N drops its round, a negative manual award kept the same way, a seeded player who has not played shown at 0, segments with their own best N, a tie on points broken by more cards played over the same rounds, a player who played more but whose extra rounds fell outside the best N still winning that tie, a tie on both shared with the next position skipped, open rounds excluded.

## S8 Pairing proposals

Module: `domain/pairing.py`. Rule R11.
Accept: round 1 ordered by index, no rematch while an unmet unpaired player exists, least recent rematch otherwise, odd player rotation, high_low sides, random sides reproducible from `rng_seed`, odd player and odd side in teams.

## S9 Season pipeline

Modules: `domain/facts.py` (add `RoundFacts`, `SeasonFacts`), `domain/results.py` (add `RoundView`, `SeasonView`), `domain/season.py`. This step resolves `reference_rounds` to entries, so it owns R7's rule that a reference round must use this round's tee: it is the only place rounds and their tees both exist. Every config whose contest reads cards gains `allowance` here, so duel, field and allplay but not teambonus, and `DuelConfig` also gains `reference_rounds`. This step also orders contests so a teambonus runs after the contest its `source` names, and treats a `source` that names no contest of this round as an error: a teambonus that runs first would quietly pay nobody. It passes only contest awards to a teambonus, never manual ones. A manual award's key is a label with no uniqueness (R9), so an admin who labels one with a contest's key would otherwise have it silently summed into a team's total and change who wins the bonus. Each config also gains `kind` here, and `ContestConfig` returns as the union alias over the four, with `kind` as the discriminator this step dispatches on.
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
