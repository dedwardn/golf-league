# S9b Season pipeline

**Implemented**

`compute_season(facts)` turns a season's facts into every round's awards and winners, the season
table and each segment's. It replays each player's index over all their counted cards, late ones
included, nets each round's cards once per contest at that contest's allowance, runs a teambonus
after the duel it names with only that duel's awards, and counts closed rounds only. The configs
carry `kind`, `allowance` and a duel's `reference_rounds`; `RoundFacts` and `SeasonFacts` refuse
a teambonus without a duel source, and a reference round that is missing, repeated, later
than its own round or on another tee.

**Where**

| File | Holds |
|---|---|
| `src/league/domain/facts.py` | `allowance` with R9's bound on duel, field and allplay, `reference_rounds` on duel, `kind` on all four, the `ContestConfig` union, `RoundFacts` and `SeasonFacts` with their checks, and `_check_reference_rounds`. 286 lines. |
| `src/league/domain/results.py` | `RoundView`, `SegmentView`, `SeasonView`. 121 lines. |
| `src/league/domain/season.py` | New. `compute_season`, with `_index_by_card`, `_entries`, `_on_time`, `_references`, `_card_contest_awards`, `_round_awards` and `_winners`. 184 lines. |
| `src/league/domain/contests.py` | `_is_on_time` renamed `is_on_time`; body and docstring unchanged. |
| `tests/domain/fixtures/season.py` | New. The golden season as facts. |
| `tests/domain/test_season.py` | New. Ten tests over the golden season and six variants of it. |
| `tests/domain/test_facts.py` | Nine tests for the new bounds and the cross-fact checks; `test_r9_virtual_n_is_one_or_more` builds its duel from `a_duel()`. |
| `src/league/domain/strokes.py` | `FULL_ALLOWANCE`, a playing handicap with no contest allowance (second audit). |
| `src/league/domain/index.py` | R4's strokes at `FULL_ALLOWANCE` instead of a bare 100 (second audit). |
| `tests/domain/test_strokes.py` | `test_r1_allowance_zero_gives_no_strokes` (second audit). |

152 tests, 100 percent coverage of `league.domain`. Also edited at `/finish`: `docs/BUILD_PLAN.md`
(status) and `docs/ARCHITECTURE.md` (Public API cells). Committed beforehand on their own: six
doc edits, as `ceb5c44`.

Every accept criterion has a test. Before the report, each of these bugs was seeded into the
pipeline in memory and failed at least one test: entries in the mapping's order, one set of
entries per round at allowance 100, an index replayed from on-time cards only, reference rounds
ignored, late cards let into the reference pool, and late cards let into the round winner.

*The golden season.* Tee A has rating equal to par, slope 113 and stroke index equal to hole
number, so a playing handicap is allowance times index rounded half up and a differential is ten
times gross over par. Every card is par except the listed holes, each one over. Index before each
card, in tenths: ann 0, 0, 0, 0 · bob 40, 40, 40, 35 · cam 80, 70, 70, 70 · dee 120, 120, 115,
113 · eve 160, 160, 155, 157 · fay 180 throughout. dee's 113 before round 4 comes from her late
round-2 83.

| Net at 100 | ann | bob | cam | dee | eve | fay | Winners |
|---|---|---|---|---|---|---|---|
| R1 | 72 | 72 | 70 | 72 | 72 | 72 | cam |
| R2 | 72 | 72 | 72 | 71 late | 71 | 72 | eve |
| R3 | 72 | 71 | 72 | 71 | 72 | 72 | bob, dee |
| R4 open | 72 | 72 | 72 | 73 | 72 | 70 | none |

- R1, field on total, points 10, 6, 3, 1: cam 10, the other five 2 each, and eve's manual 2.
- R2, duel on stableford at 90, handicaps 0, 4, 6, 11, 14, 16: ann beats fay, bob beats eve,
  cam's 35 points beat a virtual side of 76 and 32, and dee's late 36 beats the virtual side of
  ann, bob, cam and eve, 73 and 35. Three points each to ann, bob, cam and dee.
- R3, allplay on total, scale 2: bob and dee 9/5, the other four 3/5.
- R4, best ball on total at 100 from round 3: ann and bob's 68 beat dee and eve's 70, and cam
  and fay's 65 beat a virtual side of 73, at 4 points a win. The teambonus goes to east, 12 to
  4: ann, bob and cam 3 each. The field at 75, handicaps 0, 3, 5, 8, 12, 14, nets 72, 73, 74, 76,
  76, 74: ann 12, bob 8, cam and fay 5, dee and eve 1. dee's manual 20 under the key `bb`.
- Season, best 2 of rounds 1 to 3: cam 13, ann, bob and dee 5 sharing second, eve 23/5 fifth,
  fay 13/5 sixth. Segment first-half: cam 13, ann, bob and dee 5, eve 4, fay 2.

**Public API**

```python
# facts.py
ContestConfig = DuelConfig | FieldConfig | AllplayConfig | TeamBonusConfig
# DuelConfig:      allowance: int = 100, reference_rounds: tuple[int, ...] = (), kind: Literal["duel"] = "duel"
# FieldConfig:     allowance: int = 100, kind: Literal["field"] = "field"
# AllplayConfig:   allowance: int = 100, kind: Literal["allplay"] = "allplay"
# TeamBonusConfig: kind: Literal["teambonus"] = "teambonus"


@dataclass(frozen=True)
class RoundFacts:
    number: int
    tee: Tee
    contests: tuple[ContestConfig, ...]
    cards: Mapping[str, Card]
    pairings: Mapping[str, tuple[Pairing, ...]]
    manual: tuple[ManualAward, ...]
    closed_at: datetime | None


@dataclass(frozen=True)
class SeasonFacts:
    rounds: tuple[RoundFacts, ...]
    seed_index_tenths: Mapping[str, int]
    provisional: frozenset[str]
    index_rule: IndexRule
    standings_rule: StandingsRule
    teams: Mapping[str, str]
```

`ValueError` for an allowance outside 0 to 100 (R9), a contest key repeated in a round (R9), a
teambonus whose `source` is not a duel contest of its round (R9), a round number repeated in a
season (R13), and a duel's reference rounds when one repeats, is no round of the season, is later
than the duel's own round or is on another tee (R7).

```python
# results.py
@dataclass(frozen=True)
class RoundView:
    awards: RoundAwards
    winners: tuple[str, ...]

@dataclass(frozen=True)
class SegmentView:
    name: str
    rows: tuple[StandingsRow, ...]

@dataclass(frozen=True)
class SeasonView:
    rounds: tuple[RoundView, ...]
    standings: tuple[StandingsRow, ...]
    segments: tuple[SegmentView, ...]

# season.py
def compute_season(facts: SeasonFacts) -> SeasonView

# contests.py
def is_on_time(entry: NetEntry, closed_at: datetime | None) -> bool
```

`compute_season` keeps the rounds in the order of `facts.rounds` and the segments in the order of
the standings rule. A round's awards are its contests' in config order, a teambonus in its own
place, then its manual awards. Entries are built in player id order. `KeyError` for a card whose
player has no seed index, or a duel whose key has no pairings; `ValueError` only as the rule
functions it calls raise it. It returns no index.

**Deviations from plan**

1. The derivation of the golden season is in this report, under Where, as the draft asked, and
   the fixture's docstring points here. The finish skill lists the report's headings and nothing
   else, so it sits under an existing heading rather than its own.
2. `FULL_ALLOWANCE = 100` names the allowance of R10's winners, of the entries a teambonus reads
   and of R4's strokes. The plan said "allowance 100" without naming it. It first lived in
   `season.py`; the second audit moved it to `strokes.py`, which owns R1.
3. `SeasonFacts`'s reference checks are in a private `_check_reference_rounds` directly above
   it. They first sat inline, which the architect counted at the complexity limit, so the two
   R7 checks the owner added at the second audit went in with them as one private function.
4. The fixture also exports `DEE_LATE`, the late card's timestamp, which the late-winner test
   moves round 2's close to.
5. `facts.py` ends at 286 lines, so the owner's fallback of moving the configs to
   `domain/configs.py` was not needed.
6. `docs/steps/S9b-draft.md` is deleted, but not in the S9b commit: the owner's commit
   `c6e0384`, a tooling change to the architect agent, deleted it by mistake and is pushed.
7. `strokes.py`, `index.py` and `test_strokes.py` are outside BUILD_PLAN's S9b module list.
   The owner's second-audit rulings sent `FULL_ALLOWANCE` and the allowance-0 test there.

Nothing else differs from the approved plan.

Settled at the first audit:

8. Finding 2, applied. The comment on `RoundFacts`'s source check said a field or missing
   source would quietly pay nobody, which was false: a field source pays its positions, and a
   missing one raises. Deleted; the error message states R9's rule.
9. Finding 4, applied. `_references` has one path, `config.reference_rounds or
   (round_.number,)`, instead of a separate branch for this round. `SeasonFacts` keeps round
   numbers unique, so this round is found by its number.
10. Finding 7, applied. `test_r7_two_contests_of_a_round_are_netted_at_their_own_allowance`
   and `test_r9_a_teambonus_sums_contest_awards_and_not_manual_ones` are gone: each asserted a
   slice the golden awards test already asserts in full, so neither could fail alone. Their
   comments now sit above `FIELD_AT_75` and `BONUS`, naming R7 and R9. The late-winner test lost
   its first assertion, which the golden winners test already makes; the second audit put it
   back. `test_facts.py`'s `a_round` defaults its tee to conftest's `TEE`.
11. Finding 1, declined. A duel key missing from `pairings` stays a `KeyError`, as the
   architect's plan ruling 6 had it and the owner approved. A key missing between two inputs one
   caller builds together is that caller's bug (the owner's S8 ruling 15). `duel_awards` keeps
   R9's `ValueError` for an empty pairing list, its own input. The architect proposed two doc
   edits stating this, one to BUILD_PLAN's S9b section and one to ARCHITECTURE's Errors
   convention. The owner made both edits.
12. Finding 5, declined. `FULL_ALLOWANCE` names R10's full playing handicap, and
    `MAX_ALLOWANCE` R9's ceiling on an allowance. They are equal for different reasons.
13. Finding 6, declined. Building the teambonus's entries only in rounds with a teambonus
    moves a line and removes none, and D4 makes the extra netting free.
14. Finding 3, sent to the owner, who ruled at the second audit: item 20.

Settled at the second audit, by the owner:

15. Finding 1, applied. `test_r10_a_late_card_does_not_win_its_round` asserts again that eve
    wins round 2 alone, before the moved-close assertion: without it the test passed a pipeline
    that let late cards win.
16. Finding 2, applied. `test_r1_allowance_zero_gives_no_strokes` pins R9's "0 plays the
    contest off gross". The behaviour already held; nothing checked it.
17. Finding 3, applied. `FULL_ALLOWANCE` moved to `strokes.py` and is imported by `index.py` and
    `season.py`. The config defaults stay a literal 100, because `facts.py` cannot import
    `strokes.py`.
18. Finding 4, applied in part. `test_r9_virtual_n_is_one_or_more` uses `replace(a_duel(),
    virtual_n=0)`. The two `a_field` helpers keep their names.
19. Finding 5, no code change. The owner reworded BUILD_PLAN's S9b section.
20. Finding 6, applied. `_index_by_card` returns player id to card id to index, and `_entries`
    looks each card up through its player, so a card id two players share cannot cross between
    them. Also from the owner's ruling on the first audit's finding 3: R7 now makes reference
    rounds distinct and none later than this round, which `_check_reference_rounds` enforces,
    with `test_r7_a_reference_round_later_than_its_own_round_is_an_error` and
    `test_r7_a_reference_round_named_twice_is_an_error`.

**Deliberately not done**

- A player's current index on the view. S14 and S15 (draft ruling 9).
- A round `state` or `late_until`. `closed_at` is all the pipeline reads; acceptance is S10.
- An error for `pairings` naming a key the round has no contest for (draft ruling 7).
- A season-wide check that card ids are unique. S11's primary key on card id enforces it, and
  the pipeline no longer depends on it (item 20).
- Refusing to open a round whose duel has no published pairings (R14). S14.
- Points and indexes as formatted strings. S15.

**Open questions**

Answered by this step:
- S4 question 1, the shape of `references`: settled by S9a's `ContestEntries`.
- S6 question 2, a teambonus sourced from another teambonus: `RoundFacts` requires a duel source.
- S6b question 1, a duel without pairings: R14 now makes it unreachable, so it stays an error.
- S7 question 1, the seeded list: `compute_season` takes it from `seed_index_tenths`'s keys,
  so no id repeats, and a card from an unseeded player is a `KeyError`.
- S7 question 3, segment tables: computed eagerly.
- S9a question 1, the trust in the caller: `season.py` filters every pool on time and
  `SeasonFacts` checks the tee.
- Card ids repeated across players (R13): indexes are keyed by player, then card id, so a
  repeat cannot net one player's card off another's index (item 20).
- Bounds on `reference_rounds` (R7): distinct, and none later than this round (item 20).

Carried:
1. S2 question 1, the index of a player with no cards. `compute_season` returns no index, so
   the seed-as-index view is S14's and S15's.
2. A manual award for a player who has no seed index and no card reaches no table, without an
   error, because the tables list seeded players only. SPEC states no bound. S11 or S14.
3. S8's resolving of pairing history out of a season. S14.
