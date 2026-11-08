import html
import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from test_admin import (
    INPUT,
    NOTICE,
    OPEN_YOUR_ADMIN_LINK,
    Visitor,
    a_player,
    a_wrong_cookie,
    nav,
    no_cookie,
    warns,
)
from test_app import ADMIN_TOKEN, an_app

from fixtures.database import everything, golden_database
from fixtures.team_season import SEASON as T3
from league.domain.facts import BaySetting, SeasonFacts, StandingsRule
from league.domain.index import PROPOSED_INDEX_RULE
from league.services.runtime import open_database
from league.services.setup import create_player, create_season, stored_season

NEW = "Winter Tour 26/27"
# Drawn in docs/design/admin-season.html, in the roster's id order.
PLAYERS = ["Daniel", "Henrik", "Inge", "Jens", "Mats", "Terje"]
GOLFBOX = ["8.6", "15.7", "1.1", "0.2", "15.4", "12.0"]
SEEDS = {"Daniel": 60, "Henrik": 110, "Inge": 8, "Jens": 1, "Mats": 108, "Terje": 84}
TEAMS = ["Daniel & Henrik", "Jens & Terje", "Inge & Mats"]
FIRSTS = ["Daniel", "Jens", "Inge"]
SECONDS = ["Henrik", "Terje", "Mats"]
LINES = T3.bay_settings
DESIGN: dict[str, Any] = {
    "best_n": "9",
    "player": PLAYERS,
    "golfbox": GOLFBOX,
    "team": TEAMS,
    "first": FIRSTS,
    "second": SECONDS,
    "menu": [line.menu for line in LINES],
    "setting": [line.setting for line in LINES],
    "value": [line.value for line in LINES],
}
SELECT = re.compile(r'<select [^>]*name="(first|second)"[^>]*>(.*?)</select>')
SELECTED = re.compile(r'<option value="([^"]*)" selected>')
SUBMIT = re.compile(r'<button [^>]*type="submit"[^>]*>([^<]+)</button>')
BUTTON = re.compile(r'<button ([^>]*type="submit"[^>]*)>')
NAME_AND_VALUE = re.compile(r'name="([^"]*)" value="([^"]*)"')
UNSEEN = (
    'style="position:absolute;width:1px;height:1px;padding:0;border:0;overflow:hidden;'
    'clip-path:inset(50%);white-space:nowrap"'
)
BEST_N = re.compile(r"Best rounds count</div><div>([^<]+)</div>")
PLAYER_ROW = re.compile(
    r'<a style="font-size:14px" href="/admin/players/link\?player=[^"]*">([^<]+)</a>'
    r'<span[^>]*>([^<]+)</span><span class="meta">([^<]*)</span>'
)
TEAM_ROW = re.compile(
    r'grid-template-columns:1.4fr 2fr"><span[^>]*>([^<]+)</span><span class="meta">([^<]+)</span>'
)
LINE_ROW = re.compile(
    r'grid-template-columns:.7fr 1fr 2.2fr"><span class="meta">([^<]*)</span>'
    r'<span class="meta">([^<]*)</span><span[^>]*>([^<]*)</span>'
)

Opened = Callable[[str], TestClient]


def an_admin(app: FastAPI) -> TestClient:
    client = TestClient(app, follow_redirects=False)
    client.get(f"/admin/k/{ADMIN_TOKEN}")
    return client


@pytest.fixture
def fresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[FastAPI]:
    """A deployment whose season nobody stored, on a database holding the design's players."""
    engine = open_database(tmp_path / "league.db")
    for player_id in reversed(PLAYERS):
        create_player(engine, player_id)
    engine.dispose()
    app = an_app(monkeypatch, tmp_path / "league.db", NEW)
    yield app
    app.state.engine.dispose()


@pytest.fixture
def admin(fresh: FastAPI) -> TestClient:
    return an_admin(fresh)


@pytest.fixture
def golden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Opened]:
    """Opens the admin's browser on one golden season."""
    golden_database(tmp_path).dispose()
    apps: list[FastAPI] = []

    def opened(season_id: str) -> TestClient:
        apps.append(an_app(monkeypatch, tmp_path / "league.db", season_id))
        return an_admin(apps[-1])

    yield opened
    for app in apps:
        app.state.engine.dispose()


def inputs(response: Response, name: str) -> list[str]:
    return [html.unescape(value) for field, value in INPUT.findall(response.text) if field == name]


def chosen(response: Response, name: str) -> list[str]:
    """What each select of that name has selected, empty where it has nothing."""
    return [
        html.unescape(next(iter(SELECTED.findall(options)), ""))
        for field, options in SELECT.findall(response.text)
        if field == name
    ]


def rows(pattern: re.Pattern[str], response: Response) -> list[tuple[str, ...]]:
    return [tuple(html.unescape(cell) for cell in row) for row in pattern.findall(response.text)]


def a_form(**changes: Any) -> dict[str, Any]:
    return {**DESIGN, **changes}


def test_the_form_lists_every_stored_player_with_three_team_rows_and_one_line(
    admin: TestClient,
) -> None:
    response = admin.get("/admin/season")
    assert response.status_code == 200
    assert inputs(response, "player") == PLAYERS
    assert inputs(response, "golfbox") == [""] * 6
    assert inputs(response, "team") == [""] * 3
    assert chosen(response, "first") == [""] * 3
    assert inputs(response, "menu") == [""]
    assert html.unescape(NEW) in html.unescape(response.text)
    assert warns(response) == []


def test_decision_1_the_designs_season_is_stored_as_a_team_season(
    fresh: FastAPI, admin: TestClient
) -> None:
    response = admin.post("/admin/season", data=DESIGN)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/season"
    assert stored_season(fresh.state.engine, NEW) == SeasonFacts(
        rounds=(),
        seed_index_tenths=SEEDS,
        provisional=frozenset(),
        index_rule=PROPOSED_INDEX_RULE,
        standings_rule=StandingsRule(best_n=9),
        teams=dict(zip(FIRSTS + SECONDS, TEAMS * 2, strict=True)),
        mode="team",
        bay_settings=LINES,
    )


def test_the_stored_season_reads_back_with_no_input_and_no_save(admin: TestClient) -> None:
    admin.post("/admin/season", data=DESIGN)
    response = admin.get("/admin/season")
    assert BEST_N.findall(response.text) == ["9"]
    assert rows(PLAYER_ROW, response) == [
        ("Daniel", "6.0", "Daniel & Henrik"),
        ("Henrik", "11.0", "Daniel & Henrik"),
        ("Inge", "0.8", "Inge & Mats"),
        ("Jens", "0.1", "Jens & Terje"),
        ("Mats", "10.8", "Inge & Mats"),
        ("Terje", "8.4", "Jens & Terje"),
    ]
    assert rows(TEAM_ROW, response) == [
        ("Daniel & Henrik", "Daniel & Henrik"),
        ("Inge & Mats", "Inge & Mats"),
        ("Jens & Terje", "Jens & Terje"),
    ]
    assert tuple(BaySetting(*row) for row in rows(LINE_ROW, response)) == LINES
    assert INPUT.findall(response.text) == []
    assert SUBMIT.findall(response.text) == []
    assert "two players each" not in response.text


def test_an_empty_best_n_counts_every_round_and_a_comma_is_a_decimal_mark(
    fresh: FastAPI, admin: TestClient
) -> None:
    admin.post("/admin/season", data=a_form(best_n=" ", golfbox=["8,6", *GOLFBOX[1:]]))
    facts = stored_season(fresh.state.engine, NEW)
    assert facts is not None
    assert facts.standings_rule == StandingsRule()
    assert facts.seed_index_tenths["Daniel"] == 60
    assert BEST_N.findall(admin.get("/admin/season").text) == ["Every round"]


def test_a_plus_golfbox_handicap_is_a_plus_handicap(fresh: FastAPI, admin: TestClient) -> None:
    admin.post("/admin/season", data=a_form(golfbox=["+1.2", "+0.5", *GOLFBOX[2:]]))
    facts = stored_season(fresh.state.engine, NEW)
    assert facts is not None
    assert facts.seed_index_tenths["Daniel"] == -8
    assert facts.seed_index_tenths["Henrik"] == -3


def test_a_player_without_a_golfbox_handicap_or_team_is_not_in_the_season(
    fresh: FastAPI, admin: TestClient
) -> None:
    left_out = ["8.6", "15.7", "", "0.2", "", "12.0"]
    form = a_form(golfbox=left_out, team=[*TEAMS[:2], ""], first=[*FIRSTS[:2], ""])
    form["second"] = [*SECONDS[:2], ""]
    assert admin.post("/admin/season", data=form).status_code == 303
    facts = stored_season(fresh.state.engine, NEW)
    assert facts is not None
    assert set(facts.seed_index_tenths) == {"Daniel", "Henrik", "Jens", "Terje"}
    assert set(facts.teams) == {"Daniel", "Henrik", "Jens", "Terje"}


def assert_as_typed(response: Response, form: dict[str, Any]) -> None:
    """Every kind of field reads back as the form held it."""
    assert inputs(response, "best_n") == [form["best_n"]]
    assert inputs(response, "golfbox") == form["golfbox"]
    assert inputs(response, "team") == form["team"]
    assert chosen(response, "first") == form["first"]
    assert chosen(response, "second") == form["second"]
    assert inputs(response, "menu") == form["menu"]
    assert inputs(response, "setting") == form["setting"]
    assert inputs(response, "value") == form["value"]


GOLFBOX_REFUSED = "A Golfbox handicap is a number with one decimal, such as 8.6."


@pytest.mark.parametrize(
    ("changes", "refusal"),
    [
        ({"golfbox": ["8.62", *GOLFBOX[1:]]}, GOLFBOX_REFUSED),
        ({"golfbox": ["abc", *GOLFBOX[1:]]}, GOLFBOX_REFUSED),
        ({"golfbox": ["nan", *GOLFBOX[1:]]}, GOLFBOX_REFUSED),
        ({"golfbox": ["-1.2", *GOLFBOX[1:]]}, GOLFBOX_REFUSED),
        ({"golfbox": ["86", *GOLFBOX[1:]]}, "the seed index of Daniel is not -5.0 to 54.0"),
        ({"golfbox": ["1e20", *GOLFBOX[1:]]}, "the seed index of Daniel is not -5.0 to 54.0"),
        ({"best_n": "0"}, "best_n is 1 or more"),
        ({"best_n": "x"}, "Best rounds count is a whole number."),
        (
            {"team": [*TEAMS[:2], ""], "first": [*FIRSTS[:2], ""], "second": [*SECONDS[:2], ""]},
            "seeded player Inge is in no team",
        ),
        ({"second": [*SECONDS[:2], ""]}, "A team has a name and two players."),
        ({"team": [*TEAMS[:2], " "]}, "A team has a name and two players."),
        ({"second": [*SECONDS[:2], "Inge"]}, "A team has a name and two players."),
        ({"first": ["Daniel", "Jens", "Daniel"]}, "Daniel is in two teams."),
        ({"team": [*TEAMS[:2], "Mats"]}, "no team's id is a seeded player's id"),
        ({"golfbox": [*GOLFBOX[:5], ""]}, "Terje is not in the season."),
        (
            {"golfbox": [""] * 6, "team": [""] * 3, "first": [""] * 3, "second": [""] * 3},
            "A season has at least one team.",
        ),
    ],
)
def test_a_refused_save_keeps_every_field_as_typed_and_stores_nothing(
    fresh: FastAPI, admin: TestClient, changes: dict[str, Any], refusal: str
) -> None:
    before = everything(fresh.state.engine)
    form = a_form(**changes)
    response = admin.post("/admin/season", data=form)
    assert response.status_code == 400
    assert warns(response) == [refusal]
    assert everything(fresh.state.engine) == before
    assert_as_typed(response, form)


def test_enter_in_a_field_presses_the_first_submit_button_which_stores_nothing(
    fresh: FastAPI, admin: TestClient
) -> None:
    """Enter submits the form with its first submit button, and a stored season cannot be saved
    again, so that button only redraws the form as typed."""
    page = admin.get("/admin/season").text
    assert SUBMIT.findall(page)[:2] == ["Redraw", "Save season"]
    first = BUTTON.findall(page)[0]
    assert 'form="season"' in first
    assert UNSEEN in first
    assert 'tabindex="-1"' in first
    name, value = NAME_AND_VALUE.findall(first)[0]
    before = everything(fresh.state.engine)
    form = a_form(golfbox=["abc", *GOLFBOX[1:]])
    response = admin.post("/admin/season", data={**form, name: value})
    assert response.status_code == 200
    assert everything(fresh.state.engine) == before
    assert warns(response) == []
    assert_as_typed(response, form)
    response = admin.post("/admin/season", data={**DESIGN, name: value})
    assert stored_season(fresh.state.engine, NEW) is None
    assert_as_typed(response, DESIGN)


def test_save_season_once_the_season_is_stored_is_refused(
    fresh: FastAPI, admin: TestClient
) -> None:
    admin.post("/admin/season", data=DESIGN)
    before = everything(fresh.state.engine)
    form = a_form(best_n="8")
    response = admin.post("/admin/season", data=form)
    assert response.status_code == 400
    assert warns(response) == [f"season {NEW} is already stored"]
    assert everything(fresh.state.engine) == before
    assert_as_typed(response, form)


def test_add_a_line_redraws_the_form_with_an_empty_line_and_stores_nothing(
    fresh: FastAPI, admin: TestClient
) -> None:
    before = everything(fresh.state.engine)
    response = admin.post("/admin/season", data=a_form(add="line"))
    assert response.status_code == 200
    assert everything(fresh.state.engine) == before
    assert inputs(response, "menu") == [*DESIGN["menu"], ""]
    assert inputs(response, "golfbox") == GOLFBOX
    # A field in error is kept as typed and not refused, since nothing is saved.
    response = admin.post("/admin/season", data=a_form(add="line", golfbox=["abc", *GOLFBOX[1:]]))
    assert response.status_code == 200
    assert inputs(response, "golfbox")[0] == "abc"
    assert warns(response) == []


def test_removing_the_second_of_three_lines_keeps_the_first_and_third(
    fresh: FastAPI, admin: TestClient
) -> None:
    before = everything(fresh.state.engine)
    form = a_form(menu=["A", "B", "C"], setting=["a", "b", "c"], value=["1", "2", "3"], remove="1")
    response = admin.post("/admin/season", data=form)
    assert response.status_code == 200
    assert everything(fresh.state.engine) == before
    assert inputs(response, "menu") == ["A", "C"]
    assert inputs(response, "value") == ["1", "3"]


def test_t3_reads_back_its_players_in_id_order_and_its_teams_in_team_id_order(
    golden: Opened,
) -> None:
    response = golden("t3").get("/admin/season")
    assert response.status_code == 200
    assert BEST_N.findall(response.text) == ["4"]
    assert PLAYER_ROW.findall(response.text) == [
        ("ann", "2.0", "red"),
        ("bob", "10.0", "red"),
        ("cam", "4.0", "blue"),
        ("dee", "16.0", "blue"),
        ("eve", "6.0", "green"),
        ("fay", "12.0", "green"),
        ("gus", "8.0", "gold"),
        ("hal", "18.0", "gold"),
    ]
    # team_members gives red, blue, green and gold, in the order of each team's first player.
    assert rows(TEAM_ROW, response) == [
        ("blue", "cam & dee"),
        ("gold", "gus & hal"),
        ("green", "eve & fay"),
        ("red", "ann & bob"),
    ]
    assert tuple(BaySetting(*row) for row in rows(LINE_ROW, response)) == T3.bay_settings


def test_s9b_reads_back_its_teams_of_three(golden: Opened) -> None:
    response = golden("s9b").get("/admin/season")
    assert rows(TEAM_ROW, response) == [("east", "ann & bob & cam"), ("west", "dee & eve & fay")]


def test_section_7_the_seed_share_reads_back_in_a_team_season_only(golden: Opened) -> None:
    share = "of each player's Golfbox handicap"
    assert share in html.unescape(golden("t3").get("/admin/season").text)
    assert share not in html.unescape(golden("s9b").get("/admin/season").text)


def test_a_season_seeded_out_of_id_order_reads_back_in_id_order(
    fresh: FastAPI, admin: TestClient
) -> None:
    facts = replace(
        T3,
        rounds=(),
        seed_index_tenths=dict(sorted(T3.seed_index_tenths.items(), reverse=True)),
    )
    for player_id in T3.seed_index_tenths:
        create_player(fresh.state.engine, player_id)
    create_season(fresh.state.engine, NEW, facts)
    rows = PLAYER_ROW.findall(admin.get("/admin/season").text)
    assert [player for player, _, _ in rows] == sorted(T3.seed_index_tenths)


def test_season_setup_has_the_nav_with_season_marked(admin: TestClient) -> None:
    expected = [
        ("Season", "/admin/season", True),
        ("Players", "/admin/players", False),
        ("Courses", "/admin/tees", False),
    ]
    assert nav(admin.get("/admin/season")) == expected
    assert nav(admin.post("/admin/season", data=a_form(best_n="x"))) == expected
    admin.post("/admin/season", data=DESIGN)
    assert nav(admin.get("/admin/season")) == expected


@pytest.mark.parametrize("visitor", [no_cookie, a_player, a_wrong_cookie])
def test_season_routes_refuse_a_visit_without_the_admin_cookie(
    fresh: FastAPI, visitor: Visitor
) -> None:
    before = everything(fresh.state.engine)
    browser = visitor(TestClient(fresh, follow_redirects=False))
    for response in (
        browser.get("/admin/season"),
        browser.post("/admin/season", data=DESIGN),
        browser.post("/admin/season", data=a_form(add="line")),
    ):
        assert response.status_code == 401
        assert NOTICE.findall(response.text) == [OPEN_YOUR_ADMIN_LINK]
    assert everything(fresh.state.engine) == before
