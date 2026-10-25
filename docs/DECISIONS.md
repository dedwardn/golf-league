# Decisions

Settled questions, newest last. One paragraph each: what, why, what it rules out. The code agent does not reopen these. The owner can, by adding a new entry that replaces an old one.

**D1 First user is the owner's own friend league (2026-09-19).** Build what that league needs. Other groups, sim centres and monetisation are out of scope until a season has run on this. Rules out: multi-tenant accounts, billing, vendor integrations.

**D2 Python only, server-rendered (2026-09-19).** FastAPI, Jinja, HTMX, SQLite. One language and one process keep the surface small for a solo owner working with a code agent. Rules out: a separate front-end codebase and an API contract to keep in sync.

**D3 Net cards, not pairwise stroke differences (2026-09-19, to be confirmed by the owner).** Every player plays off their own full playing handicap against the card, and duels compare net hole scores. One net card per player per contest makes best ball, virtual sides and allplay plain compositions of the same data. The Rules of Golf method gives the handicap difference to the higher player, which can put strokes on slightly different holes. Rules out: a second allocation method.

**D4 Derived values are never stored (2026-09-19).** Indexes, results, awards and standings are recomputed from facts on every read. v0.1 stored them and needed repair scripts. A season is about 300 cards, so cost is irrelevant.

**D5 Formats are config over four contest kinds (2026-09-19).** duel, field, allplay, teambonus, each on a basis of holes, total or stableford, with single, bestball or virtual sides. Last season's formats and the mechanics marked v1 in LEAGUE_DESIGN.md are expressible this way. Later mechanics may need a new kind, each as its own step.

**D6 Every player always hands in a full individual card (2026-09-19).** Team formats are compositions of individual cards. This keeps one card type and lets every round feed the index. Rules out: scramble, foursomes and other shared-ball formats.

**D7 Players are identified by a personal secret link (2026-09-19).** No passwords, no sign-up. Enough for a friend group and almost no code.

**D8 Hole-by-hole cards only (2026-09-19).** No totals-only cards. Old seasons are not imported as cards. Seed indexes for the first season are typed in by the admin.

**D9 Trust is social (2026-09-19).** R12 hides cards until you have played, the group sees every card afterwards, and the admin can correct or void. No video, markers or attestation.

**D10 The owner authors the guardrails (2026-09-19).** `pyproject.toml`, `scripts/`, `.claude/` and the docs named in CLAUDE.md are changed only on the owner's request. When a prose rule is broken twice, it is turned into a check.

**D11 Course rating and slope are typed in per tee (2026-09-19).** The Trackman card shows yardage, par and stroke index, but not rating or slope. Daniel plays each course up front and reads both from the Trackman app, so they are entered once per tee and the photo fills the rest. Rules out: defaulting to slope 113, and deriving difficulty from the field for now. A field-derived difficulty stays available as a later step if the course mix turns out to distort indexes.

**D12 Players are added by the admin and carry sim names (2026-09-19).** The admin enters a name and outdoor handicap, the app makes a link, and the admin sends it in the group chat. Each player collects the names their simulator cards use, so a photographed card finds the right player. Rules out: self sign-up, and any identity check beyond the link.

**D13 v2 moves to its own repository (2026-09-20).** The v2 tree started as a subdirectory of `golf_tourney`, whose history also holds v0.1 and two abandoned React attempts. A code agent reading `git log` there lands on the code CLAUDE.md names as the anti-pattern, and every diff carries a `v2/` prefix for the life of the project. The four step commits are carried over with `git subtree split --prefix=v2`, so S0 to S2 and their step reports survive the move. The old repository is archived, not deleted: it holds the league data the backtest used and the code the rules were read out of. Rules out: reaching into the archive from a build step. Anything v2 needs from it is copied in as a fixture, by the step that needs it.

**D14 Points are exact (2026-09-20).** `Award.points` and the config fields that set them are `Fraction`, never `float`. R10 orders standings by sums of points, so two players who should be level have to compare equal. No input has been shown where float breaks that, and at these magnitudes it may never: three float thirds do sum to exactly 1.0. Exactness is here so the question does not have to be asked again at each new rule that divides. The divisions arrive regardless: allplay divides by the field size at S5 and teambonus halves a bonus at S6. Fraction in the config as well as the award, so a half point for a draw costs no later change to a field a season is already stored against. `multiplier` stays an integer, because a double points round is the case it exists for and a half weight round is expressed by halving the points. Rules out: floats anywhere in points, and a scaled integer unit like tenths, which the allplay division would break.

**D4 consequence, recorded 2026-09-22.** Because nothing derived is stored, a rule changed part-way through a season does not take effect from that round onwards: it rewrites every round already played, including standings the group has already seen and argued about. Rule changes therefore belong before a season starts. One that cannot wait needs its own decision about what the group is told, because the alternative, freezing rounds once they close, means storing derived values and is exactly what D4 rules out.

**D15 Two season modes (2026-10-25).** A season is individual or team. In a team season two players form a team for the whole season, and the team is the competitor: it earns the points, holds the standings row and wins rounds. Rounds are scored by ranking every team against every other, with allplay, not by head-to-head matches. The next real season is a team season, so team mode is built before the season can start. Rules out: individual and team scoring in one season, teams of any size but two, substitutes, and duels in a team season.

**D16 Shared-ball formats in a team season (2026-10-25).** Trackman's bay software plays scramble, foursome and greensome, and the group wants them. In a team season a shared-ball round has one team card per team, played together on one bay. D6 now holds for individual seasons and for a team season's own-ball rounds only. A team card feeds no index. Rules out: team cards in an individual season.

**D17 Indexes are fixed in a team season (2026-10-25).** Every player's index is their seed for the whole team season, and every team handicap is built from it with the format's allowance. Team handicaps stay stable and predictable, and the question of what a shared ball does to an index never arises. A seed can be corrected until round one closes, because a later correction rewrites every round already played (D4 consequence). Rules out: index movement during a team season, and tracking an index on the side for now.
