# Build plan

One step per session. One step per commit. A step starts with `/step Sx` and ends with `/finish Sx`, then `/audit`, then the owner commits. Steps are done in order. A step is split when it carries more than one idea, not when it crosses a line count. Roughly 300 changed lines is a prompt to stop and ask whether it is still one idea, not a limit: a split that leaves a step with no behaviour to test is the wrong split.

Every step inherits these acceptance criteria: `./scripts/check.sh` passes, each worked example in the named rules has a test, the step report exists, nothing outside the listed modules changed. Dataclasses are added to `facts.py`, `configs.py`, `results.py` or a screen's own domain module by the step that first needs them, and only the fields that step needs.

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
| S7 | Standings | done |
| S8 | Pairing proposals | done |
| S9a | Round winners and reference entries | done |
| S9b | Season pipeline with the golden season test | done |
| T1 | Competitors: the rename that lets a team earn awards | done |
| T2 | Team handicaps and team scores | done |
| T3 | Team season pipeline with the golden team season | done |
| S10 | Access: visibility, card acceptance, locking | done |
| S11 | Store, read side: schema, migrations, load facts | done |
| S12 | Store, write side: save each fact | done |
| S13 | Services for play: submit, view | done |
| S14a | Services for admin: set up a season | done |
| S14b | Services for admin: run a round | done |
| S14c | Services for admin: correct a round | done |
| S15a | Web foundation: link tokens, standings table | done |
| S15b | Standings for the viewer | done |
| S15b2 | Standings round grid | done |
| S15c | Player home | done |
| S15d1 | A tee's course and name | done |
| S15d2 | Set up the bay | done |
| S16a | Card entry | done |
| S16b | Round before playing | done |
| S16c1 | Round result | todo |
| S16c2 | Getting around and notices | todo |
| S17 | Web for admin | todo |
| S18 | Deploy and backup | todo |
| | **Season can start here** | |
| S19 | Extract: card from Trackman app screenshot | todo |
| S20 | Share: result image and round recap | todo |
| S21 | Individual season: pairing admin and duel screens | todo |

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

Modules: `domain/facts.py` (add `StandingsRule`, `Segment`), `domain/results.py` (add `RoundAwards`, `StandingsRow`), `domain/standings.py`. Rule R10.
Accept: plain sum, best N with fewer than N rounds played, a round the player did not score in never counted as a zero, a manual award kept when best N drops its round, a negative manual award kept the same way, a seeded player who has not played shown at 0, segments with their own best N, a tie on points shared with the next position skipped, a shared first included, and the R10 bounds: `best_n` of 1 or more, a segment starting at round 1 or later and ending no earlier than it starts, segment names unique.

## S8 Pairing proposals

Module: `domain/pairing.py`. Rule R11.
Accept: round 1 ordered by index, a shared position broken by index then player id, no rematch while an unmet unpaired player exists, least recent rematch otherwise, the highest-ranked of those last met in the same round, players on opposite best ball sides counted as having met, the single-sided player chosen before the rest are paired, the rotation going to the lowest-ranked with the fewest single-sided pairings including once everyone has had one, high_low sides with the middle player alone, random sides reproducible from `rng_seed` with the last of the shuffle alone, sides paired by combined points, and an odd number of sides giving the single-sided pairing to the one-member side when there is one, even when it is not lowest on combined points, and otherwise to the lowest side.

## S9a Round winners and reference entries

Modules: `domain/standings.py`, `domain/contests.py`, `domain/results.py`. Rules R10 for the round winner, R7 for reference rounds. `round_winners` takes one closed round's on-time entries netted at full playing handicap and returns the ids of the players with the lowest net total. The caller filters, as `standings` receives closed rounds only. The winning net total arrives with S15, which reads it. `duel_awards` gains `references`: the on-time entries of the contest's reference rounds, netted at this contest's allowance with the index R6 gave each card, from which every virtual side is drawn. The caller filters them, each reference round against its own `closed_at`. To stay within five arguments, the three card-reading contests take one input type from `results.py` holding the tee, `closed_at` and the entries netted for that contest: `duel_awards` takes it with `references`, `pairings` and `config`, and `field_awards` and `allplay_awards` take it with `config`. `teambonus_awards` is unchanged. The caller passes this round's on-time entries when `reference_rounds` is empty.
Accept: the lowest net total wins, players level on it share the round, no entries means no winner, a virtual side drawn from the reference entries rather than this round's, and reference entries still excluding the players on the side the virtual side will meet.

## S9b Season pipeline

Modules: `domain/facts.py` (add `RoundFacts`, `SeasonFacts`), `domain/results.py` (add `RoundView`, `SegmentView`, `SeasonView`), `domain/season.py`, `domain/contests.py` (only to make the on-time test public as `is_on_time`, because S9a left the filtering to this step's caller). `RoundView` holds the round's `RoundAwards` from S7 rather than repeating its fields, and the round's winners from `round_winners` (S9a) over its on-time cards netted at full playing handicap. This step resolves `reference_rounds` to entries, so it owns R7's rule that a reference round must be a round of the season and use this round's tee: it is the only place rounds and their tees both exist. Every config whose contest reads cards gains `allowance` here, bounded by R9, so duel, field and allplay but not teambonus, and `DuelConfig` also gains `reference_rounds`. This step also orders contests so a teambonus runs after the contest its `source` names, and treats a `source` that names no duel contest of this round as an error, which `RoundFacts` raises. It passes only contest awards to a teambonus, never manual ones. A manual award's key is a label with no uniqueness (R9), so an admin who labels one with a contest's key would otherwise have it silently summed into a team's total and change who wins the bonus. Each config also gains `kind` here, and `ContestConfig` returns as the union alias over the four, with `kind` as the discriminator this step dispatches on. `SeasonFacts` holds open and closed rounds only: a draft round has no cards, and R14 opens a round with a duel only once its pairings are published, so a duel without pairings stays an error.
Accept: one hand-built season of 6 players and 4 rounds that uses every contest kind, a late card, a best ball round and a manual award, checked against hand-computed awards, the season and segment tables, and round winners, one round won on a tie. The late card would change its round's winner if it were counted. One round has two card-reading contests at allowances that order its players differently. A late card moves its player's index for their next card. A reference round on another tee, naming no round of the season, later than its own round or named twice, is an error. A virtual side built from a named reference round reads that round's on-time cards, netted at this contest's allowance. A provisional player's index moves at the early rate. Standings receive closed rounds only, so an open round's awards appear in no table. The fixture lives in `tests/fixtures/` and is agreed with the owner before coding.
Watch: R7 nets a card at the contest's allowance, so entries are built per contest, not once per round. A pipeline that caches one set of entries per round is wrong the moment two contests differ in allowance.

## T1 Competitors

Rule R15's competitor. Modules: `domain/results.py`, `domain/facts.py`, and every module and test that reads a renamed field. Where a field or parameter holds whoever earns an award or holds a standings row, it is renamed from player to competitor: `NetEntry`, `Side`, `Award`, `StandingsRow`, `ManualAward`, and the seeded list `standings` takes. Pairings, cards and seed indexes stay about players. The one step with no behaviour of its own: the whole suite proves the rename by staying green, and keeping it apart leaves T3's diff about teams only.
Accept: no behaviour changes and no expected value in any test changes.

## T2 Team handicaps and team scores

Rules R16, R17. First, with no other change in the same commit: the contest configs, the `Basis` alias and R9's bounds on them move from `domain/facts.py` to a new `domain/configs.py`, the fallback the owner set at S9b, because `facts.py` has 286 lines and the format config does not fit. Every module and test that imports a moved name changes that import only, and the suite stays green with no expected value changed. Then modules: `domain/configs.py` (the format config with its allowances and their bounds), `domain/facts.py` (`Card`'s docstring: a team card is a `Card`), `domain/strokes.py` (`course_handicap`, R16's exact bracket, which `playing_handicap` then rounds, so R1 is written once), new `domain/teams.py` (team playing handicaps and team scores). Pure functions over one team in one round; nothing here reads a season. An own-ball team's score is a `NetCard`, or none when either player's card is missing: the players' own net cards come in as `NetCard`s and never become `NetEntry`s (settled at T1). A shared-ball team's score is R3's `net_card` over its team card at the team's playing handicap, and a team without a team card leaves its caller nothing to net, as a missing single side does. The score depends on the contest's basis as well as the format. Best ball takes the lower net per hole on every basis. Combined sums the nets on total and holes, but on stableford it is a synthetic net card with each hole at par + 2 minus the two players' summed points, so R8, which recomputes stableford from a net card, reads exactly R17's summed points and not the points of the summed net.
Accept: R16's worked example for every format, an allowance overridden by the round, an allowance outside 0 to 100 as an error, R17's worked example, best ball and combined on total and stableford, a combined stableford hole where one player scores 0 points and the summed net would score fewer than the summed points, a shared-ball team card netted at the team's playing handicap, and an own-ball team missing either player's card having no score, under best ball and under combined.

## T3 Team season pipeline

Rule R15. Modules: `domain/configs.py` (the union over the five format configs), `domain/facts.py` (`SeasonFacts` gains `mode`, `RoundFacts` gains `format` and team cards), `domain/season.py` (the team branch), `domain/standings.py` (a team season's round winners). In a team season `compute_season` plays every card off the seed index, builds each team's score per round under R17 and wraps it in a `NetEntry` whose competitor is the team, runs field and allplay over those entries, and builds the team tables. The entry's `submitted_at` is the latest of the cards it was built from; its `card_id`, which field and allplay do not read, is this step's to choose. `SeasonFacts` refuses a team season with a seeded player outside a team, a team not of two, a contest other than field and allplay, or a round without a format.
Accept: one hand-built team season of 4 teams and 5 rounds, one round per format, scored by allplay with `best_n` 4, with a round where one player's card is missing, a late team card, a shared-ball round in which one team has no team card, and one round that also has a field contest, checked against hand-computed awards, the team table and round winners, with each team's score worked out in the step report, since the view carries no score. One round is won on its round total by a team that does not have the lowest net total. A late card scores nothing. The fixture lives in `tests/fixtures/` and is agreed with the owner before coding.

## S10 Access

Modules: `domain/access.py`, `domain/facts.py` (`RoundFacts` gains `late_until`, which acceptance and visibility read). Rules R12, R13 acceptance, R14's tee lock, and R15's team cards and seed index lock: one team card per team in a shared-ball round, visibility once the team's card is in, and a team season's seed indexes locked once round one closes. R14's lock on a round's contest config and pairings is S14b's, because a draft round never reaches the domain. The admin's view does not ask R12 (S13).
Accept: a player before and after their own card, after close, a closed round that still takes late cards, a second card, a late card with and without `late_until`, a new card after a void, a card from a player without a seed index for the season refused, one team card for both partners in a shared-ball round and none shared in an own-ball round, a tee with and without a card or team card, and a team season's seed index before and after round one closes.

## S11 Store, read side

Adds dependencies: sqlalchemy, alembic, pydantic. Modules under `league/store`. Tables for the facts in SPEC section 4 only, including the season's mode, its teams, team cards and a round's format. Contest, index and standings config stored as JSON and validated on load. `load_season_facts(connection, season_id) -> SeasonFacts` runs on the connection its service hands it, and leaves out voided cards, voided team cards and draft rounds. Until S18 there is no database to migrate, so S13 and S14 extend S11's one migration rather than adding new ones; the exemption of `store/migrations/versions` from the structure check's one-home rule waits for the first migration after S18.
Accept: the S9b and T3 fixtures inserted into a temporary database load into identical `SeasonFacts`. The database holds one counted card per player per round and one counted team card per team per round (R13): a second counted card is refused, and a new card after a void is accepted.

## S12 Store, write side

Modules: `store/save.py` (new), and `store/schema.py` and `store/load.py` for the JSON adapters both use. One save function per fact in SPEC section 4 that the tables hold, each on the connection its service hands it and without a commit of its own. A season team is saved onto its players' seeded rows. Changing a stored fact, such as opening or closing a round or voiding or correcting a card, is S14's. No updates of derived values, because there are none.
Accept: each save function round-trips through `load_season_facts`, and the save functions replace S11's test row writers.

## S13 Services for play

Modules: `services/play.py` (new), `store/schema.py`, the `s11` migration, `store/save.py` and `store/load.py` for a player's link token, and `domain/access.py`, which makes public whether a round takes team cards (R15). Use cases: find the player for a link token, submit a card, season view for a viewer (R12 applied).
Accept: each use case tested against a temporary database, with the clock passed in, and the admin's season view showing every round, since the admin always sees (R12). In a team season, submit a card stores the player's team's team card in a shared-ball round and the player's own card in an own-ball one (R15), each only when access.py accepts it.

## S14a Services for admin: set up a season

Modules: `services/setup.py` (new), `store/schema.py` and the `s11` migration for a round's window, `store/save.py` for the window and the writes that replace a stored tee, seed index or link token, and `store/load.py` for a tee and the rounds on it. Use cases: create a player with a fresh link token, replace a player's link token, create a tee, change a tee, create a season with its mode, index rule, standings rule, seed indexes, provisional flags and season teams in one transaction, correct a seed index, and create a round as a draft with its window. A tee changes only while no card or team card is on it (R14), and in a team season a seed index can be corrected while no round is closed (R15), each as `access.py` answers. A season team naming a player with no seed index is refused. A season's teams and rules do not change once it is created.
Accept: each use case tested against a temporary database. A tee with a card or a team card is not changed, and one whose only card is voided is. A tee's rounds are read from every season. The S9b and T3 seasons, created without rounds, load back equal. A team season's seed index is corrected while round one is open and refused once it closes, and an individual season's is corrected after. A created round is a draft that `load_season_facts` leaves out, and keeps its window. A replaced link token finds the player and the old one finds nobody. The use cases only create what R15 reads: a round with a format only in a team season, and no `late_until` in a team season. Every refusal stores nothing.

## S14b Services for admin: run a round

Modules: `services/run.py` (new) for opening, closing and reopening, `services/setup.py` for changing a draft round beside `create_round`, whose checks it reuses, `domain/access.py` for R14's duel pairings gate and R13's reopen, `store/save.py` for the writes that change a stored round, `store/load.py` for a round of one number in one state, and `store/schema.py` with the `s11` migration for the CHECK that ties a round's `state` to `closed_at`. Use cases: change a draft round, open, close and reopen a round. A round with a duel contest opens only once that contest's pairings are published, and a round's contest config and published pairings cannot change once it opens (R14). `reopen_round(engine, season_id, number)` is refused unless the round is closed and has no card or team card submitted after `closed_at`, and it sets the state to open and `closed_at` to null (R13, SPEC decision 7). Proposing and publishing pairings is S21.
Accept: as S13. A round that is not a draft neither changes nor opens, a round that is not open does not close, and closing records `closed_at` (R13). A duel round without published pairings does not open (R14). A round's format does not change once it has opened, so its cards stay the kind R15 reads. A closed round with only on-time cards reopens, a round with a late card does not, nor does an open or a draft round, and after a reopen the round is in no table until it closes again. The database refuses a closed round without `closed_at` and any other round with one. Every refusal stores nothing.

## S14c Services for admin: correct a round

Modules: `services/run.py`, and in `store/save.py` the writes that change a stored card or team card. Use cases: add a manual award, correct and void a card or a team card. The tests' hand-written `void` is replaced by the store's write, and by the `void_card` use case in the services tests.
Accept: as S13. The use cases only create what R15 reads: team cards only in a shared-ball round and players' cards only in an own-ball one. Carried from S10: a correction never gives a shared-ball round a card of a player's own.

## S15 to S17 Web

Adds dependencies: fastapi, uvicorn, jinja2, python-multipart, and httpx as a dev dependency for the test client. A route checks the link-token cookie and then calls one use case, apart from ARCHITECTURE's exception for a write whose screen shows its own errors. A use case that needs the time takes it as `now`, in naive UTC, from the one services function that reads the clock, which S15a adds. Templates contain no arithmetic. Mobile first. S15a: app, link-token cookie, the engine the app opens, with SQLite's foreign keys on as the test database has them, and the standings table on its Season and segment tabs with position, name and points. S15b: the rest of the standings screen: the viewer's row, counted cards, round totals with dropped ones marked, the gap to the place above, the best N line and each closed round's winners. First, with no other change in the same commit, the team branch moves from `domain/season.py` to a new `domain/team_rounds.py` (T3's open question). S15c: player home, with the link landing on it and the Home tab. S16a to S16c: card entry with 18 inputs and a confirm screen, and the round page, each in its own section below. S17: admin pages for everything in S14, drawn from `docs/design/`, where `admin-round.html` also carries a round's actions, and the use case that lists a round's counted cards and team cards with their ids, which correcting and voiding need because `SeasonView` carries no card id. A team season is served first, with section 7's team screens from decision 9; what only an individual season shows is S21.
Accept: route tests with the test client. The owner clicks through on a phone before the step's commit. S15a: a link sets the cookie, an unknown link and a replaced link's cookie are refused, and both golden seasons' tables show on a screen with their positions and points. S15b: both golden seasons show every row's counted cards, the viewer's row with its round totals, the dropped ones marked, and its gap to the place above, the best N line on a table with a `best_n`, and each closed round's winners with their total. A viewer from whom R12 hides a round does not see its winners, and reads the same table as everyone else. S15c: a link lands on home and both screens have the Home tab. A team season shows one block per open round, oldest first, with each format's line, each player's strokes or the team's, the card status and the count of teams with a score, and the season block once below them. T3 reads "No round is open right now." with the season block, and a viewer from whom R12 hides an open round still reads its count.

Parked for S17: the admin's error state, which S16c2's notice screen for players does not cover (the owner, after S16b).

Open question for S17: can a tee's numbers be corrected while it has no card from another season, so a mistyped rating can be fixed mid-season? The correction would rescore that season's rounds (D4). Today nothing can fix a wrong rating once a card exists, since the tee and the round's tee are both locked.

Open question for S17: should changing a tee, or setting up a round on one, be refused with ValueError when no stored tee has that course and tee name? Today `change_tee` changes nothing without a word, and `create_round` raises the database's error. The architect leans yes: refuse an unknown tee with a clear error, as a seed index correction already does.

Open question for S17: is a tee's course or tee name refused when empty, and is surrounding whitespace trimmed before a tee is stored? The architect leans yes: non-empty names on `Tee`, trimmed at the ends by the form, with case kept as Trackman lists it.

Open question for S17: what does the bay settings form do with a line that clashes with the bay screen's fixed blocks? Today a menu named "Players" shows as a second Players block after Game, a Game line named "Holes" or "Game type" shows below the fixed line of that name, and only a menu written exactly "Game" joins the Game block, so "game" becomes a block of its own. The architect leans no check: the glossary shows bay settings as written, the admin sees the screen they produce, and a refusal would be code for a mistake only the admin can make.

## S15b2 Standings round grid

The viewer's row shows every closed round in round order as a grid, each cell under its round number, with the round total. A dropped round is marked, and a round without a round total shows "–". `RoundTotal` regains its round number. The gap to the place above becomes the difference between the two rows' points as shown, so 16.0 and 9.3 give "6.7 to 1st".
Accept: T3's gold row reads – 2.5 2.3 1.5 3.0 under R1 to R5, a dropped round is marked, and gold's gap reads 6.7.

## S15d1 A tee's course and name

A tee gains its course and name, which together identify it (SPEC glossary and section 4), and the separate tee id is deleted. Modules: `domain/facts.py`, `domain/results.py`, `domain/home.py`, `store/schema.py`, the `s11` migration, `store/load.py`, `store/save.py`, `services/setup.py`, `web/templates/home.html`. A caller holding a tee passes the `Tee`, and a caller that only names one passes its course and tee name. Home heads a round with its course, then its tee and close, as drawn.
Accept: one course with two tees reads "White tee" on one round and "Blue tee" on another. `load_tee`, `update_tee` and `load_rounds_on_tee` each leave alone a tee sharing the course and a tee sharing the name. A second tee of one course and name, and a round on a tee nobody stored, are refused by the keys. A reference round on a tee of another name with the same numbers is an error (R7).

## S15d2 Set up the bay

Section 7's Set up the bay screen, linked from each open round block on home. A season gains its bay settings (SPEC glossary), written through the setup use case until S17. Modules: `domain/facts.py`, `domain/results.py`, `domain/bay.py` (new), `store/schema.py`, the `s11` migration, `store/load.py`, `store/save.py`, `services/setup.py`, `services/play.py`, `web/app.py`, `web/templates/bay.html` (new), `web/templates/formats.html` (new), `web/templates/home.html`. Every game type is Stroke (Gross), so Trackman applies no handicap, cards are gross and the app applies the strokes. The demo season carries the owner's settings. Game: Pins Medium; Mulligans "Always. Only for an obvious technical fault, such as a shot the sim misread or didn't pick up."; Putting "Auto, Fixed". Course: Wind Off; Fairway firmness Medium; Green firmness Medium; Green stimp 9.
Accept: an own-ball round's screen reads "Individual, Stroke (Gross)" and "Holes: All" first under Game, then the season's Game lines; a shared-ball round's reads "Add both of you to one team." and its format's game type; the Course block lists the season's lines in the order written; and Players shows the round's tee name apart from its course.

## S16a Card entry

First, with no other change in the same commit: `HomePlayer`, `HomeTeam`, `HomeRound` and `HomeView` move from `domain/results.py` to `domain/home.py`, and `BayMenu` and `BayRound` to `domain/bay.py`, because `results.py` has 293 lines (S15d2's proposal). Every module and test that imports a moved name changes that import only, and the suite stays green with no expected value changed. Then modules: `domain/facts.py`, `domain/entry.py` (new), `services/play.py`, `web/app.py`, `web/templates/submit-confirm.html` (new), `web/templates/home.html`, `web/static/app.css` with `docs/design/tokens.css` for a disabled button, and python-multipart, which Starlette needs to read a form. Section 7's Check the card as typed entry in a team season, on one screen: home's Register card, while the round takes the viewer's card, opens it with 18 empty inputs, each with its hole and par, under the round's course, tee name and par. Typing a score of 2 to 9 moves to the next hole, and a 1 waits for a second digit. Check the card shows the same screen with the scores as typed, editable, and again after a hole is changed. A hole that is empty, not a whole number or outside 1 to 19 is outlined and named on the warn line, and with none the screen shows out, in and total and enables Submit card, which any edit disables until the card is checked again. Submit card hands the card in through `submit_card` (R13, R15) and lands on home, and with a hole in error shows the screen with its errors and stores nothing. R13's bound of 1 to 19 is `Card`'s, in `facts.py` beside the par bounds, and the screen reads it from there. The screen's one script only moves focus and disables Submit card, so the server judges every card as if no script ran.
Accept: home offers Register card on an open round whose card the viewer has not handed in, and not once it is in, in an individual season or to a viewer outside the season. The screen has 18 inputs named h1 to h18, each labelled with its hole and par. The design's card reads back as Out 41, In 40 and Total 81 with every score in hole order, and a changed hole checked again reads its new totals. A check with hole 5 empty outlines hole 5 alone and reads "Looks like an error on hole 5.", one with 20 on hole 5 and a non-number on hole 12 reads "Looks like an error on holes 5 and 12.", and neither shows out, in or total. A score of 19 checks clean, and `Card` refuses 0 and 20 and takes 1 and 19. Submit card is disabled on the empty screen and after a check with an error, and enabled after a clean one. A submitted card is stored with its scores in hole order and reads "Card in" on home, and in a shared-ball round it is the team's card and reads "Card in" on the partner's home. A submit with a hole in error shows the screen with that hole outlined, and a second card and a round that does not take the card are refused with the domain's message. Each stores nothing.
Not in this step: Register a card's photo screen, the players found, and the holes hard to read with their warn line (S19), and card entry in an individual season (S21).

## S16b Round before playing

Section 7's Round before playing at `/rounds/{number}`, in a team season, for a viewer from whom R12 hides the round: the round's number and close, per team "Score in", "1 of 2 cards" or "Not yet", the count of teams with a score, and Register card, which opens S16a's screen. Who holds which card is read from the season's facts, since `SeasonView` carries no cards (S13). A viewer who sees the round reads its result from S16c, and until then the route answers them "No such round." Modules: `domain/locked.py` (new), `services/play.py`, `web/app.py`, `web/templates/round-locked.html` (new).
Accept: on `t3_open`, hal reads round 1 with red, blue and green "Score in" and gold "1 of 2 cards", and cam reads round 3 with blue "Not yet" and the other three "Score in", each with 3 of 4 teams with a score. An own-ball team with neither card reads "Not yet". A viewer whose card, or whose team's team card, is in reads "No such round.", and a viewer outside the season reads the rows without Register card.
Settled at S16b's plan: a shared-ball team with its team card reads "Score in", as section 7 says, and the design's comment now agrees. A team is shown by its id, which is its name (section 4). The design's pairs of player names are sample names an admin could give, as the Team name input in `admin-season.html` shows. The teams are listed in team id order, and the line "Scores stay hidden until your card is in" shows only beside Register card, so a viewer outside the season does not read it (the owner, at S16b's plan).

## S16c1 Round result

Section 7's round result for a team season at `/rounds/{number}`, for a viewer who sees the round (R12), in place of S16b's "No such round.", and Submit card landing on the round page instead of home, since a viewer whose card is in reads the round as its result. Modules: `domain/round_result.py` (new), `domain/results.py` for `SeasonView`'s round of one number, which `domain/home.py` and `domain/locked.py` then read in place of their own lookups (S16b's open question), `domain/standings.py` for a competitor's round total in one round, which an open round's result needs and no table holds, `services/play.py`, `web/app.py`, `web/templates/round-result.html` (new). The page's nav is Home and Standings, as on Round before playing, until S16c2 adds the Round tab, so until then a closed round's result is opened by its URL.
Accept: on T3, gus reads round 5 as gold in Foursome with team net 64, one row "Team" with 79 gross and 13 strokes, gold 64, green 65, blue 66 and red 66 ranked, "3 of 3" teams beaten, 3.0 points, and 3rd → 2nd with "6.7 to 1st". hal reads round 2 as team net 141 from gus's 74 and his own 67, with his row, 87 gross and 18 strokes, before gus's, 82 and 8, red 140, blue 141, gold 141 and green 142 ranked, "1.5 of 3", 2.5 points, and 4th → 4th with "0.3 to 3rd". ann reads round 2 with 7.0 points and 2nd → 1st with no gap, and round 5 with 0.5 points, since a manual award is no contest award (R10). Round 4 ranks red, gold and blue and names green, whose team card is late, as without a score. gus reads closed round 1 with gold without a score and "4th" with "0.8 to 2nd". On `t3_open`, ann reads open round 3 as red 70 net, "1.5 of 2" and 2.3 points, with no change in position. A viewer outside the season reads closed round 1's ranking and the team without a score, with no team block and no points. A viewer from whom R12 hides the round still reads Round before playing, an absent round and an individual season's round read "No such round.", and Submit card lands on `/rounds/{number}`.
Settled at S16c1's plan (the owner): a combined round's team net is the two players' nets, each hole capped at net double bogey, summed, so T3's gold reads 141 in round 2. An open round shows its round total with no change in position and no gap. For a closed round the position before is the season table over the closed rounds numbered below it, and the position after is that table with the round added; with no closed round below it, only the position after shows, as "4th", since a tie at 0 points says nothing. "See all cards" is parked under S20, to be designed first. A bar is the share of the other teams with a score that its team beats, a tie counting half, as a whole percent rounded half up. A team without a score reads "No score this round." in place of its net, a player or team without a card reads "No card" before the strokes, and teams without a score are named in team id order as "blue and gold have no score this round."

## S16c2 Getting around and notices

Every refusal a player can meet shows one shared notice screen in place of a plain-text response, in the app's style, with a short message and a Home button: "No such round." becomes "That round isn't open.", and a visit without a valid link cookie reads "Open your personal link from the group chat." A hole in error on Check the card stays on the card screen, and Submit card's other refusals, such as a second card, show on the notice screen in the domain's own words. The card screen's script also disables Submit card once it is pressed, so a double tap cannot send a second card and land on a refusal after the first was saved (the owner, after S16b). Every player page is reachable by tapping from home: each open round's card on home links to its round page at `/rounds/{number}`, which shows Round before playing or the round result, and the Round tab on every player screen opens the oldest open round, or the latest closed round when none is open. S16b's round page and S16c1's round result get their phone click-through in this step, under run-step's click-through rule (the owner, after S16b).

## S18 Deploy and backup

One Dockerfile, SQLite on a persistent volume in an EU region, nightly copy of the database file off the machine, a one-page runbook. The link-token cookie gains `Secure` here, once TLS is settled. The runbook names `LEAGUE_DATABASE` and `LEAGUE_SEASON`. The image carries the system time zone database, which `zoneinfo` reads for the screens' local time. The hosting choice is made at the start of this step and recorded in DECISIONS.md.

## S19 Extract

Adds dependency: anthropic. `extract.read_card(image_bytes) -> DraftCard` with per-hole scores and, when visible, pars and stroke indexes. The player always confirms or corrects the draft before it becomes a card. Sim names: their table, adding them to a player, R14's one-or-more, and whether two players may share one. Before this step the owner collects 20 real screenshots as the test set, and the step starts by measuring accuracy on them. The Trackman app's scorecard shows 8 holes a row, so holes 9 and 18 sit off-screen: the test set is taken the way players will take it, and the step settles whether a card needs two screenshots. The bay's final scorecard shows all 18 holes on one screen.

## S20 Share

A round recap as text and one result image per round for the group chat. Format decided at the start of the step. Also the round's cards and team cards under R12, which section 7's round result links to as "See all cards", designed in `docs/design/` first (the owner, at S16c1's plan).

## S21 Individual season

The use cases and screens only an individual season needs: proposing and publishing pairings, the pairings screen, and the duel, virtual side and teambonus blocks of home and the round result, and card entry, the round page and the Round tab in an individual season. The domain for them exists from S4 to S9b. A round result that marks a late card's award, names the position a field award was for, or names the team a bonus went to needs a field no rule reads yet (S4, S5 and S6).
