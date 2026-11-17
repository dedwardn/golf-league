import html
import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine
from test_admin import (
    NOTICE,
    OPEN_YOUR_ADMIN_LINK,
    Visitor,
    a_player,
    a_wrong_cookie,
    nav,
    no_cookie,
    the_nav,
)
from test_app import ADMIN_TOKEN, an_app

from fixtures.database import a_copy, a_template, everything
from fixtures.team_season import SEASON as T3
from fixtures.team_season import t3_open
from league.domain.configs import AllplayConfig, GreensomeFormat, ScrambleFormat
from league.domain.facts import StoredRound
from league.services.run import open_round, reopen_round
from league.services.setup import RoundSetup, create_round, create_tee, stored_rounds

ROUND_ROW = re.compile(
    r'<a class="row card card--sunken"[^>]*href="([^"]+)"><span class="grow"[^>]*>'
    r'<span[^>]*>([^<]+)</span><span class="meta"[^>]*>([^<]+)</span></span>'
    r'<span class="pill [^"]+">(\w+)</span></a>'
)
FIELD = re.compile(r'<div class="field__label">([^<]+)</div><div[^>]*>([^<]+)</div>')
HEADING = re.compile(r'<h1 class="h1"[^>]*>([^<]+)</h1>')
BACK = re.compile(
    r'<a class="btn btn--ghost btn--icon" href="([^"]+)" aria-label="Back to rounds">'
)
FORM = re.compile(r'<form class="card stack"[^>]*method="post" action="([^"]+)">')
INPUT = re.compile(r'<input [^>]*name="(\w+)" value="([^"]*)"')
OPTION = re.compile(r'<option value="([^"]*)"( selected)?>([^<]+)</option>')
FORMAT_ROW = re.compile(
    r'<input type="radio" name="format" value="(\w+)"( checked)?[^>]*>\s*<span[^>]*>([^<]+)</span>'
)
WARN = re.compile(r'<p class="card card--warn help"[^>]*>([^<]+)</p>')
ADD_A_ROUND = '<a class="btn btn--primary btn--block" href="/admin/rounds/new">Add a round</a>'
ADD_A_TEE = '<a href="/admin/tees/new">Add a course and tee</a>'
FIXED = "A round&#39;s setup is fixed once it opens."
WINDOW = "Opens and Closes are a date and a time."
NO_TEE = "Pick a course and tee."
WHITE = "Trinity Forest Golf Club · White"
BLUE = "Trinity Forest Golf Club · Blue"
# A window of its own, in winter time, so a time shown in UTC or the fixtures' window shows.
OPENS = datetime(2026, 3, 2, 8, 0)
CLOSES = datetime(2026, 3, 15, 21, 0)

Admin = Callable[[str], TestClient]


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    seasons = {"t3-open": t3_open(), "no-rounds": replace(T3, rounds=())}
    return a_template(tmp_path_factory.mktemp("template"), seasons)


@pytest.fixture
def database(tmp_path: Path, template: Path) -> Iterator[Engine]:
    engine = a_copy(template, tmp_path)
    yield engine
    engine.dispose()


@pytest.fixture
def browse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, database: Engine
) -> Iterator[Callable[[str], TestClient]]:
    """Opens a browser that has followed no link yet on one season of the database."""
    apps: list[FastAPI] = []

    def a_browser(season_id: str) -> TestClient:
        apps.append(an_app(monkeypatch, tmp_path / "league.db", season_id))
        return TestClient(apps[-1], follow_redirects=False)

    yield a_browser
    for app in apps:
        app.state.engine.dispose()


@pytest.fixture
def admin(browse: Callable[[str], TestClient]) -> Admin:
    """Opens the admin's browser on one season of the database."""

    def an_admin(season_id: str) -> TestClient:
        client = browse(season_id)
        client.get(f"/admin/k/{ADMIN_TOKEN}")
        return client

    return an_admin


def round_rows(response: Response) -> list[tuple[str, str, str, str]]:
    """Each row of Rounds as where it goes, its round, its course and tee, and its state."""
    return [
        (href, html.unescape(name), html.unescape(tee), state)
        for href, name, tee, state in ROUND_ROW.findall(response.text)
    ]


def fields(response: Response) -> list[tuple[str, str]]:
    """Each line of the round card as its label and what it reads, in order."""
    return [
        (html.unescape(label), html.unescape(text)) for label, text in FIELD.findall(response.text)
    ]


def a_draft(database: Engine) -> None:
    """Round 6 of T3 as a draft, with allowances that are not its format's defaults."""
    tee = T3.rounds[2].tee
    setup = RoundSetup(
        "t3",
        6,
        tee.course,
        tee.name,
        OPENS,
        CLOSES,
        T3.rounds[2].contests,
        format=ScrambleFormat(low=40, high=10),
    )
    create_round(database, setup)


def test_rounds_lists_every_round_of_the_season_each_opening_its_screen(admin: Admin) -> None:
    assert round_rows(admin("t3").get("/admin/rounds")) == [
        ("/admin/rounds/1", "Round 1 · Best ball", WHITE, "Closed"),
        ("/admin/rounds/2", "Round 2 · Combined", WHITE, "Closed"),
        ("/admin/rounds/3", "Round 3 · Scramble", BLUE, "Closed"),
        ("/admin/rounds/4", "Round 4 · Greensome", BLUE, "Closed"),
        ("/admin/rounds/5", "Round 5 · Foursome", BLUE, "Closed"),
    ]


def test_rounds_read_an_open_round_and_a_draft(admin: Admin, database: Engine) -> None:
    states = [row[3] for row in round_rows(admin("t3-open").get("/admin/rounds"))]
    assert states == ["Open", "Closed", "Open", "Closed", "Closed"]
    a_draft(database)
    assert round_rows(admin("t3").get("/admin/rounds"))[-1] == (
        "/admin/rounds/6",
        "Round 6 · Scramble",
        BLUE,
        "Draft",
    )


def test_a_season_with_no_round_lists_none(admin: Admin) -> None:
    response = admin("no-rounds").get("/admin/rounds")
    assert response.status_code == 200
    assert round_rows(response) == []


def test_a_round_screen_reads_its_tee_window_format_and_allowances(admin: Admin) -> None:
    response = admin("t3").get("/admin/rounds/1")
    assert HEADING.findall(response.text) == ["Round 1 &middot; Best ball"]
    assert fields(response) == [
        ("Course and tee", "Trinity Forest Golf Club · White · par 72"),
        ("Opens", "Mon 5 Jan, 09:00"),
        ("Closes", "Sun 1 Feb, 22:00"),
        ("Format", "Best ball"),
        ("Handicap allowance", "85% each"),
    ]
    assert BACK.findall(response.text) == ["/admin/rounds"]


@pytest.mark.parametrize(
    ("number", "format_", "allowance"),
    [
        (2, "Combined", "100% each"),
        (3, "Scramble", "35% lower, 15% higher"),
        (4, "Greensome", "60% lower, 40% higher"),
        (5, "Foursome", "50% of the pair's total"),
    ],
)
def test_r16_each_format_reads_its_own_allowance(
    admin: Admin, number: int, format_: str, allowance: str
) -> None:
    assert fields(admin("t3").get(f"/admin/rounds/{number}"))[3:] == [
        ("Format", format_),
        ("Handicap allowance", allowance),
    ]


def test_r16_an_opened_round_reads_its_own_allowances(admin: Admin, database: Engine) -> None:
    """Only create_round called directly gives a round allowances other than its format's
    defaults, and its card reads them once it opens."""
    a_draft(database)
    open_round(database, "t3", 6)
    response = admin("t3").get("/admin/rounds/6")
    assert fields(response) == [
        ("Course and tee", "Trinity Forest Golf Club · Blue · par 72"),
        ("Opens", "Mon 2 Mar, 09:00"),
        ("Closes", "Sun 15 Mar, 22:00"),
        ("Format", "Scramble"),
        ("Handicap allowance", "40% lower, 10% higher"),
    ]
    assert FIXED in response.text


@pytest.mark.parametrize("season_id", ["t3", "t3-open"])
def test_r14_an_open_or_closed_rounds_setup_is_fixed(admin: Admin, season_id: str) -> None:
    assert FIXED in admin(season_id).get("/admin/rounds/1").text


def test_a_round_without_a_format_reads_its_number_alone(admin: Admin) -> None:
    client = admin("s9b")
    assert round_rows(client.get("/admin/rounds"))[0][1] == "Round 1"
    response = client.get("/admin/rounds/1")
    assert HEADING.findall(response.text) == ["Round 1"]
    assert [label for label, _ in fields(response)] == ["Course and tee", "Opens", "Closes"]


def test_the_page_of_a_round_the_season_does_not_have_reads_no_such_round(
    admin: Admin,
) -> None:
    response = admin("t3").get("/admin/rounds/99")
    assert response.status_code == 404
    assert NOTICE.findall(response.text) == ["No such round."]


@pytest.mark.parametrize("visitor", [no_cookie, a_player, a_wrong_cookie])
def test_rounds_refuse_a_visit_without_the_admin_cookie(
    browse: Callable[[str], TestClient], database: Engine, visitor: Visitor
) -> None:
    """Each post names a round on which it would store something with the cookie."""
    a_draft(database)
    reopen_round(database, "t3", 1)
    browser = visitor(browse("t3"))
    before = everything(database)
    tee = "course=Trinity+Forest+Golf+Club&tee=White"
    responses = [
        browser.get("/admin/rounds"),
        browser.get("/admin/rounds/1"),
        browser.get("/admin/rounds/new"),
        browser.post("/admin/rounds/new", data=a_form("7", tee, "scramble")),
        browser.post("/admin/rounds/6", data=a_form("", tee, "scramble")),
        browser.get("/admin/rounds/6/open"),
        browser.post("/admin/rounds/6/open"),
        browser.post("/admin/rounds/1/close"),
        browser.post("/admin/rounds/2/reopen"),
    ]
    for response in responses:
        assert response.status_code == 401
        assert NOTICE.findall(response.text) == [OPEN_YOUR_ADMIN_LINK]
    assert everything(database) == before


def test_rounds_and_a_round_have_the_nav_with_rounds_marked(admin: Admin) -> None:
    client = admin("t3")
    for path in ("/admin/rounds", "/admin/rounds/1", "/admin/rounds/new"):
        assert nav(client.get(path)) == the_nav("Rounds")


# The round card as a form (S17d2b).
FORMAT_ROWS = [
    ("bestball", "Best ball · 85% each"),
    ("combined", "Combined · 100% each"),
    ("scramble", "Scramble · 35% lower, 15% higher"),
    ("foursome", "Foursome · 50% of the pair's total"),
    ("greensome", "Greensome · 60% lower, 40% higher"),
]
TEES = [
    "Old Links · White · par 72",
    "Trinity Forest Golf Club · Blue · par 72",
    "Trinity Forest Golf Club · White · par 72",
]
DECISION_6 = (AllplayConfig("allplay", "stableford", Fraction(10)),)
BLUE_TEE = T3.rounds[2].tee


def options(response: Response) -> list[tuple[str, bool, str]]:
    """Each tee of the select as its value, whether it is selected, and what it reads."""
    return [
        (html.unescape(value), bool(selected), html.unescape(text))
        for value, selected, text in OPTION.findall(response.text)
    ]


def tee_value(response: Response, text: str) -> str:
    """The value of the drawn option that reads `text`, as the browser posts it."""
    return next(value for value, _, shown in options(response) if shown == text)


def format_rows(response: Response) -> list[tuple[str, str]]:
    return [(key, html.unescape(text)) for key, _, text in FORMAT_ROW.findall(response.text)]


def checked(response: Response) -> list[str]:
    return [key for key, on, _ in FORMAT_ROW.findall(response.text) if on]


def inputs(response: Response) -> dict[str, str]:
    """Every input but the format rows, as its name and value."""
    found = INPUT.findall(response.text)
    return {name: html.unescape(value) for name, value in found if name != "format"}


def warns(response: Response) -> list[str]:
    return [html.unescape(warn) for warn in WARN.findall(response.text)]


def a_form(number: str, tee: str, format_: str, closes: str = "2026-03-15T22:00") -> dict[str, str]:
    """Save round's fields, opening at the round's own Opens."""
    form = {"opens": "2026-03-02T09:00", "closes": closes, "format": format_}
    if number:
        form["number"] = number
    if tee:
        form["tee"] = tee
    return form


def last(database: Engine, season_id: str) -> StoredRound:
    return stored_rounds(database, season_id)[-1]


def test_r13_rounds_has_add_a_round_above_its_rows(admin: Admin) -> None:
    text = admin("t3-open").get("/admin/rounds").text
    assert ADD_A_ROUND in text
    assert text.index(ADD_A_ROUND) < text.index('href="/admin/rounds/1"')


def test_r13_new_round_form_lists_every_tee_and_format_at_its_defaults(admin: Admin) -> None:
    response = admin("t3-open").get("/admin/rounds/new")
    assert response.status_code == 200
    assert HEADING.findall(response.text) == ["Round 6"]
    assert inputs(response) == {"number": "6", "opens": "", "closes": ""}
    assert [(text, selected) for _, selected, text in options(response)] == [
        (tee, False) for tee in TEES
    ]
    assert ADD_A_TEE in response.text
    assert format_rows(response) == FORMAT_ROWS
    assert checked(response) == ["bestball"]
    assert FORM.findall(response.text) == ["/admin/rounds/new"]
    assert BACK.findall(response.text) == ["/admin/rounds"]
    assert warns(response) == []


@pytest.mark.parametrize(
    ("season_id", "draft", "number"),
    [
        pytest.param("no-rounds", None, 1, id="no-round"),
        pytest.param("t3-open", 9, 10, id="after-a-gap"),
    ],
)
def test_r13_new_round_is_numbered_after_the_highest_stored(
    admin: Admin, database: Engine, season_id: str, draft: int | None, number: int
) -> None:
    if draft is not None:
        tee = (BLUE_TEE.course, BLUE_TEE.name)
        setup = RoundSetup(season_id, draft, *tee, OPENS, CLOSES, DECISION_6, ScrambleFormat())
        create_round(database, setup)
    response = admin(season_id).get("/admin/rounds/new")
    assert HEADING.findall(response.text) == [f"Round {number}"]
    assert inputs(response)["number"] == str(number)


def test_r13_save_round_stores_a_draft_at_the_checked_formats_defaults(
    admin: Admin, database: Engine
) -> None:
    client = admin("t3-open")
    blue = tee_value(client.get("/admin/rounds/new"), TEES[1])
    response = client.post("/admin/rounds/new", data=a_form("6", blue, "scramble"))
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/rounds/6"
    stored = last(database, "t3-open")
    assert (stored.round.number, stored.state, stored.round.tee) == (6, "draft", BLUE_TEE)
    assert (stored.opens_at, stored.closes_at) == (OPENS, datetime(2026, 3, 15, 21, 0))
    assert stored.round.format == ScrambleFormat(35, 15)
    assert stored.round.contests == DECISION_6


def test_r14_a_draft_reads_as_the_form_filled_as_stored(admin: Admin, database: Engine) -> None:
    a_draft(database)
    response = admin("t3").get("/admin/rounds/6")
    assert HEADING.findall(response.text) == ["Round 6 &middot; Scramble"]
    assert inputs(response) == {"opens": "2026-03-02T09:00", "closes": "2026-03-15T22:00"}
    assert [(text, selected) for _, selected, text in options(response)] == [
        (TEES[0], False),
        (TEES[1], True),
        (TEES[2], False),
    ]
    assert ADD_A_TEE in response.text
    assert format_rows(response) == FORMAT_ROWS
    assert checked(response) == ["scramble"]
    assert FORM.findall(response.text) == ["/admin/rounds/6"]
    assert FIXED not in response.text
    assert fields(response) == []


def test_r14_save_round_changes_a_draft(admin: Admin, database: Engine) -> None:
    """Closes is in summer time, so a fixed offset from UTC would store it an hour out."""
    a_draft(database)
    client = admin("t3")
    white = tee_value(client.get("/admin/rounds/6"), TEES[2])
    form = a_form("", white, "greensome", closes="2026-04-12T22:00")
    response = client.post("/admin/rounds/6", data=form)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/rounds/6"
    stored = last(database, "t3")
    assert (stored.state, stored.round.tee) == ("draft", T3.rounds[0].tee)
    assert stored.round.format == GreensomeFormat(60, 40)
    assert stored.closes_at == datetime(2026, 4, 12, 20, 0)
    assert stored.round.contests == T3.rounds[2].contests
    assert inputs(client.get("/admin/rounds/6"))["closes"] == "2026-04-12T22:00"


def test_r16_save_round_stores_the_checked_formats_defaults(admin: Admin, database: Engine) -> None:
    """The draft is at 40 and 10, and decision 6 plays every round at the defaults."""
    a_draft(database)
    client = admin("t3")
    blue = tee_value(client.get("/admin/rounds/6"), TEES[1])
    client.post("/admin/rounds/6", data=a_form("", blue, "scramble"))
    assert last(database, "t3").round.format == ScrambleFormat(35, 15)


def test_r13_second_save_of_a_new_round_is_refused(admin: Admin, database: Engine) -> None:
    client = admin("t3-open")
    blue = tee_value(client.get("/admin/rounds/new"), TEES[1])
    client.post("/admin/rounds/new", data=a_form("6", blue, "scramble"))
    first = last(database, "t3-open")
    again = a_form("6", blue, "scramble", closes="2026-03-20T22:00")
    response = client.post("/admin/rounds/new", data=again)
    assert response.status_code == 400
    assert warns(response) == ["The season already has a round 6."]
    assert inputs(response)["closes"] == "2026-03-20T22:00"
    assert stored_rounds(database, "t3-open")[5:] == (first,)


@pytest.mark.parametrize("path", ["/admin/rounds/new", "/admin/rounds/6"])
@pytest.mark.parametrize(
    ("changed", "refusal"),
    [
        pytest.param({"opens": ""}, WINDOW, id="opens-empty"),
        pytest.param({"opens": "2026-03-02"}, WINDOW, id="opens-a-date-alone"),
        pytest.param({"tee": ""}, NO_TEE, id="no-tee"),
    ],
)
def test_r13_refused_save_shows_every_field_as_typed(
    admin: Admin, database: Engine, path: str, changed: dict[str, str], refusal: str
) -> None:
    """Every field differs from what the form opens with, so a redraw at the stored round or the
    defaults shows."""
    a_draft(database)
    client = admin("t3")
    white = tee_value(client.get("/admin/rounds/new"), TEES[2])
    typed = a_form("7", white, "foursome", closes="2026-03-20T22:00")
    form = typed | changed
    before = everything(database)
    response = client.post(path, data={name: value for name, value in form.items() if value})
    assert response.status_code == 400
    assert warns(response) == [refusal]
    assert (inputs(response)["opens"], inputs(response)["closes"]) == (
        form["opens"],
        "2026-03-20T22:00",
    )
    assert checked(response) == ["foursome"]
    selected = [text for _, on, text in options(response) if on]
    assert selected == ([TEES[2]] if form["tee"] else [])
    assert FORM.findall(response.text) == [path]
    assert everything(database) == before


def test_r13_a_course_holding_an_ampersand_and_a_slash_is_stored_through_its_option(
    admin: Admin, database: Engine
) -> None:
    tee = replace(T3.rounds[0].tee, course="Pebble & Spyglass / Links")
    create_tee(database, tee)
    client = admin("t3-open")
    shown = "Pebble & Spyglass / Links · White · par 72"
    value = tee_value(client.get("/admin/rounds/new"), shown)
    client.post("/admin/rounds/new", data=a_form("6", value, "bestball"))
    assert last(database, "t3-open").round.tee == tee


@pytest.mark.parametrize(("season_id", "number"), [("t3-open", 1), ("t3", 1), ("t3", 99)])
def test_r14_save_round_on_a_round_that_is_no_draft_opens_its_page(
    admin: Admin, database: Engine, season_id: str, number: int
) -> None:
    client = admin(season_id)
    white = tee_value(client.get("/admin/rounds/new"), TEES[2])
    before = everything(database)
    response = client.post(f"/admin/rounds/{number}", data=a_form("", white, "scramble"))
    assert response.status_code == 303
    assert response.headers["location"] == f"/admin/rounds/{number}"
    assert everything(database) == before


def test_r15_an_individual_seasons_save_round_is_refused(admin: Admin, database: Engine) -> None:
    client = admin("s9b")
    page = client.get("/admin/rounds/new")
    form = a_form(inputs(page)["number"], options(page)[0][0], "bestball")
    before = everything(database)
    response = client.post("/admin/rounds/new", data=form)
    assert response.status_code == 400
    assert warns(response) == ["an individual season's round has no format"]
    assert everything(database) == before


# The state card (S17d3).
# A Tuesday in winter, which no round's window or close shares, so a close shows when it was made.
NOW = datetime(2026, 2, 3, 19, 30)
STATE = re.compile(
    r'<span class="pill (pill--\w+)">(\w+)</span><span class="meta grow"[^>]*>([^<]+)</span>'
)
ACTION = re.compile(
    r'<form method="post" action="([^"]+)">'
    r'<button type="submit" class="btn btn--primary btn--block"[^>]*>([^<]+)</button></form>'
)
LINK = re.compile(r'<a class="btn (btn--\w+) btn--block"[^>]*href="([^"]+)">([^<]+)</a>')
LINE = re.compile(r'<p class="fine" style="margin:\d+px 0 0">([^<]+)</p>')
SETUP = re.compile(r'<p class="meta"[^>]*>([^<]+)</p>')
OPENING = "Opening lets players hand in cards and fixes the round's setup. It cannot be undone."
CLOSING = (
    "Closing makes the round count in the standings and shows every card to everyone. "
    "You can undo it."
)
UNDOING = (
    "Undoing the close takes the round out of the standings until it closes again, "
    "and players can hand in cards."
)
LATE = "A round with a late card stays closed."
ASK = "Open round 6 now? Players can hand in cards and the setup is fixed for good."


def state(response: Response) -> list[tuple[str, str, str]]:
    """The state card's row as its pill's colour, its state and the time beside it."""
    return [(pill, name, html.unescape(time)) for pill, name, time in STATE.findall(response.text)]


def actions(response: Response) -> list[tuple[str, str]]:
    return ACTION.findall(response.text)


def links(response: Response) -> list[tuple[str, str, str]]:
    return LINK.findall(response.text)


def lines(response: Response) -> list[str]:
    return [html.unescape(line) for line in LINE.findall(response.text)]


@pytest.fixture
def now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("league.web.admin_round.utc_now", lambda: NOW)


def test_r13_a_draft_reads_its_opens_and_open_round_as_a_link(
    admin: Admin, database: Engine
) -> None:
    a_draft(database)
    response = admin("t3").get("/admin/rounds/6")
    assert state(response) == [("pill--muted", "Draft", "Opens Mon 2 Mar, 09:00")]
    assert links(response) == [("btn--primary", "/admin/rounds/6/open", "Open round")]
    assert 'action="/admin/rounds/6/open"' not in response.text
    assert lines(response) == [OPENING]


def test_r13_open_round_asks_once_and_stores_nothing(admin: Admin, database: Engine) -> None:
    """The draft is at 40 and 10, and the setup line names its format alone."""
    a_draft(database)
    before = everything(database)
    response = admin("t3").get("/admin/rounds/6/open")
    assert response.status_code == 200
    assert everything(database) == before
    assert state(response) == [("pill--muted", "Draft", "Opens Mon 2 Mar, 09:00")]
    assert ASK in response.text
    assert [html.unescape(setup) for setup in SETUP.findall(response.text)] == [
        "Scramble · Trinity Forest Golf Club · Blue · Mon 2 Mar, 09:00 to Sun 15 Mar, 22:00"
    ]
    assert actions(response) == [("/admin/rounds/6/open", "Yes, open round 6")]
    assert links(response) == [("btn--ghost", "/admin/rounds/6", "Cancel")]
    assert lines(response) == []
    assert FORM.findall(response.text) == []
    assert fields(response) == []


def test_r13_yes_opens_the_draft_and_fixes_its_setup(admin: Admin, database: Engine) -> None:
    a_draft(database)
    client = admin("t3")
    response = client.post("/admin/rounds/6/open")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/rounds/6"
    assert last(database, "t3").state == "open"
    page = client.get("/admin/rounds/6")
    assert state(page) == [("pill--win", "Open", "Closes Sun 15 Mar, 22:00")]
    assert actions(page) == [("/admin/rounds/6/close", "Close round")]
    assert FIXED in page.text
    assert FORM.findall(page.text) == []


@pytest.mark.parametrize(("season_id", "number"), [("t3-open", 1), ("t3", 5), ("t3", 99)])
def test_r13_open_round_on_a_round_that_is_no_draft_opens_its_page(
    admin: Admin, database: Engine, season_id: str, number: int
) -> None:
    before = everything(database)
    response = admin(season_id).get(f"/admin/rounds/{number}/open")
    assert response.status_code == 303
    assert response.headers["location"] == f"/admin/rounds/{number}"
    assert everything(database) == before


def test_r13_an_open_round_reads_its_closes_and_close_round(admin: Admin) -> None:
    response = admin("t3-open").get("/admin/rounds/1")
    assert state(response) == [("pill--win", "Open", "Closes Sun 1 Feb, 22:00")]
    assert actions(response) == [("/admin/rounds/1/close", "Close round")]
    assert lines(response) == [CLOSING]


@pytest.mark.usefixtures("now")
def test_r13_close_round_records_closed_at(admin: Admin, database: Engine) -> None:
    client = admin("t3-open")
    response = client.post("/admin/rounds/1/close")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/rounds/1"
    closed = stored_rounds(database, "t3-open")[0]
    assert (closed.state, closed.round.closed_at) == ("closed", NOW)
    page = client.get("/admin/rounds/1")
    assert state(page) == [("pill--muted", "Closed", "Closed Tue 3 Feb, 20:30")]
    assert actions(page) == [("/admin/rounds/1/reopen", "Undo close")]
    assert lines(page) == [UNDOING]


def test_r13_undo_close_reopens_a_closed_round(admin: Admin, database: Engine) -> None:
    client = admin("t3")
    page = client.get("/admin/rounds/5")
    assert state(page) == [("pill--muted", "Closed", "Closed Mon 2 Feb, 23:00")]
    assert actions(page) == [("/admin/rounds/5/reopen", "Undo close")]
    response = client.post("/admin/rounds/5/reopen")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/rounds/5"
    reopened = stored_rounds(database, "t3")[4]
    assert (reopened.state, reopened.round.closed_at) == ("open", None)


def test_r13_a_closed_round_with_a_late_card_stays_closed(admin: Admin, database: Engine) -> None:
    """green's team card for round 4 came in after it closed."""
    client = admin("t3")
    page = client.get("/admin/rounds/4")
    assert actions(page) == []
    assert lines(page) == [LATE]
    before = everything(database)
    response = client.post("/admin/rounds/4/reopen")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/rounds/4"
    assert everything(database) == before


@pytest.mark.usefixtures("now")
@pytest.mark.parametrize(
    ("season_id", "number", "action"),
    [
        pytest.param("t3-open", 1, "open", id="open-an-open-round"),
        pytest.param("t3", 5, "open", id="open-a-closed-round"),
        pytest.param("t3", 6, "close", id="close-a-draft"),
        pytest.param("t3", 5, "close", id="close-a-closed-round"),
        pytest.param("t3", 6, "reopen", id="reopen-a-draft"),
        pytest.param("t3-open", 1, "reopen", id="reopen-an-open-round"),
        pytest.param("t3", 99, "open", id="open-no-round"),
        pytest.param("t3", 99, "close", id="close-no-round"),
        pytest.param("t3", 99, "reopen", id="reopen-no-round"),
    ],
)
def test_r13_an_action_the_state_does_not_allow_stores_nothing(
    admin: Admin, database: Engine, season_id: str, number: int, action: str
) -> None:
    a_draft(database)
    client = admin(season_id)
    before = everything(database)
    response = client.post(f"/admin/rounds/{number}/{action}")
    assert response.status_code == 303
    assert response.headers["location"] == f"/admin/rounds/{number}"
    assert everything(database) == before


def test_r13_a_new_rounds_form_has_no_state_card(admin: Admin) -> None:
    assert "card--mine" not in admin("t3").get("/admin/rounds/new").text
