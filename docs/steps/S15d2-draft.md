# S15d2 Set up the bay: rulings made before the plan

The architect reviewed S15d as one plan on 2026-11-02 and split it into S15d1 and S15d2. The owner approved the plan, the split and the fixture changes. What follows is the reviewed plan for S15d2, which comes back to the architect only if it changes. S15d1 has landed first, so a tee is `Tee(course, name, ...)` and `tee_id` is gone.

## Plan

- `domain/facts.py`: `BaySetting(menu: str, setting: str, value: str)`, shown as written, read by no rule. `SeasonFacts.bay_settings: tuple[BaySetting, ...] = ()`, which `compute_season` does not read; the docstring says so, as `RoundFacts` does of `late_until`.
- `domain/results.py`: `BayMenu(name: str, lines: tuple[BaySetting, ...])` and `BayRound(number: int, format: str, shared_ball: bool, course: str, tee_name: str, game: tuple[BaySetting, ...], menus: tuple[BayMenu, ...])`.
- `domain/bay.py` (new): `bay_round(facts: SeasonFacts, number: int) -> BayRound | None`. None for no such open round (it filters `closed_at is None` itself) and for an individual season (until S21). `game` is the lines whose menu is "Game"; `menus` is each other menu in first-written order, its lines in written order, gathered where the admin interleaved them. `shared_ball` comes from `takes_team_card`. It reuses home.py's `assert round_.format is not None` narrowing with its comment.
- `store/schema.py` and the `s11` migration: `seasons.bay_settings` Text NOT NULL, and `BAY_SETTINGS_JSON = TypeAdapter(tuple[BaySetting, ...])`.
- `store/save.py`: `save_season(connection, season_id: str, facts: SeasonFacts) -> None`, with "`facts.rounds` is not read". `store/load.py` reads the column into `SeasonFacts`.
- `services/setup.py`: `create_season` keeps its signature and calls the new `save_season`. This is the setup use case BUILD_PLAN names.
- `services/play.py`: `bay_view(engine, season_id: str, number: int) -> BayRound | None`. No viewer: the screen holds no result and no viewer data, and refusing an outside viewer would be a bound no rule states.
- `web/app.py`: `_bay` at `/rounds/{number}/bay`. No cookie is refused as on every route. None gives `PlainTextResponse("No such round.", 404)`, the shape `_standings` uses.
- `web/templates/formats.html` (new, no screen): home's `formats` map moves here and gains each format's game type; home and bay `{% from "formats.html" import formats %}`.
- `web/templates/bay.html` (new): a back row to `/` as on `submit-photo.html`, and no tabs. "Round N · <format name>", "Course: <course>". Players block: own-ball "Add everyone playing. For each player:", shared-ball "Add both of you to one team. For each player:", "Tee: <tee name>", "HCP index: leave as it is". Game block: "Game type: <game type>", "Holes: All", then each Game line as "<setting>: <value>". One block per other menu, titled with its name. "Leave every other setting as it is." Last, own-ball "After the round, enter your Gross row from the scorecard.", shared-ball "After the round, one of you enters the team's Gross row." No `|safe`.
- `web/templates/home.html`: the Set up the bay button inside `{% if team %}`, in `grid-2` at half width until S16, between the rows and the foot, `href="/rounds/{{ round.number }}/bay"`.
- `tests/fixtures/team_season.py`: T3's `SEASON` carries the owner's settings, in this order. Game: Pins Medium; Mulligans "Always. Only for an obvious technical fault, such as a shot the sim misread or didn't pick up."; Putting "Auto, Fixed". Course: Wind Off; Fairway firmness Medium; Green firmness Medium; Green stimp 9. S9B has none. `tests/fixtures/database.py` calls the new `save_season`.

## Rulings on the tests

- Web: own-ball Game block reads game type and "Holes: All" first, then the season's lines; shared-ball "Add both of you to one team." with its game type, parametrized over scramble, foursome and greensome on the `all-open` season; combined reads "Individual, Stroke (Gross)"; the Course block in written order; blocks in Trackman's order with each closing line; Players on `t3-open` round 3 reads "Tee: Blue", apart from its course. The Mulligans value renders `didn&#39;t`, so the test unescapes it.
- Web 404s: closed on `t3-open` round 2, which exists; individual season on `s9b-open` round 4, which exists and is open; an unknown number. Without a cookie, refused. A league player outside the season gets 200.
- Web home: each open round of a team season links to its bay; no link in an individual season or for a viewer outside the season. `test_section_7_home_has_no_buttons_until_s15d_and_s16` is replaced by a test that the one button is the bay's.
- `tests/domain/test_bay.py`: interleaved menus in the order Weather, Game, Course, Weather, Game, asserting `game` holds both Game lines and `menus` is Weather (two lines) then Course, which `sorted()` would fail. A season without settings has empty `game` and `menus`. `shared_ball` for own-ball and shared-ball. Each None case. Read `line.setting` and `line.value` rather than comparing whole `BaySetting`s, since vulture reads no templates.
- `tests/services/test_play.py`: `bay_view` reads a stored season; a draft created through `create_round` gives None (the domain cannot tell a draft from an unknown number).
- Bay settings round-trip through the existing S9b and T3 equality tests and `create_season`'s.

## Doc edits to apply with S15d2

`docs/ARCHITECTURE.md`:

- Old: `which home reads and RoundFacts does not carry`
  New: `which home reads and RoundFacts does not carry, and from S15d2 BaySetting, one line of a season's bay settings, which SeasonFacts carries for the bay screen and `compute_season` does not read`
- Old: `HomePlayer, HomeTeam, HomeRound, HomeView, and `points_text``
  New: `HomePlayer, HomeTeam, HomeRound, HomeView, BayMenu, BayRound, and `points_text``
- Old: `and whether the season is a team season, for the same reason.`
  New: `and whether the season is a team season, and the bay screen's say a round's format, course, tee name and the season's bay settings, for the same reason.`
- Add after the `domain/home.py` row: `| `domain/bay.py` | One open round's Set up the bay screen: its format, its tee, and the season's bay settings split into the Game lines and each other menu. It calls `access.py` and holds no rule of its own | | `bay_round` |`
- Old: `which shows every round, and a player's home |`
  New: `which shows every round, a player's home, and one open round's bay screen |`
- Old: `One Jinja template per screen, built from `docs/design/``
  New: `One Jinja template per screen, built from `docs/design/`, and `formats.html`, which is no screen and holds each format's name, line and game type for the screens that import it`

`docs/SPEC.md`, section 7:

- Old: `A team season only, until S21. No design file:`
  New: `An open round, in a team season only until S21. No design file:`
- Old: `with no format, no rows, no "Scores unlock" and no season card.`
  New: `with no format, no rows, no "Scores unlock", no link to Set up the bay and no season card.`
- Old: `and the link to Set up the bay on each open round with S15d.`
  New: `and the link to Set up the bay on each open round of a team season with S15d.`

## Demo

The demo database lives outside the repo, rebuilt from T3 and `t3_open` through the fixture save functions so every round has a window, and so it carries the owner's settings. The owner clicks through on a phone before the commit.
