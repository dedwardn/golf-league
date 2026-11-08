# Design reference

Static HTML for every screen, plus one stylesheet. First produced from the design canvas on 2026-09-19, redrawn for the team season on 2026-11-01.

These are **layout references, not templates**. Steps S15 to S17 turn them into Jinja templates under `src/league/web/templates/`. Rules for that work:

- Copy `tokens.css` to `src/league/web/static/app.css` and link it. Do not add a second stylesheet, a CSS framework or a build step.
- Build each template from the matching file here. Keep the structure, the class names and the wording. If a screen needs something the reference does not show, stop and ask rather than inventing a layout.
- Classes live in `tokens.css`. A one-off tweak is an inline style, as in these files. A pattern that appears on three screens earns a class, added to `tokens.css` in the same step.
- The sample data here is made up but shaped like the real thing. What each screen actually reads from `SeasonView` is listed in section 7 of `docs/SPEC.md`.
- Templates contain no arithmetic. Every number on these screens is computed in the domain and passed in, except a count of the rows a screen is passed, which the template may take, as Round before playing's "3 of 4" counts its teams.
- No JavaScript but one allowed kind, as ARCHITECTURE's Stack records: a short inline script in a screen's template that only moves focus, enables and disables a control, or reloads a page the browser restored from its back-forward cache, with no arithmetic on what the screen shows and no validation, which stay on the server. Check the card's is the first. Add a course and tee's is the second: a par moves focus to the next hole's par once one digit is typed, hole 9 to hole 10, and selects its text on focus, while a stroke index does not jump.
- Forms post to the paths shown in the `action` attributes. Those are the routes to build.
- A decimal the admin types takes a comma or a dot as its decimal mark, since a phone's number keyboard in Norway shows a comma.
- Mobile first: the player screens and the admin round, player and tee screens are drawn at 390 px wide, one column that reads the same on a laptop, and must work on a phone. Season setup is drawn at 1180 px for a laptop and must not break at 390 px.

Accessibility is part of the reference: real `button`, `a` and `label` elements, a visible label on every input, and touch targets of at least 44 px. Keep them. The one exception is the hole rows of `admin-tee.html`, about 36 px each with a 32 px input, so the 18 holes of par and stroke index fit on a phone and stay easy to read (the owner, at S17b's click-through).

## Files

Drawn for a team season, the one built first:

Player, on a phone: `home.html`, `submit-photo.html`, `submit-confirm.html`, `round-locked.html`, `round-result.html`, `standings.html`.

Admin, on a phone first: `admin-round.html`, `admin-player.html`, `admin-tee.html`. Admin, on a laptop: `admin-season.html`. A round's actions (open, close, undo a close, correct or void a card, a manual award) sit on `admin-round.html`, so no screen of their own is needed. Every admin screen has a bottom nav like the player nav, Season, Rounds, Players and Courses, with its own tab marked, because a link opened on the phone starts a browser without the admin cookie, so the admin moves only by tapping. Season joins with S17c and Rounds with S17d.

Individual season, for S21: `admin-pairings.html` is still the September drawing. What only an individual season shows on the other screens (duels, contests and presets, index rates, provisional players) was in the September files, which git keeps at commit `79d777f`. S21 redraws it.

This folder is the reference the code follows. The September canvas is retired.
