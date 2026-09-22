# S6b The virtual side for any player without an award

**Implemented**

A duel's sweep now reaches every counted card whose player holds no award in the
contest, not only the late ones, so a player who was in no pairing when the round opened
meets the virtual side and earns from it instead of scoring nothing. The `earned` set is
back as the guard that stops a player being paid twice, and a duel with no pairings at
all is now an error rather than a contest that quietly awards the whole field.

**Where**

| File | Holds |
|---|---|
| `src/league/domain/contests.py` | `duel_awards` rejects empty `pairings`, collects `earned` from the pairing awards, and sweeps every entry outside it. `_late_awards` is `_alone_awards`, since the old name is false the moment an on-time card reaches it and R9's own word is alone. 213 lines. |
| `tests/domain/test_contests_duel.py` | Three new tests, one rename to match R9's "each such card", and five existing tests whose expected tuples grew. 237 lines. |
| `tests/domain/test_contests_teambonus.py` | One comment rewritten, no assertion changed. |

101 tests, 100 percent coverage of `league.domain`. 85 added lines and 18 removed across
three files, one of them `src`. Every accept criterion has a test: an unpaired on-time
card earns, a late card still earns, a player who lost at `points_loss` 0 is not swept
again, both sides missing leaves each card to the virtual side, and no pairings is an
error. Also edited at `/finish`: `docs/BUILD_PLAN.md` (status). `docs/ARCHITECTURE.md`
is untouched, because no public name was added, removed or renamed.

This step retracts S4's audit finding 4, which deleted the `earned` set with the
reasoning that a player with a late card can never be among the pairing awards, so R9's
"got no points in this contest" was automatic. That was true of the code as it stood:
the sweep was confined to late cards, and R13 gives a player one counted card per round.
It stopped being true the moment the sweep reached on-time cards. The set is not a
defensive nicety restored out of caution. Removing it now fails thirteen tests, and
narrowing it to players who took points rather than players who hold an award fails
eight, because `a_config()` sets `points_loss` to zero and every loser in the file has an
award worth nothing. The finding was right when it was written and is wrong now.

**Public API**

No public name was added, removed or renamed. `duel_awards` keeps its signature:

```python
def duel_awards(
    entries: Sequence[NetEntry],
    tee: Tee,
    closed_at: datetime | None,
    pairings: Sequence[Pairing],
    config: DuelConfig,
) -> tuple[Award, ...]
```

Its contract changed twice. It raises `ValueError` when `pairings` is empty, which R9
now states. And it returns awards in pairing order, then one for each card the pairings
left without an award, in entry order, where it previously put only late cards last.

**Deviations from plan**

1. The empty-pairings check and `test_r9_a_duel_with_no_pairings_is_an_error` are not in
   the plan as written. They were added when the owner ruled on the plan's only open
   question, on the ground that this step creates the hazard: before the sweep widened,
   an unpublished pairing list produced no awards, which is visibly nothing, and after it
   the same round would award every player against a virtual side built from the rest of
   the field, which reads as a result. R9 gained the sentence in commit `67faf0d`.
2. One line beyond the plan's "the loop inside `duel_awards` plus the helper rename": the
   comment in `_pairing_awards` said "each late card is on its own" where R9 now says
   each such card. Leaving it would have left the module contradicting the rule in the
   one branch that most needs to agree with it.

Nothing else differs. The three planned files are the three files changed, the five
tuples that grew are the five the plan listed, and each grew to the values the plan
predicted.

Applied at audit:

3. The two line counts above were wrong: 205 was carried forward from S6's report without
   recounting, and 248 was never counted at all. They are 213 and 237. A step report is
   the agent's own output, so the owner exempted `docs/steps/` from CLAUDE.md rule 4
   rather than have the reviewer report a number it could fix.
4. The comment on `test_r9_a_player_who_lost_a_pairing_is_not_swept_again` said the
   virtual side was 72. Excluding Ann the pool is Bob 66, Cal 74, Dee 74, so hole 1 is
   `round_half_up(13/3)` and the side is 71. The assertion was right and is unchanged.
   Both wrong numbers this step were in prose that nothing verifies.
5. The comment on `test_r9_teambonus_two_teams_that_played_and_earned_nothing_share_the_bonus`
   is two lines saying what the test guards, not five narrating step history.

Settled at audit, no code change:

6. The reviewer proposed giving Ann a zero award in that teambonus test, on the ground
   that R9's duel now guarantees every counted card an award. Rejected by the owner: the
   fixture is what the test exists for. With a zero award for Ann, seeding `sums` from
   `round_awards` rather than from the on-time entries gives the same answer, and the
   mutation stops failing. R9 constrains what a season contains, not what a
   `Sequence[Award]` may hold, and `teambonus_awards` states no precondition that every
   entry has an award. I re-ran that mutation after the comment change: it still fails
   this test and no other.
7. The empty-pairings bound sits in `contests.py` while ARCHITECTURE assigns R9 bounds to
   `facts.py`. It is in the only place it can be, because `pairings` is an argument and
   no dataclass owns the list, as is the single-side check beside it, which needs the
   config as well as the pairing. ARCHITECTURE gains a clause: `facts.py` owns bounds on
   one dataclass's own fields, and a bound needing two facts together, or a whole
   collection, lives with the rule that can see both.

**Deliberately not done**

- Pairings themselves and the admin screens. S8 and S17.
- Anything in S7, including the standings that will read these extra awards.
- Late cards in field and allplay contests. R9 still confines them to duels, and open
  decision 4 asks whether that should change.
- Any change to `teambonus_awards`. It sums more awards now, because more exist, but its
  contract is untouched.

**Open questions**

1. A duel on a round whose pairings were never published now raises rather than returning
   nothing. S9 decides what the admin sees: an error that names the round, or a season
   that refuses to compute at all. The second would take down every other round's view
   for one unpublished list, which argues for the first, but it is S9's call.
2. The virtual side for a swept player is built from the on-time entries, which include
   the other swept players. In a round whose pairings cover half the field, the unpaired
   half are each measured against a pool containing one another. That follows R7 as
   written and I believe it is intended, but it has not been stated anywhere.
3. Not this step's, but next: S7's accept line includes tie order, and R10's tie order is
   still open decision 5. The criterion cannot be written until it is settled.
