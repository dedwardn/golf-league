import html
import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime
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

from fixtures.database import a_copy, a_template
from fixtures.team_season import SEASON as T3
from fixtures.team_season import t3_open
from league.domain.configs import ScrambleFormat
from league.services.setup import RoundSetup, create_round

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
FIXED = "A round&#39;s setup is fixed once it opens."
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


def test_r14_a_draft_reads_its_own_setup_and_is_not_fixed(admin: Admin, database: Engine) -> None:
    a_draft(database)
    response = admin("t3").get("/admin/rounds/6")
    assert fields(response) == [
        ("Course and tee", "Trinity Forest Golf Club · Blue · par 72"),
        ("Opens", "Mon 2 Mar, 09:00"),
        ("Closes", "Sun 15 Mar, 22:00"),
        ("Format", "Scramble"),
        ("Handicap allowance", "40% lower, 10% higher"),
    ]
    assert FIXED not in response.text


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
    browse: Callable[[str], TestClient], visitor: Visitor
) -> None:
    browser = visitor(browse("t3"))
    for path in ("/admin/rounds", "/admin/rounds/1"):
        response = browser.get(path)
        assert response.status_code == 401
        assert NOTICE.findall(response.text) == [OPEN_YOUR_ADMIN_LINK]


def test_rounds_and_a_round_have_the_nav_with_rounds_marked(admin: Admin) -> None:
    client = admin("t3")
    for path in ("/admin/rounds", "/admin/rounds/1"):
        assert nav(client.get(path)) == the_nav("Rounds")
