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
