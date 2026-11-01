# Design reference

Static HTML for every screen, plus one stylesheet. First produced from the design canvas on 2026-09-19, redrawn for the team season on 2026-11-01.

These are **layout references, not templates**. Steps S15 to S17 turn them into Jinja templates under `src/league/web/templates/`. Rules for that work:

- Copy `tokens.css` to `src/league/web/static/app.css` and link it. Do not add a second stylesheet, a CSS framework or a build step.
- Build each template from the matching file here. Keep the structure, the class names and the wording. If a screen needs something the reference does not show, stop and ask rather than inventing a layout.
- Classes live in `tokens.css`. A one-off tweak is an inline style, as in these files. A pattern that appears on three screens earns a class, added to `tokens.css` in the same step.
- The sample data here is made up but shaped like the real thing. What each screen actually reads from `SeasonView` is listed in section 7 of `docs/SPEC.md`.
- Templates contain no arithmetic. Every number on these screens is computed in the domain and passed in.
- Forms post to the paths shown in the `action` attributes. Those are the routes to build.
- Mobile first: the player screens are drawn at 390 px wide, the admin screens at 1180 px. The player screens must work on a phone; the admin screens are used on a laptop.

Accessibility is part of the reference: real `button`, `a` and `label` elements, a visible label on every input, and touch targets of at least 44 px. Keep them.

## Files

Drawn for a team season, the one built first:

Player, on a phone: `home.html`, `submit-photo.html`, `submit-confirm.html`, `round-locked.html`, `round-result.html`, `standings.html`.

Admin, on a laptop: `admin-season.html`, `admin-round.html`, `admin-player.html`, `admin-tee.html`. A round's actions (open, close, undo a close, correct or void a card, a manual award) sit on `admin-round.html`, so no screen of their own is needed.

Individual season, for S21: `admin-pairings.html` is still the September drawing. What only an individual season shows on the other screens (duels, contests and presets, index rates, provisional players) was in the September files, which git keeps at commit `79d777f`. S21 redraws it.

This folder is the reference the code follows. The September canvas is retired.
