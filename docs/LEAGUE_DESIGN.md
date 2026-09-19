# League design

Why the engine is shaped the way it is, and a menu of season designs it must be able to express. Research date 2026-09-19. Items marked (inference) are design reasoning, not tested anywhere.

## The problem, from our own data

Three seasons, about 250 player-rounds. Players per round fell from 16 to 4 in 2024-25. The median player finished 5 of 11 rounds. Players who ended with fewer than 6 rounds averaged +3.7 net over their first three rounds, stayers +0.5. Match play on net totals was balanced (14 wins, 11 losses, 1 draw for the higher handicap) but not close: median margin 6.5 strokes. Round-to-round noise is 3 to 5 strokes per player. Part of the early gap is a seeding problem, which R5 addresses. The rest is league design.

## What the evidence says

- The worst combination is one cumulative table, one big prize and full live standings. Trailing contestants stop trying when the gap is very large, and leaders ease off (Casas-Arce and Martinez-Jerez; Mueller and Schotter).
- Hiding standings is not the fix. Rank feedback helps when there are several reachable prizes and hurts when there is one. Show standings framed against something reachable: the next place, the next tier, with discards applied (Gelber lab study; Barankay).
- Intermediate prizes remove the discouragement effect for the player who is behind (Davis Cup study, 2,447 matches).
- Raising stakes late backfires. F1's double-points finale in 2014 was opposed by 96 percent of polled fans and dropped after one race. The PGA Tour dropped starting strokes after 2024.
- Punishing the leader feels unfair. Capping damage, discards, several paths to a prize and helping the trailer feel fair (game design literature on rubber-banding).
- Famous golf results are shaky: the Tiger Woods "superstar effect" does not survive a corrected design. The robust finding is narrower: very large visible gap plus concentrated prize leads to quitting.

Sources: https://asu.elsevierpure.com/en/publications/relative-performance-compensation-contests-and-dynamic-incentives , https://ideas.repec.org/a/bla/jeurec/v8y2010i4p717-743.html , https://users.nber.org/~agelber/papers/prizestructure.pdf , https://faculty.wharton.upenn.edu/wp-content/uploads/2012/07/rankincentives_1.pdf , https://ideas.repec.org/a/eee/eecrev/v118y2019icp364-381.html , https://www.racefans.net/2014/11/23/f1s-hated-double-points-finale-likely-one-off/ , https://www.pgatour.com/article/news/latest/2025/05/27/pga-tour-announces-enhancements-to-tour-championship-format-and-fedexcup-race , https://oakleafgames.wordpress.com/2014/02/13/game-theory-runaway-leader-rubber-banding-and-feedback/ , https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2533537

## The key async insight

Who you play with and who you play against are separate. A card handed in during the window counts against the assigned opponent, the whole field, a box, a team and a virtual side at the same time, no matter who shared the bay. One card can feed several contests, which is how a round stays meaningful for a player whose main race is lost.

## Mechanics and how the engine expresses them

| Mechanic | Effect on comeback and engagement | Engine | Status |
|---|---|---|---|
| Hole-by-hole net match | A blow-up hole costs one hole, not the round. Closer matches (inference) | duel, basis holes | v1 |
| Net total match, as 2025-26 | Familiar | duel, basis total | v1 |
| Position points, as 2023-25 | Familiar. Top-heavy tables reward variance | field with `position_points` | v1 |
| All-play: your card against every card | A bad round bottoms out at zero, every place is worth points, no luck of the draw. Less drama without a named opponent | allplay | v1 |
| Named rival on top of all-play | Keeps "my match this week" | duel plus allplay on the same round | v1 |
| Virtual opponent for absentees and catch-up | Missing a window is not fatal | duel with late cards, R9 | v1 |
| 2v2 best ball, high with low | Mixes abilities, social | duel, side bestball, pairing high_low | v1 |
| East v West with team bonus | Your card matters to others | duel plus teambonus | v1 |
| Best N of M rounds | A three-round bad start is fully erasable with best 7 of 10. Leaders discard too | standings `best_n` | v1 |
| Split season with segment winners | A hard restart at the point where this group collapses. A segment win should be a perk, not the only route (MLB 1981 lesson) | standings `segments` | v1 |
| Round winners and small recurring prizes | Intermediate prizes are the best-evidenced remedy | derived from awards per round | v1 view |
| Multiplier rounds | Supported, but evidence says keep it gentle. A double-points finale reads as artificial | contest `multiplier` | v1 |
| Boxes of 4 to 6 with promotion and relegation | A fresh winnable mini-league every cycle among near-equals. Weak below about 12 players | allplay with a scope per box, plus grouping facts | later |
| Knockout and plate resolved from cards, starting mid-season | A new contest opens where interest drops | duel with bracket pairing | later |
| Season team table | Your card matters after your own title is gone. A team with two dropouts is dead, so count the best 75 percent of cards | table over awards by season team | later |
| Season eclectic | Can only improve, late starters catch up fast. Needs a repeated course | new table over net cards | later |
| Finals day starting strokes (Gundersen) | Everyone arrives alive, the season buys a bounded head start. Cap the spread at about 5 net strokes | table to strokes mapping | later |
| Joker: declare one round double before playing | A legitimate lever for the trailer. Variance, not skill | per-player multiplier fact | later |
| Winner handicap cuts, bounties on the leader, streak bonuses, unlimited attempts | Feel unfair or reward paying for more bay time | | not planned |

Sources for mechanics: all-play https://www.footballguys.com/subscribers/apps/article.php?article=HarstadFiT7 , box leagues https://ussquash.org/organize/box-leagues-and-ladders/ , split seasons https://images.bowl.com/bowl/media/legacy/internap/bowl/rules/pdfs/SplitSeasonLeagues.pdf , discards https://www.rya.org.uk/network/running-racing/guidance-and-good-practice/club-racing/scoring/ , Gundersen https://en.wikipedia.org/wiki/Gundersen_method , eclectic allowances https://www.usga.org/handicapping/roh/Content/rules/Committee%20Content/USGA/LG_R7h8.htm , Duolingo leagues https://www.lennysnewsletter.com/p/how-duolingo-reignited-user-growth , jokers https://quizquizquiz.com/2012/11/jokers-in-quiz-nights/

## Three season blueprints

**A. Rival plus everyone (proposed starting point for 2026-27, owner decides).** 10 rounds, two-week windows. Each round has two contests on the same card: a Swiss-paired duel on holes (win 2, draw 1) and an allplay on holes with scale 2. So a round is worth 0 to 4 points, half from your named opponent and half from how you did against everyone. Rounds 4 and 7 are team rounds: best ball high with low, and East v West with a bonus. Standings best 7 of 10, segments rounds 1 to 5 and 6 to 10 with a small prize per segment and per round. Absentees and odd players meet the virtual side, with late cards accepted for two windows. Finals day in person. Risk: two numbers per round need one clear screen to explain.

**B. Boxes.** Round 1 seeds three boxes by net result. Three cycles of three rounds. Inside a box every card plays every other card (win 3, half 1, plus 1 for handing in). Two go up, one goes down, no card in a cycle means automatic drop. No cumulative table. Box and cycle position convert to finals day strokes. Risk: thin boxes. Needs 14 or more active players.

**C. Two halves, three trophies.** Opening and Closing tables (best 4 of 5 each), a season team score all year, and a knockout with plate that starts in round 6 and is resolved from the round cards. In any window there are three reasons to hand in a card, two of which do not depend on your start. Risk: complexity and a diluted main title.

Blueprint A needs only version 1 of the engine. B and C need the later steps named in the table.

## Example: blueprint A, round 3, as config

```json
{
  "contests": [
    {"key": "rival", "kind": "duel", "basis": "holes", "side": "single",
     "points_win": 2, "points_draw": 1, "points_loss": 0, "virtual_n": 4},
    {"key": "everyone", "kind": "allplay", "basis": "holes", "scale": 2}
  ]
}
```

The round itself carries `opens_at`, `closes_at` and `late_until` (R13). Season standings rule: `{"best_n": 7, "segments": {"opening": [1, 5], "closing": [6, 10]}}`.
