# S9a Round winners and reference entries

**Implemented**

A closed round's winners can now be computed: the players with the lowest net total among
its on-time entries, level players sharing the round, none when there are no entries. A duel
contest now draws every virtual side from a `references` argument instead of from the round's
own on-time entries, so S9b can hand it the cards of other rounds. To stay within five
arguments, the three card-reading contests take one `ContestEntries` holding the tee,
`closed_at` and the entries netted for that contest. Nothing calls `round_winners` or passes
anything but this round's entries as `references` yet; S9b is the caller.

**Where**

| File | Holds |
|---|---|
| `src/league/domain/results.py` | `ContestEntries`. 93 lines. |
| `src/league/domain/contests.py` | The three card-reading contests take `ContestEntries`, and `duel_awards` takes `references`. `_pairing_awards` and `_alone_awards` draw the virtual side from them. Two docstrings rewritten. 210 lines. |
| `src/league/domain/standings.py` | `round_winners`. 106 lines. |
| `tests/domain/conftest.py` | `a_contest`, the builder every contest test file uses. |
| `tests/domain/test_contests_duel.py`, `test_contests_field.py`, `test_contests_allplay.py` | The 27 existing calls rewritten with no assertion changed, a local `on_time` helper in the duel file, and its late-card comment rewritten. Two new R7 tests in the duel file. |
| `tests/domain/test_standings_winners.py` | New. The three R10 round winner tests. 18 lines. |

132 tests, 100 percent coverage of `league.domain`. 186 lines added and 75 removed across
eight files, plus the new test file; about 180 of the changed lines are the mechanical
rewrite of existing calls. Also edited at `/finish`: `docs/BUILD_PLAN.md` (status) and
`docs/ARCHITECTURE.md` (the Public API cells for `results.py` and `standings.py`). Committed
beforehand on their own: the Owns cell of the `results.py` row, as `7cdcce1`.

Every accept criterion has a test: the lowest net total wins, players level on it share the
round, no entries means no winner, a virtual side drawn from the reference entries rather than
this round's, and reference entries still excluding the players the virtual side will meet.
The last two are split across both private paths: one goes through a pairing whose other side
is missing, the other through the sweep, so converting only one of `_pairing_awards` and
`_alone_awards` fails a test.

**Public API**

```python
# results.py
@dataclass(frozen=True)
class ContestEntries:
    tee: Tee
    closed_at: datetime | None
    entries: tuple[NetEntry, ...]
```

What one card-reading contest reads: its entries netted at that contest's allowance, the tee
they were netted on, and the close that decides which are on time. An input bundle, not a
result. No shape check.

```python
# contests.py
def duel_awards(
    contest: ContestEntries,
    references: Sequence[NetEntry],
    pairings: Sequence[Pairing],
    config: DuelConfig,
) -> tuple[Award, ...]

def field_awards(contest: ContestEntries, config: FieldConfig) -> tuple[Award, ...]

def allplay_awards(contest: ContestEntries, config: AllplayConfig) -> tuple[Award, ...]
```

Behaviour unchanged except that every virtual side in a duel is drawn from `references`. The
caller filters them, each reference round against its own `closed_at`, and passes this
round's on-time entries when the contest names no reference rounds. `teambonus_awards` and
`manual_awards` are unchanged.

```python
# standings.py
def round_winners(entries: Sequence[NetEntry]) -> tuple[str, ...]
```

The ids of the players with the lowest net total among those entries, sorted by player id,
empty when there are none. The caller passes one closed round's on-time entries netted at
full playing handicap. The winning net total is not returned: S15 reads it.

**Deviations from plan**

1. `docs/steps/S9b-draft.md` was reformatted with `ruff format`, and is part of this commit.
   `./scripts/check.sh` failed on a clean `HEAD` because the draft's Python code blocks were
   not formatted, which none of the S9a work caused. The owner asked for the file to be
   formatted on its own and included here: two aligned trailing comments and one blank line
   changed, no wording.
2. `on_time` in `test_contests_duel.py` takes an optional `closed_at`, defaulting to the
   round's close. The plan described a local helper that filters on time; the open-round test
   needs it to pass `None`.
3. The first line of `standings.py`'s module docstring now also names round winners. The
   plan did not list it; the module owns them and the old line no longer said so.
4. `results.py` now imports `Tee` from `facts.py`, which it did not before. `facts.py` imports
   nothing from `results.py`, so there is no cycle.

Nothing else differs. The planned files are the files changed, plus the draft above, and the
public functions are the ones listed.

Declined at audit, all five on the architect's ruling, with no change to code or docs:

5. Finding 1, `round_winners` sorting by player id, which R10 does not state. Sorting is the
   determinism `standings` already follows, and returning input order would make the result
   depend on how S9b builds its entries. The test passes the tied pair in reverse order so it
   fails an implementation that returns input order.
6. Finding 2, `round_winners` not enforcing R10's "on-time". BUILD_PLAN S9a says the caller
   filters, as `standings` receives closed rounds only. The check that a late card would
   change the winner is in S9b's accept line.
7. Finding 3, a shared `_on_time_entries` helper in `contests.py`. The predicate already has
   one body, `_is_on_time`; a helper would replace two one-line comprehensions with a third
   name. `teambonus_awards` filters player ids and could not use it.
8. Finding 4, the duel tests' `on_time` mirroring `_is_on_time`. It plays the caller's role,
   and a drift from R13 would show in S9b's late-card test. Passing explicit lists would add
   noise to 27 call sites.
9. Finding 5, `results.py` described as output dataclasses while holding `ContestEntries`.
   ARCHITECTURE already states the exception in words, and the owner approved that wording.

**Deliberately not done**

- `reference_rounds` on `DuelConfig`, resolving it to entries, and R7's rule that a reference
  round is a round of the season on this round's tee. S9b.
- `allowance` and `kind` on the configs, the `ContestConfig` union, contest ordering and
  `compute_season`. S9b.
- The winning net total on a view. S15.
- Any check on `references`. They arrive already filtered and on the right tee, so a bad pool
  is the caller's bug.

**Open questions**

1. `round_winners` and `duel_awards` trust the caller to pass on-time entries, and
   `duel_awards` never checks that `references` are on this round's tee. That is by design
   until S9b resolves them, but until then a wrong pool gives a plausible-looking virtual side
   rather than an error.
