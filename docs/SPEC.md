# Specification

Owner: Daniel. This file defines what the system does. How the code is organised is in ARCHITECTURE.md, the order of work is in BUILD_PLAN.md, why the league is shaped this way is in LEAGUE_DESIGN.md. Rule ids (R1, R2, ...) are stable. Code, tests and step reports refer to them.

## 1. Purpose

Run a private golf league for 8 to 30 players of mixed ability who play a season on Trackman simulators at commercial centres. Each round has a window. Players play when they want and with whoever they want, submit their own 18-hole card, or one card per team in a team season's shared-ball round, and the system works out everything else. The admin configures the season and never computes anything by hand.

Users: players (submit a card, see rounds and standings) and one admin (sets up seasons and rounds, publishes pairings, closes rounds, corrects mistakes). Players are identified by a personal secret link. There are no passwords and no sign-up.

## 2. Scope

In version 1: seasons, rounds with windows, hole-by-hole cards entered by the player, league handicap index, contests of kind duel, field, allplay and teambonus on holes, total or stableford basis, best ball sides, virtual sides for missing opponents and catch-up, manual awards for side contests and adjustments, multipliers, standings with best N and segments, Swiss and team pairing proposals, visibility rule, admin corrections. A season is individual or team (R15). A team season has fixed two-player teams, scored by field and allplay on best ball, combined, scramble, foursome and greensome formats.

After version 1, each as its own step: reading a card from a Trackman app screenshot, shareable result images, boxes with promotion and relegation, knockout resolved from cards, season team table, joker rounds, finals day starting strokes.

Never: vendor API integrations, shared-ball formats in an individual season (there every player plays their own ball and hands in a full card), 9-hole cards, money handling, chat, video or other verification machinery, accounts with passwords, outdoor GPS features.

## 3. Glossary

One name per concept. Code uses exactly these names.

| Term | Meaning |
|---|---|
| player | A person in the league. |
| sim name | What a simulator scorecard calls a player, such as KEDAGSVIK. A player can have several. Matching ignores case. |
| link token | The secret in a player's personal link. It identifies them and can be replaced. |
| admin | The one person who runs the league. |
| season | One league season with its rules and rounds. |
| round | One numbered unit of play in a season, on one tee, with a window. |
| window | The planned time from `opens_at` to `closes_at`. Informational. What counts is the round's state and `closed_at`. |
| tee | A course and tee: 18 pars, 18 stroke indexes, course rating and slope. Rating and slope are typed in by the admin from the Trackman app after playing the course once. Par and stroke index can be read from a card photo. |
| card | One player's 18 gross hole scores for one round, with an id and `submitted_at`. The id is unique within a season and settles the order when two cards share a timestamp (R6, R13). |
| counted card | A card that has not been voided. The domain never receives voided cards. |
| on-time card | A counted card with `submitted_at` at or before the round's `closed_at`, or any counted card while the round is still open. |
| late card | A counted card submitted after `closed_at` and at or before `late_until`. |
| index | The player's league handicap index, one decimal. Not a WHS index. |
| seed index | The index a player starts a season with. A fact set by the admin. |
| course handicap | A player's R1 bracket on a tee, before the allowance and before rounding, kept exact (R16). |
| playing handicap | Whole strokes a player receives on a tee in a contest (R1). |
| team playing handicap | Whole strokes a shared-ball team receives on its team card (R16). |
| net card | 18 net hole scores: gross minus allocated strokes (R3). |
| side | What is compared in a duel: a net card, and the players who earn what it wins. One player, a best ball of several, or a virtual side, which has no players because nobody earns its points (R7). |
| contest | One scoring job on a round, described by config. A round has one or more. |
| pairing | One or two sides that meet in a duel contest. A side is a list of players. |
| season team | A named group of players for the whole season. In an individual season teambonus reads it. In a team season every team has exactly two players and competes as one (R15). |
| season mode | `individual` or `team`, one per season (R15). |
| competitor | Who earns awards and has a row in the standings: the player in an individual season, the team in a team season. |
| format | How a team's score for a round is made in a team season (R17): `bestball` or `combined`, which are own-ball, or `scramble`, `foursome` or `greensome`, which are shared-ball. |
| team card | One team's 18 gross hole scores for a shared-ball round, played together on one ball, with an id and `submitted_at`. |
| award | Points given to one player in one round by one contest or by the admin, with a reason: `win`, `draw` or `loss` in a duel, `position` in a field contest, `record` in an allplay contest, `bonus` in a teambonus, `manual` for an admin's award. |
| standings | The season table computed from awards (R10). |
| fact | Something entered by a person and stored. |
| derived value | Anything computed from facts. Never stored. |

## 4. Facts and derived values

Facts: players with their sim names and link token, tees, seasons with their mode, index rule and standings rule, each player's seed index and provisional flag per season, season teams, rounds with contest config, a team season's format, state, `closed_at` and `late_until`, published pairings, cards, team cards, manual awards.

Derived, always recomputed from facts by one pipeline: indexes, playing handicaps, team playing handicaps, net cards, team scores, sides, contest results, awards, standings, what a viewer may see.

A full season is about 300 cards. Recomputing everything on every request is cheap. Nothing derived is saved, cached or repaired.

## 5. Rules

**Arithmetic.** Rounding is half up: `floor(x + 0.5)`, never Python's `round`, which rounds a half to even. Every value that gets rounded is computed exactly first (`fractions.Fraction` or integers), never with floats. Exact arithmetic is not here because floats have been shown to give a wrong handicap; a sweep of R1 found no such input. It is here so the question does not have to be asked again at each new rule. Shares, rates and allowances are stored as whole percents (70, not 0.7). One-decimal values (index, course rating, differential) are held in tenths as integers.

**R1 Playing handicap.** `H = round((index * slope / 113 + course_rating - par_total) * allowance / 100)`. `allowance` comes from the contest config, default 100.
Example: index 18.4, slope 131, rating 73.2, par 72. Raw 22.53. Allowance 100 gives 23. Allowance 90 gives 20.

**R2 Stroke allocation.** For `H >= 0`: every hole gets `H // 18` strokes, and holes with stroke index `<= H % 18` get one more. For `H < 0`: holes with stroke index `> 18 + H` get minus one. `H < -18` is an error.
Examples: H 5 gives 1 on stroke index 1 to 5. H 20 gives 2 on stroke index 1 and 2, and 1 elsewhere. H 40 gives 3 on stroke index 1 to 4, and 2 elsewhere. H -2 gives -1 on stroke index 17 and 18.

**R3 Net card.** `net[h] = gross[h] - strokes[h]`. Net total is the sum. Stableford points on a hole are `max(0, 2 + par[h] - net[h])`. Every player plays off their own full playing handicap against the card. Duels compare net cards. There is no pairwise "difference" allocation (decision D3).
Example: par 4, stroke index 3, H 20 gives 1 stroke. Gross 6 is net 5, which is 1 stableford point.

**R4 Differential.** Cap each gross hole at `par[h] + 2 + strokes[h]`, with strokes from R2 at allowance 100. `differential = (capped_total - course_rating) * 113 / slope`, to one decimal.
Example: capped total 95, rating 73.2, slope 131 gives 18.8.

**R5 Index update.** `new = old + rate / 100 * (differential - old)`, to one decimal, clamped to -5.0 to 54.0. `rate` is `early_rate` when the player is provisional and has fewer than `early_cards` counted cards in this season before this one. Otherwise it is `rate_down` when the differential is below the old index, else `rate_up`. The three rates are whole percents from 0 to 100 and `early_cards` is 0 or more; anything else is an error. Proposed defaults, to be confirmed by the owner: new players seeded at 70 percent of outdoor handicap and marked provisional, `early_rate` 70, `early_cards` 3, `rate_down` 50, `rate_up` 30.
Examples with old 18.4, not provisional: differential 14.2 gives 16.3. Differential 25.0 gives 20.4.

**R6 Index timing.** The index used for a card is the seed index replayed through all of that player's earlier counted cards in the season, ordered by `submitted_at`, and by card id when two cards share a timestamp. Every counted card updates the index, whatever the contest. A card's index never changes after submission, unless the admin voids or corrects an earlier card.

**R7 Sides.** Net cards for a contest use that contest's allowance.
- `single`: one net card.
- `bestball`: per hole the lowest net score among the members' on-time net cards. Members without an on-time card are left out. A side with no on-time card is **missing**.
- `virtual`: a synthetic net card. Take the on-time cards of the contest's `reference_rounds` (default: this round), excluding cards of the players on the side it will meet. Reference rounds must be distinct rounds of the season, none later than this round, and use this round's tee, else it is an error. Keep the `virtual_n` best by net total (default 4, all if fewer, earlier `submitted_at` wins a tie for the last place, and the lower card id when those are equal). Per hole take the mean of their net scores, rounded. If no card is left the virtual side is net par on every hole.
Example: hole net scores 4, 5, 5, 6 give 5. Scores 4, 4, 5, 5 give 4.5, rounded to 5.

**R8 Compare.** Two sides are compared on one basis. `holes`: the lower net score wins the hole, the side with more holes won wins, margin is holes up after 18. `total`: lower net total wins, margin in strokes. `stableford`: more points wins, margin in points. Equal is a draw.
Example on holes: A wins 7 holes, B wins 5, 6 halved. A wins, 2 up.

**R9 Contests.** Every contest has `key` (unique in the round), `kind` and `multiplier` (default 1, applied to every award of the contest). A contest that reads cards also has `basis` and `allowance`, a whole percent from 0 to 100 with default 100, where 0 plays the contest off gross; anything else is an error. A contest turns cards, or the awards of another contest, into awards.
- `duel`: fields `side` (single or bestball, no default), `points_win`, `points_draw`, `points_loss`, `virtual_n` (1 or more, default 4), `reference_rounds`. Anything else for `side` or `virtual_n` is an error. A pairing has one or two sides, never none, and under `side` single each of its sides names exactly one player. Needs pairings, and a duel with none is an error. Each pairing is compared under R8. Members of a side who have an on-time card get that side's points. A side that is missing, or absent because the pairing has one side, is replaced by the virtual side for its opponent. A card from a player who has no award in this contest meets the virtual side alone as a single side, and earns points from that, whether the card came in late or the player was in no pairing when the round opened. It is an award that decides this, not a points total: a player who lost a pairing has an award, even where `points_loss` is 0, and is not swept a second time. It never changes anyone else's award. If both sides are missing, each such card is handled that way separately.
- `field`: basis total or stableford. On-time single sides are ranked and awarded from `position_points`. Tied players share the mean of their positions' points. Positions beyond the list score 0.
- `allplay`: every on-time single side is compared under R8 with every other. `points = scale * (wins + 0.5 * draws) / (n - 1)`. With one card, no award. Example: 5 cards, a player wins 2, draws 1, loses 1. Scale 2 gives 1.25.
- `teambonus`: field `source` names a duel contest of the same round. Sum that contest's awards from on-time cards per season team. Each member with an on-time card of the team with the highest sum gets `bonus`. Teams level at the top share one `bonus` equally, so two tied teams get half each and three get a third each. A team with no on-time card has no sum and does not enter the ranking, so it cannot dilute the share of a team that played. A team that played but earned nothing in the source contest does have a sum, of zero, and enters. Players without a season team are ignored. A teambonus has no `basis` and no `allowance`.
- Manual awards (longest drive, closest to pin, hole in one, adjustment) are facts with a player, a round, points and a key the admin writes, such as `longest-drive`. The key is a label, not an identifier: several manual awards in a round may share one, as an adjustment given to two players would. They are added to the awards as they are, without a multiplier. A manual award names a competitor of the season, a seeded player or, in a team season, a team; anything else is an error.
Late cards score only in duel contests in version 1.

**R10 Standings.** Every player with a seed index for the season has a row in every table, with 0 points until they play. A player's round total is the sum of their awards from contests in that round. Season points are the sum of their round totals over closed rounds, or of their best `best_n` round totals when set, chosen only from closed rounds in which they hold an award from a contest, so a round they did not score in is never a zero that displaces a worse one. Every manual award in one of the table's closed rounds is then added in full, whether or not the player scored in that round: best N forgives rounds of golf, never a penalty or a longest drive. `segments` are named, inclusive round ranges, each with its own optional `best_n`, computed by the same rule over those rounds. Every `best_n` is 1 or more, a segment's first round is 1 or more and its last no earlier than its first, and segment names are unique in the season; anything else is an error. Order: points. Players level on points share the position, and the position after a shared one is skipped, as on a golf leaderboard. The rows of a shared position carry no order of merit between them. A closed round's winner is the player with the lowest net total among its on-time cards, netted at full playing handicap with no contest allowance, and every player level on that total on a tie. A round with no on-time card has no winner. Winning a round earns no points.

**R11 Pairing proposals.** A pure function proposes pairings and the admin may edit them. Publishing makes them facts. Two players have met when they were on opposite sides of a published duel pairing this season.
- `swiss`: order by season standings as R10 orders them, then index ascending, then player id, so a shared position is broken by index and round 1, where everyone is level, is ordered by index. From the top, pair each player with the highest-ranked unpaired player they have not met. When every unpaired player has been met, take the one met least recently, and of those last met in the same round, as both players of a best ball side were, the highest-ranked. With an odd number, the single-sided pairing is settled first: it goes to the lowest-ranked player among those with the fewest published single-sided pairings this season, so it rotates and starts again from the bottom once everyone has had one. The rest are then paired from the top. Only published single-sided pairings count: a player who met the virtual side because their card was late or because they were in no pairing (R9) has not had one.
- `teams`: players are ranked as for swiss. `high_low` joins the highest-ranked with the lowest-ranked, and so on inward, and with an odd number the middle player forms a one-member side. `random` shuffles the ranked order with an `rng_seed` passed in and takes consecutive pairs, and with an odd number the last player of the shuffle forms a one-member side. Sides are then paired from the top by combined points, sides level on points ordered by their highest-ranked member, without regard to who has met, since sides are new each round. With an odd number of sides, the single-sided pairing goes to the one-member side when there is one, so two-player sides meet each other and the lone player meets a single virtual card rather than a best ball of two, and otherwise to the lowest-ranked side.
Pairings across season teams for a teambonus round are made by hand in version 1.

**R12 Visibility.** A player sees other players' cards and any result of a round only after their own counted card for that round is in, or once the round can accept no more cards, which is when it is closed and `late_until` is unset or past. Until then a player without a card sees only who has one, so a late card is never played against a virtual side the player has been shown. The admin always sees everything. Standings show closed rounds only, the same for every viewer, a closed round still taking late cards included.

**R13 Round lifecycle and cards.** States: draft, open, closed. The admin opens and closes. Closing records `closed_at`. A card is accepted when the round is open, or when it is closed, `late_until` is set and the time is at or before it. One counted card per player per round. A card is accepted only from a player with a seed index for the season. A second submission is rejected. The admin can correct the hole scores of a card, which keeps its `submitted_at`, or void it, after which a new one is accepted under the same rule. A card has 18 whole-number scores of 1 or more, and so does a team card. A picked-up hole is entered as the score the simulator recorded. A tee has 18 pars of 3 to 6 and the stroke indexes 1 to 18 once each. A card's id is unique within a season, and so is a round's number.

**R14 Setup and locking.** A tee cannot be changed once a card exists on it, so old rounds keep the numbers they were scored with. Add a new tee instead. A round with a duel contest opens only once that contest's pairings are published. A round's contest config and published pairings lock when the round opens; changing them afterwards needs a deliberate reopen by the admin. A round can only use a tee that has a course rating and a slope; a tee created from a photo is a draft until the admin adds them, and a draft cannot be used by a round. A player has one or more sim names, and a card read from a photo is matched to a player by them. A name on a photographed card that matches no player is offered to the admin, who either links it to a player, adds a player, or ignores that row.

**R15 Team seasons.** A season's `mode` is `individual`, the default, or `team`. In a team season every seeded player belongs to exactly one season team, and every team has exactly two players; anything else is an error. The team is the competitor. R9 and R10 read team wherever they say player, so awards, round totals, standings rows and round winners belong to teams, every team has a row in every table, and a manual award names a team. A closed round's winners are the teams with the highest round total, every team level on it on a tie, in place of R10's lowest net total. Each round has a `format` (R17), and a round without one is an error. Its contests are field or allplay only, with no `allowance` of their own, since the format carries it (R16), so an allowance set on one is not read. A duel, a teambonus, pairings and virtual sides do not exist in a team season, and a contest of another kind is an error. Indexes do not move: every card and team card is played off the player's seed index, and R4 to R6 do not apply. A seed index can be corrected until round one closes and is locked after. In an own-ball round each player hands in their own card under R13. In a shared-ball round each team hands in one team card instead, under R13's acceptance rule, with one counted team card per team per round and no card of a player's own; under R12 its players see others' cards and results once their team's card is in. Late cards score in duels only (R9), so a team season scores none.

**R16 Team handicaps.** A player's course handicap is R1's bracket before the allowance and before rounding, `index * slope / 113 + course_rating - par_total`, kept exact. The format sets the allowances, each a whole percent from 0 to 100 with a default the round may override; anything else is an error.
- `bestball` and `combined`: each player plays off their own playing handicap, R1 at `allowance` (defaults 85 and 100).
- `scramble`: the team plays off `round(low / 100 * lower + high / 100 * higher)`, where lower and higher are the two players' course handicaps (defaults 35 and 15).
- `greensome`: as scramble (defaults 60 and 40).
- `foursome`: the team plays off `round(allowance / 100 * (a + b))` (default 50).
Strokes fall under R2, a team's on its team card.
Example: indexes 10.0 and 20.0 on a tee of slope 113 with rating equal to par give course handicaps 10 and 20. Best ball gives 9 and 17. Combined gives 10 and 20. Scramble gives 3.5 + 3 = 6.5, so 7. Greensome gives 6 + 8 = 14. Foursome gives 15.

**R17 Team scores.** A team's score for a round needs every card its format reads: both players' on-time cards in an own-ball round, the team's on-time team card in a shared-ball one. A team without them has no score and no award in the round.
- `bestball`: per hole the lower of the two players' net scores.
- `combined`: per hole the sum of the two players' net scores, and on stableford the sum of their points, never the points of the summed net.
- `scramble`, `foursome`, `greensome`: the team card netted at the team's playing handicap (R3).
Field and allplay rank and compare team scores as they do single sides (R8, R9).
Example: par 4, nets 3 and 7. Best ball scores 3. Combined scores 10, and on stableford 3 + 0 = 3 points.

## 6. Open decisions for the owner

Decisions 1 to 4 and 7 change rules, and under D4 a rule changed after round one rewrites every round already played, so they are due before round one. Decision 5 only names a winner once a table's last round has closed, so it is due before the first segment or season ends. Decision 6 is round config and only touches rounds not yet opened, but round one needs it. Decision 9 is due before S15.

1. R5 defaults: seed share, the three rates, and whether `rate_up` should be slower than `rate_down`. In a team season only the seed share matters, since indexes do not move (R15).
2. R3 and D3: net cards against full handicap, not the Rules of Golf difference method. Strokes can land on slightly different holes. Accept?
3. R7: virtual side from the best 4 on-time cards, rounded per hole, which differs slightly from last season's mean of the best 4 net totals. Not used in a team season.
4. R9: should late cards also score in field and allplay contests, by being placed against the frozen on-time field? In a team season this decides whether a late team scores at all. Settled for a team season: no late window; S14 offers no `late_until`.
5. R10: a shared first place. Every table shares positions on equal points, as on a golf leaderboard, and only a winner needs a single name. Decide how a first place still shared when the last round of a season or segment closes is separated: most cards played (rewards turning up and cannot be gained by sitting out, but under best N it pays the discard advantage twice), a playoff the group arranges, or joint winners. If a place other than first carries a prize, the same question applies at that boundary.
6. Which contests the 2026-27 season uses. Settled: a team season (R15), scored by allplay every round, with every round but one counting, so `best_n` is one less than the number of rounds. Open: the number of rounds, each round's format, and the allplay basis and scale.
7. R13 and R14: what a reopen is. R14 says changing locked config needs a deliberate reopen, but R13's states are draft, open and closed with no way back. Say which transitions exist and whether `closed_at` survives one: a closed round that loses or moves it turns late cards into on-time ones, which changes every sweep and virtual side in the round.
9. Section 7 for a team season: what home, the round result and the standings show for a team, a partner's card and a team card, and the design files for them in `docs/design/`.

## 7. Screens

`docs/design/` holds a static HTML reference for every screen, plus `tokens.css`. Steps S15 to S17 build the Jinja templates from those files and follow their layout, class names and wording rather than inventing new ones. `docs/design/README.md` has the rules. This table says what each screen reads in an individual season. A team season's screens are decision 9.

| Screen | File | Reads |
|---|---|---|
| Player home | `home.html` | The current round: number, tee, `closes_at`, time left. The viewer's pairing in each duel contest, with both indexes and the stroke difference. A viewer who meets the virtual side, through a single-sided pairing or by being in no pairing, sees that they play the virtual side: the best `virtual_n` on-time net cards, built when the round closes, with no index or stroke difference. Season position, points, and the gap to the place above. How many players have a counted card. |
| Register a card | `submit-photo.html` | Round identity only. |
| Check the card | `submit-confirm.html` | The draft card: the tee matched or proposed, every player found with their sim name and total, 18 gross scores each with a confidence flag, out, in and total. |
| Round before playing | `round-locked.html` | Round number, `closes_at`, and per player whether a counted card exists. Nothing else, by R12. |
| Round result | `round-result.html` | The viewer's gross, playing handicap and net. One block per contest, in config order. Per duel contest: the comparison, the margin, the award and the 18 hole outcomes. Per allplay contest: wins, draws, losses, the award and the field ranked by net. Per field contest: the viewer's position, the award and the field ranked by the contest's basis. Per teambonus contest, shown only to a viewer with a season team: the winning team or teams, and the bonus if the viewer holds it. The round total, which is contest awards only as R10 defines it, so it matches the round total on the standings, and the change in position. Below the total, each manual award with its key and points, marked as added to the season in full. |
| Standings | `standings.html` | Season and each segment: position, name, counted cards, points. For the viewer, the round totals with dropped ones marked and the gap to the place above. Each closed round's winner under R10, or winners on a tie, with their net total. |
| Season setup | `admin-season.html` | Season name and round count, the index rule, the standings rule with its segments, every player with outdoor handicap, seed index and provisional flag, and the season teams. |
| Round and formats | `admin-round.html` | The round's tee, window and `late_until`, each contest's config, the preset list, a worked example of what the round is worth, and whether the round is locked. |
| Pairings | `admin-pairings.html` | Proposed or published pairings with each player's standings position, a flag on a rematch, and the single-sided pairing. |
| Add a player | `admin-player.html` | The player form, the link token, the sim names, and the existing roster with whether each link has been opened. |
| Add a course and tee | `admin-tee.html` | Course, tee, rating, slope, 18 pars and stroke indexes, the stroke-index check, and whether the tee is still a draft. |
