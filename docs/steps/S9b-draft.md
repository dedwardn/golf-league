# S9b draft

Draft for S9b. Fold into `docs/steps/S9b.md` and delete in the S9b commit.

This is not a step report. It is the part of the S9 plan that exists nowhere else, saved
before the session that produced it was cleared. Sections 1 to 3 are verbatim from that
plan and are superseded wherever section 4 says so. Section 5 lists the arithmetic the
S9b plan must redo before any code.

## 1. Public API, verbatim from the S9 plan

```python
# facts.py
@dataclass(frozen=True)
class RoundFacts:
    number: int
    tee: Tee
    contests: tuple[ContestConfig, ...]
    cards: Mapping[str, Card]  # player id -> their one counted card (R13)
    pairings: Mapping[str, tuple[Pairing, ...]]  # duel contest key -> its published pairings
    manual: tuple[ManualAward, ...]
    closed_at: datetime | None
```

One round as the pipeline reads it. `ValueError` when a contest key repeats (R9: `key`
unique in the round) or when `pairings` names a key the round has no contest for.

```python
# facts.py
@dataclass(frozen=True)
class SeasonFacts:
    rounds: tuple[RoundFacts, ...]
    seed_index_tenths: Mapping[str, int]
    provisional: frozenset[str]
    index_rule: IndexRule
    standings_rule: StandingsRule
    teams: Mapping[str, str]  # player id -> season team
```

One season's facts. `ValueError` when a round number repeats.

```python
# facts.py
ContestConfig = DuelConfig | FieldConfig | AllplayConfig | TeamBonusConfig
```

Added to each config: `kind: Literal["duel"] = "duel"` and siblings, the discriminator the
pipeline dispatches on; `allowance: int = 100` on `DuelConfig`, `FieldConfig` and
`AllplayConfig` but not `TeamBonusConfig`; `reference_rounds: tuple[int, ...] = ()` on
`DuelConfig`, empty meaning this round (R7's default).

```python
# results.py
@dataclass(frozen=True)
class RoundView:
    awards: RoundAwards
    winners: tuple[str, ...]
```

One round as a screen reads it. `awards` already carries the round number, so nothing is
repeated. `winners` is empty for a round that is not closed.

```python
# results.py
@dataclass(frozen=True)
class SegmentView:
    name: str
    rows: tuple[StandingsRow, ...]


@dataclass(frozen=True)
class SeasonView:
    rounds: tuple[RoundView, ...]
    standings: tuple[StandingsRow, ...]
    segments: tuple[SegmentView, ...]
```

```python
# season.py
def compute_season(facts: SeasonFacts) -> SeasonView
```

Every round's awards and winners, the season table and each segment's table, from facts
alone. `ValueError` for a reference round on another tee (R7) and for a teambonus whose
`source` names no contest of its round (R9).

## 2. The fixture, verbatim from the S9 plan

`tests/domain/fixtures/season.py`. Agreed before coding, per BUILD_PLAN. Every number
below is hand-computed; the design exists to make that cheap.

**Tee A** — `pars = (4,4,3,5, 4,4,3,5, 4,4,3,5, 4,4,3,5, 4,4)`, par 72;
`stroke_indexes = (1, 2, 3, …, 18)`, so stroke index equals hole number and a playing
handicap of *p* puts one stroke on holes 1 to *p*; `course_rating_tenths = 720`,
`slope = 113`.

Two consequences make the whole fixture checkable in one pass. Because the rating equals
par and the slope is 113, `playing_handicap = round_half_up(allowance × index_tenths /
1000)`, so at allowance 100 the playing handicap is just the index. And
`differential_tenths = 10 × (capped_total − 72)`.

**Tee B** — Tee A with `slope = 120`. Used only by the reference-round error test, never
by the golden season.

**Players, seed indexes, index rule.** Six players, nobody provisional,
`IndexRule(early_rate=70, early_cards=3, rate_down=50, rate_up=30)` — the early rate never
fires because `provisional` is empty.

| | ann | bob | cam | dee | eve | fay |
|---|---|---|---|---|---|---|
| seed index (tenths) | 0 | 40 | 80 | 120 | 160 | 180 |
| season team | east | east | east | west | west | west |

**Cards.** Every card is par on every hole except the holes listed, each of those one
over. No cap ever bites, so a card's differential is `10 × (gross − 72)`.

| gross (deviating holes) | R1 | R2 | R3 | R4 |
|---|---|---|---|---|
| ann | 72 (none) | 72 (none) | 72 (none) | 72 (none) |
| bob | 76 (15–18) | 76 (15–18) | 75 (16–18) | 76 (15–18) |
| cam | 78 (13–18) | 79 (12–18) | 79 (12–18) | 79 (12–18) |
| dee | 84 (7–18) | 84 (7–18) *late* | 83 (8–18) | 84 (1–12) |
| eve | 88 (3–18) | 87 (4–18) | 88 (3–18) | 88 (3–18) |
| fay | 90 (1–18) | 90 (1–18) | 90 (1–18) | 88 (3–18) |

**Index replay.** A player whose gross equals par plus their playing handicap has a
differential equal to their own index, so their index does not move. Only the four
deviations below move one.

| index before (tenths) | R1 | R2 | R3 | R4 | playing handicap at 100 |
|---|---|---|---|---|---|
| ann | 0 | 0 | 0 | 0 | 0, 0, 0, 0 |
| bob | 40 | 40 | 40 | 35 | 4, 4, 4, 4 |
| cam | 80 | 70 | 70 | 70 | 8, 7, 7, 7 |
| dee | 120 | 120 | 120 | 115 | 12, 12, 12, 12 |
| eve | 160 | 160 | 155 | 157 | 16, 16, 16, 16 |
| fay | 180 | 180 | 180 | 180 | 18, 18, 18, 18 |

cam's round-1 78 gives differential 60 against an index of 80, so rate_down halves the gap
to 70 and **cam plays rounds 2 to 4 off 7, not 8**. That is what stops a pipeline passing
seed indexes straight through instead of calling `index_by_card_tenths`. bob's and dee's
round-3 and eve's round-2 moves are smaller and leave their playing handicaps unchanged.

**Net totals at allowance 100**, which is what the round winner reads:

| | R1 | R2 | R3 | R4 |
|---|---|---|---|---|
| ann | 72 | 72 | 72 | 72 |
| bob | 72 | 72 | **71** | 72 |
| cam | **70** | 72 | 72 | 72 |
| dee | 72 | 72 *(late)* | **71** | 72 |
| eve | 72 | **71** | 72 | 72 |
| fay | 72 | 72 | 72 | **70** |

**Round 1** — closed. `FieldConfig(key="field", basis="total", allowance=100,
position_points=(10, 6, 3, 1))`, and `ManualAward("eve", "longest-drive", 2)`.

cam is alone on 70, so takes `position_points[0:1]` = 10. The other five tie on 72 and
share `position_points[1:6]`, which is only `(6, 3, 1)` — a slice past the end scores the
missing places 0 — so 10 ÷ 5 = 2 each.

Awards: cam 10; ann, bob, dee, eve, fay 2 each; eve a further 2, reason `manual`.
Winner: **cam**.

**Round 2** — closed, dee's card late. `DuelConfig(key="duel", basis="stableford",
allowance=90, points_win=3, points_draw=1, points_loss=0, side="single", virtual_n=4)`,
pairings `ann|fay`, `bob|eve`, `cam|dee`.

Allowance 90 gives playing handicaps 0, 4, 6, 11, 14, 16 — cam drops from 7 to 6 and dee
from 12 to 11, which is the point: these entries cannot be the ones the winner was read
from. Stableford: ann 36, bob 36, cam 35, dee 35, eve 35, fay 34.

- ann 36 beats fay 34 → ann 3, fay 0.
- bob 36 beats eve 35 → bob 3, eve 0.
- cam meets a virtual side, dee's being missing. From ann 72, bob 72, eve 73, fay 74 at
  allowance 90, the per-hole means round to par on holes 1–14 and par+1 on 15–18: total
  76, stableford 32. cam 35 wins → cam 3.
- dee holds no award, so her late card meets the virtual side alone. Its pool excludes
  only dee, so the best four are ann 72, bob 72, cam 73, eve 73 — cam over eve on
  `submitted_at`. The means round to par−1 on holes 1–3, par on 4–14, par+1 on 15–18:
  total 73, stableford 35. **A draw** → dee 1.

Awards: ann 3, bob 3, cam 3, dee 1, eve 0, fay 0. Winner: **eve**.

**Round 3** — closed. `AllplayConfig(key="allplay", basis="total", allowance=100,
scale=2)`.

bob and dee are level on 71 and beat the four on 72: each 2 × (4 + ½) ÷ 5 = 9/5. Each of
the four loses twice and draws three times: 2 × 1½ ÷ 5 = 3/5.

Awards: bob 9/5, dee 9/5, ann 3/5, cam 3/5, eve 3/5, fay 3/5. Winners: **bob and dee** —
the round won on a tie.

**Round 4** — **open**, so its awards appear in no table and it has no winner.
`DuelConfig(key="bb", basis="total", allowance=100, side="bestball", virtual_n=4,
points_win=4, points_draw=2, points_loss=0, reference_rounds=(3,))`, then
`TeamBonusConfig(key="bonus", source="bb", bonus=3)`, and `ManualAward("dee", "bb", 20)`.

Pairings: `(ann,bob) | (dee,eve)` and `(cam,fay)` single-sided.

- Best ball (ann, bob) is 68, (dee, eve) is 70 → ann 4, bob 4, dee 0, eve 0.
- (cam, fay) is 65 and meets a virtual side built from **round 3**, excluding cam and fay:
  ann 72, bob 71, dee 71, eve 72, whose means give par−1 on holes 1–2, par on 3–15, par+1
  on 16–18, total 73. 65 wins → cam 4, fay 4.
- Teambonus: east 4 + 4 + 4 = 12, west 0 + 0 + 4 = 4. East wins → ann, bob, cam 3 each.

The manual award's key is `bb`, the duel's own key. Were manual awards passed to the
teambonus, west would hold 24 and take the bonus instead — which is the hazard BUILD_PLAN
names, made into a test that fails loudly.

**Standings.** `StandingsRule(best_n=2, segments=(Segment("first-half", 1, 2),))`. Rounds
1 to 3 are closed; round 4 is not.

Round totals from contest awards: ann 2, 3, 3/5 · bob 2, 3, 9/5 · cam 10, 3, 3/5 · dee 2,
1, 9/5 · eve 2, 0, 3/5 · fay 2, 0, 3/5. eve's and fay's round-2 zero is a real award — a
loss at `points_loss` 0 — so it is a candidate best N drops, not a round they missed.

| position | player | points |
|---|---|---|
| 1 | cam | 13 |
| 2 | ann | 5 |
| 2 | bob | 5 |
| 4 | eve | 23/5 |
| 5 | dee | 19/5 |
| 6 | fay | 13/5 |

eve's 2 is her round-1 longest drive, added in full outside best N. dee's 20 sits in round
4 and so reaches no table. Position 3 is skipped behind the shared second.

Segment `first-half`, rounds 1 and 2, no `best_n`: cam 13, ann 5, bob 5 shared second,
eve 4, dee 3, fay 2.

## 3. `test_season.py`, verbatim from the S9 plan

- `test_r9_the_golden_season_awards_every_round` — the four rounds' `RoundAwards` against
  the tables above.
- `test_r10_the_golden_season_standings` — the season table.
- `test_r10_the_golden_season_segment_table` — `first-half`.
- `test_r10_the_golden_season_round_winners` — cam; eve; bob and dee; none for the open
  round.
- `test_r10_an_open_round_scores_in_no_table` — round 4's awards are in its `RoundView`
  and in no row of either table.
- `test_r9_a_teambonus_sums_contest_awards_and_not_manual_ones` — the `bb`-keyed manual
  award leaves east winning.
- `test_r7_a_reference_round_on_another_tee_is_an_error`
- `test_r9_a_teambonus_source_that_names_no_contest_of_the_round_is_an_error`
- `test_r9_a_teambonus_runs_after_the_contest_its_source_names` — the teambonus listed
  before its source in `contests` still pays.

## 4. Rulings, which override sections 1 to 3

1. `SegmentView` is in, as section 1 has it. Segment tables are computed eagerly, one per
   `StandingsRule.segments` entry.
2. An open round has no winners, as section 1 has it.
3. `provisional` is a `frozenset[str]`, as section 1 has it.
4. R9 now bounds `allowance` as a whole percent from 0 to 100, where 0 plays the contest
   off gross; anything else is an error. `facts.py` enforces it on `DuelConfig`,
   `FieldConfig` and `AllplayConfig`. `TeamBonusConfig` has no allowance.
5. A teambonus `source` must name a **duel** contest of the round, not any contest. That
   is one check, not two, so it replaces the wording in section 1's `compute_season`
   contract and the test name in section 3.
6. A reference round that names no round of the season is an error (R7), alongside one on
   another tee.
7. **No** error for `pairings` naming a key the round has no contest for. Section 1's
   `RoundFacts` contract is wrong on that point. The repeated contest key error and
   `SeasonFacts`'s repeated round number error both stay.
8. `SeasonFacts` holds open and closed rounds only. A draft round has no cards, and R14
   now opens a round with a duel only once that contest's pairings are published, so a
   duel reaching `duel_awards` without pairings stays the error S6b made it. No round
   `state` field: `closed_at is None` is the whole distinction S9b needs.
9. A player's current index is S14's and S15's, not S9b's. `compute_season` returns no
   index.
10. A player without a seed index is a loud `KeyError`. No bound, no `ValueError`.

## 5. What the S9b plan must recompute before any code

The owner changed the fixture after section 2 was written. Section 2's numbers are stale
wherever these reach, and the S9b plan carries the recomputed tables for sign-off.

**(a) dee's late round-2 card becomes 83, one over on holes 8 to 18.** At her full
handicap of 12 that nets 71, level with eve, so a pipeline that lets a late card into the
round winner names two winners instead of one. That is the point of the change. The owner
gives the downstream as:

- dee beats the virtual side 36 to 35 and earns 3, not a draw of 1.
- Her index is 115 after round 2 and 113 after round 3, so she plays round 4 off 11, not
  12.
- Round 3 is unchanged.
- Round 4's best ball for dee and eve stays 70.
- dee ends on 5, sharing second with ann and bob in both tables.

Still to recompute: her round-2 net card hole by hole at allowance 90 and the stableford
36 that follows; whether the virtual side she meets still totals 73 and 35, since the pool
excludes only her and her own card is not in it; the full season and segment tables with
dee on 5, which moves eve and fay down a position each; and her round-4 net card off 11
rather than 12, which section 2's round-4 net totals do not reflect.

**(b) Round 4 gains a second card-reading contest** at an allowance that orders the
players differently from the duel — for example a field contest on total at allowance 50,
where ann leads instead of fay. This is what proves entries are built per contest and
never cached per round. To compute: every player's playing handicap at that allowance,
their net totals, the field positions and awards, and the effect on round 4's awards
tuple. It changes no table, round 4 being open.

**(c) A late card moving its player's index gets its own test** in `test_season.py`: dee's
round-2 card is late, yet R6 replays it like any counted card, so her round-4 playing
handicap is 11. A pipeline that fed only on-time cards to `index_by_card_tenths` would
leave her on 12 and this test would catch it.

Also to add to section 3's list, from S9b's accept line: the late card that would change
its round's winner if counted, the two allowances that order a round's players
differently, and a reference round naming no round of the season.
