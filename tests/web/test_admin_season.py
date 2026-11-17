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
from sqlalchemy import Engine
from test_admin import (
    INPUT,
    NOTICE,
    OPEN_YOUR_ADMIN_LINK,
    Visitor,
    a_player,
    a_wrong_cookie,
    nav,
    no_cookie,
    the_nav,
    warns,
)
from test_app import ADMIN_TOKEN, an_app

from fixtures.database import everything, golden_database, save_whole_season
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from fixtures.team_season import t3_first
from league.domain.facts import BaySetting, SeasonFacts, StandingsRule
from league.domain.index import PROPOSED_INDEX_RULE
from league.services.runtime import open_database
from league.services.setup import (
    change_bay_settings,
    create_player,
    create_season,
    stored_season,
)

NEW = "Winter Tour 26/27"
# Drawn in docs/design/admin-season.html, in the roster's id order.
PLAYERS = ["Daniel", "Henrik", "Inge", "Jens", "Mats", "Terje"]
GOLFBOX = ["8.6", "15.7", "1.1", "0.2", "15.4", "12.0"]
SEEDS = {"Daniel": 60, "Henrik": 110, "Inge": 8, "Jens": 1, "Mats": 108, "Terje": 84}
TEAMS = ["Daniel & Henrik", "Jens & Terje", "Inge & Mats"]
FIRSTS = ["Daniel", "Jens", "Inge"]
SECONDS = ["Henrik", "Terje", "Mats"]
LINES = T3.bay_settings
Menus = list[tuple[str, list[tuple[str, str]]]]
# T3's lines, written Game first and then Course, as their sections.
MENUS: Menus = [
    (menu, [(line.setting, line.value) for line in LINES if line.menu == menu])
    for menu in ("Game", "Course")
]


def bay_fields(menus: Menus) -> dict[str, list[str]]:
    """The bay settings card's fields as a browser posts them: each section's name, and each
    line's section, setting and value."""
    lines = [
        (str(n), setting, value) for n, (_, held) in enumerate(menus) for setting, value in held
    ]
    return {
        "menu": [name for name, _ in menus],
        "line_menu": [line[0] for line in lines],
        "setting": [line[1] for line in lines],
        "value": [line[2] for line in lines],
    }


DESIGN: dict[str, Any] = {
    "best_n": "9",
    "player": PLAYERS,
    "golfbox": GOLFBOX,
    "team": TEAMS,
    "first": FIRSTS,
    "second": SECONDS,
    **bay_fields(MENUS),
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
# A correctable row has its hidden player input between the name and the league index, and its
# Golfbox input and Correct after it. No row has a cell for the team.
PLAYER_ROW = re.compile(
    r'<a style="font-size:14px" href="/admin/players/link\?player=[^"]*">([^<]+)</a>'
    r'(?:<input [^>]*>)?<span[^>]*>([^<]+)</span>(?=<input class="input"[^>]*><button|</div>)'
)
PLAYERS_HEAD = re.compile(r'<div class="tablehead" style="([^"]*)">((?:<span>[^<]*</span>)+)</div>')
PLAYERS_ROW_STYLE = re.compile(r'class="tablerow" style="([^"]*)"[^>]*><a style="font-size:14px"')
TEAM_ROW = re.compile(
    r'grid-template-columns:1.4fr 2fr"><span[^>]*>([^<]+)</span><span class="meta">([^<]+)</span>'
)
BAY_FORM = re.compile(r'<form [^>]*action="/admin/season/bay"[^>]*>(.*?)</form>', re.DOTALL)
FIXED = "League indexes are fixed once a round is closed."
HINTS = re.compile(r'name="(menu|setting|value)"(?: value="[^"]*")? placeholder="([^"]+)"')
TEXTAREA = re.compile(r'<textarea [^>]*name="([^"]+)"[^>]*>([^<]*)</textarea>')
# A box the admin types in, as against a hidden input that carries a name read as text.
BOX = re.compile(r'<input class="input"[^>]*name="([^"]+)"')
SETTING_TEXT = re.compile(
    r'<input type="hidden" name="setting" value="[^"]*"><span class="grow"[^>]*>([^<]+)</span>'
)
MENU_TEXT = re.compile(
    r'<input type="hidden" name="menu" value="[^"]*"><span class="label grow"[^>]*>([^<]+)</span>'
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
    engine = golden_database(tmp_path)
    with engine.begin() as connection:
        save_whole_season(connection, "t3-first", t3_first())
    engine.dispose()
    apps: list[FastAPI] = []

    def opened(season_id: str) -> TestClient:
        apps.append(an_app(monkeypatch, tmp_path / "league.db", season_id))
        return an_admin(apps[-1])

    yield opened
    for app in apps:
        app.state.engine.dispose()


@pytest.fixture
def golden_engine(golden: Opened, tmp_path: Path) -> Iterator[Engine]:
    """The golden database the admin's browser opens, for what it stored."""
    engine = open_database(tmp_path / "league.db")
    yield engine
    engine.dispose()


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


def values(response: Response) -> list[str]:
    return [
        html.unescape(text) for field, text in TEXTAREA.findall(response.text) if field == "value"
    ]


def boxes(response: Response) -> list[str]:
    return BOX.findall(response.text)


def sections(response: Response) -> Menus:
    """The bay settings card's sections, each its menu's name and its lines, as drawn."""
    drawn: Menus = [(name, []) for name in inputs(response, "menu")]
    lines = zip(
        inputs(response, "line_menu"), inputs(response, "setting"), values(response), strict=True
    )
    for menu, setting, value in lines:
        drawn[int(menu)][1].append((setting, value))
    return drawn


def stored_lines(response: Response) -> tuple[BaySetting, ...]:
    """The bay lines a read-back's bay form holds."""
    return tuple(
        BaySetting(menu, setting, value)
        for menu, held in sections(response)
        for setting, value in held
    )


def test_the_form_lists_every_stored_player_with_three_team_rows_and_one_line(
    admin: TestClient,
) -> None:
    response = admin.get("/admin/season")
    assert response.status_code == 200
    assert inputs(response, "player") == PLAYERS
    assert inputs(response, "golfbox") == [""] * 6
    assert inputs(response, "team") == [""] * 3
    assert chosen(response, "first") == [""] * 3
    assert sections(response) == [("", [("", "")])]
    assert boxes(response).count("menu") == 1
    assert boxes(response).count("setting") == 1
    # A menu left unnamed shows, since each empty box says which name it takes.
    assert HINTS.findall(response.text) == [
        ("menu", "Menu"),
        ("setting", "Setting"),
        ("value", "Value"),
    ]
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


def test_the_stored_season_reads_back_with_no_save_season(admin: TestClient) -> None:
    admin.post("/admin/season", data=DESIGN)
    response = admin.get("/admin/season")
    assert BEST_N.findall(response.text) == ["9"]
    assert rows(PLAYER_ROW, response) == [
        ("Daniel", "6.0"),
        ("Henrik", "11.0"),
        ("Inge", "0.8"),
        ("Jens", "0.1"),
        ("Mats", "10.8"),
        ("Terje", "8.4"),
    ]
    assert rows(TEAM_ROW, response) == [
        ("Daniel & Henrik", "Daniel & Henrik"),
        ("Inge & Mats", "Inge & Mats"),
        ("Jens & Terje", "Jens & Terje"),
    ]
    assert stored_lines(response) == LINES
    assert "Save season" not in SUBMIT.findall(response.text)
    assert inputs(response, "golfbox") == [""] * 6
    assert inputs(response, "player") == PLAYERS
    assert SUBMIT.findall(response.text).count("Correct") == 6
    assert response.text.count('action="/admin/season/index"') == 6
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
    assert inputs(response, "line_menu") == form["line_menu"]
    assert inputs(response, "setting") == form["setting"]
    assert values(response) == form["value"]


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


GAME, COURSE = MENUS
NEW_LINE = ("", "")


@pytest.mark.parametrize(
    ("add", "drawn"),
    [
        ("0", [(GAME[0], [*GAME[1], NEW_LINE]), COURSE]),
        ("1", [GAME, (COURSE[0], [*COURSE[1], NEW_LINE])]),
    ],
)
def test_section_7_add_a_setting_adds_an_empty_line_to_its_own_menu_and_stores_nothing(
    fresh: FastAPI, admin: TestClient, add: str, drawn: Menus
) -> None:
    before = everything(fresh.state.engine)
    response = admin.post("/admin/season", data=a_form(add=add))
    assert response.status_code == 200
    assert everything(fresh.state.engine) == before
    assert sections(response) == drawn
    assert boxes(response).count("setting") == 1
    assert inputs(response, "golfbox") == GOLFBOX
    # A field in error is kept as typed and not refused, since nothing is saved.
    response = admin.post("/admin/season", data=a_form(add=add, golfbox=["abc", *GOLFBOX[1:]]))
    assert response.status_code == 200
    assert inputs(response, "golfbox")[0] == "abc"
    assert warns(response) == []


def test_section_7_add_a_menu_adds_an_unnamed_menu_with_one_empty_line_and_stores_nothing(
    fresh: FastAPI, admin: TestClient
) -> None:
    before = everything(fresh.state.engine)
    response = admin.post("/admin/season", data=a_form(add_menu="menu"))
    assert response.status_code == 200
    assert everything(fresh.state.engine) == before
    assert sections(response) == [*MENUS, ("", [NEW_LINE])]
    assert boxes(response).count("menu") == 1
    assert boxes(response).count("setting") == 1


@pytest.mark.parametrize(
    ("remove", "drawn"),
    [
        ("0-1", [(GAME[0], [GAME[1][0], GAME[1][2]]), COURSE]),
        ("1-1", [GAME, (COURSE[0], [COURSE[1][0], *COURSE[1][2:]])]),
    ],
)
def test_section_7_removing_a_line_keeps_the_others_of_its_menu(
    fresh: FastAPI, admin: TestClient, remove: str, drawn: Menus
) -> None:
    before = everything(fresh.state.engine)
    response = admin.post("/admin/season", data=a_form(remove=remove))
    assert response.status_code == 200
    assert everything(fresh.state.engine) == before
    assert sections(response) == drawn


def test_section_7_a_typed_name_reads_as_text_once_redrawn(
    fresh: FastAPI, admin: TestClient
) -> None:
    typed = [*MENUS, ("Weather", [("Rain", "None")])]
    response = admin.post("/admin/season", data={**a_form(**bay_fields(typed)), "redraw": "form"})
    assert response.status_code == 200
    assert sections(response) == typed
    assert MENU_TEXT.findall(response.text) == ["Game", "Course", "Weather"]
    assert SETTING_TEXT.findall(response.text)[-1] == "Rain"
    assert "menu" not in boxes(response)
    assert "setting" not in boxes(response)


def test_t3_reads_back_its_players_in_id_order_and_its_teams_in_team_id_order(
    golden: Opened,
) -> None:
    response = golden("t3").get("/admin/season")
    assert response.status_code == 200
    assert BEST_N.findall(response.text) == ["4"]
    assert PLAYER_ROW.findall(response.text) == [
        ("ann", "2.0"),
        ("bob", "10.0"),
        ("cam", "4.0"),
        ("dee", "16.0"),
        ("eve", "6.0"),
        ("fay", "12.0"),
        ("gus", "8.0"),
        ("hal", "18.0"),
    ]
    # team_members gives red, blue, green and gold, in the order of each team's first player.
    assert rows(TEAM_ROW, response) == [
        ("blue", "cam & dee"),
        ("gold", "gus & hal"),
        ("green", "eve & fay"),
        ("red", "ann & bob"),
    ]
    assert stored_lines(response) == T3.bay_settings


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
    assert [player for player, _ in rows] == sorted(T3.seed_index_tenths)


def test_season_setup_has_the_nav_with_season_marked_and_rounds_in_its_topbar(
    admin: TestClient,
) -> None:
    form = admin.get("/admin/season")
    refused = admin.post("/admin/season", data=a_form(best_n="x"))
    admin.post("/admin/season", data=DESIGN)
    for response in (form, refused, admin.get("/admin/season")):
        assert nav(response) == the_nav("Season")
        assert '<a class="btn btn--ghost" href="/admin/rounds">Rounds</a>' in response.text


@pytest.mark.parametrize("visitor", [no_cookie, a_player, a_wrong_cookie])
def test_season_routes_refuse_a_visit_without_the_admin_cookie(
    fresh: FastAPI, visitor: Visitor
) -> None:
    before = everything(fresh.state.engine)
    browser = visitor(TestClient(fresh, follow_redirects=False))
    for response in (
        browser.get("/admin/season"),
        browser.post("/admin/season", data=DESIGN),
        browser.post("/admin/season", data=a_form(add="0")),
        browser.post("/admin/season/index", data={"player": "Daniel", "golfbox": "9.4"}),
        browser.post("/admin/season/bay", data=a_form()),
    ):
        assert response.status_code == 401
        assert NOTICE.findall(response.text) == [OPEN_YOUR_ADMIN_LINK]
    assert everything(fresh.state.engine) == before


READ_BACK = {"Daniel": "6.0", "Henrik": "11.0", "Inge": "0.8", "Jens": "0.1", "Mats": "10.8"}
READ_BACK["Terje"] = "8.4"


def indexes(response: Response) -> dict[str, str]:
    return {player: index for player, index in rows(PLAYER_ROW, response)}


@pytest.mark.parametrize(
    ("player", "golfbox", "shown"),
    [
        ("Daniel", "9.4", "6.6"),
        ("Terje", "13.5", "9.5"),
        ("Daniel", " +1.2 ", "-0.8"),
        ("Daniel", "9,4", "6.6"),
    ],
)
def test_decision_1_a_league_index_is_corrected_by_a_golfbox_handicap(
    admin: TestClient, player: str, golfbox: str, shown: str
) -> None:
    """13.5 gives 9.45, an exact half, which rounds up."""
    admin.post("/admin/season", data=DESIGN)
    response = admin.post("/admin/season/index", data={"player": player, "golfbox": golfbox})
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/season"
    assert indexes(admin.get("/admin/season")) == {**READ_BACK, player: shown}


@pytest.mark.parametrize(
    ("golfbox", "refusal"),
    [
        ("", GOLFBOX_REFUSED),
        ("abc", GOLFBOX_REFUSED),
        ("8.62", GOLFBOX_REFUSED),
        ("-1.2", GOLFBOX_REFUSED),
        ("86", "the seed index of Henrik is not -5.0 to 54.0"),
    ],
)
def test_a_refused_correction_keeps_that_row_as_typed_and_stores_nothing(
    fresh: FastAPI, admin: TestClient, golfbox: str, refusal: str
) -> None:
    admin.post("/admin/season", data=DESIGN)
    before = everything(fresh.state.engine)
    response = admin.post("/admin/season/index", data={"player": "Henrik", "golfbox": golfbox})
    assert response.status_code == 400
    assert warns(response) == [refusal]
    assert everything(fresh.state.engine) == before
    assert inputs(response, "golfbox") == ["", golfbox, "", "", "", ""]
    assert indexes(response) == READ_BACK
    assert stored_lines(response) == LINES


def players_card(response: Response) -> tuple[list[str], str, list[str]]:
    """The Players card's header labels, the header's column template and each row's."""
    [(style, labels)] = [
        head for head in PLAYERS_HEAD.findall(response.text) if "<span>Player</span>" in head[1]
    ]
    shown = re.findall(r"<span>([^<]*)</span>", labels)
    return shown, style, PLAYERS_ROW_STYLE.findall(response.text)


@pytest.mark.parametrize(
    ("season", "labels", "players"),
    [
        ("t3-first", ["Player", "League index", "Golfbox", ""], 8),
        ("t3", ["Player", "League index"], 8),
        ("s9b", ["Player", "League index"], 6),
    ],
)
def test_section_7_the_read_backs_players_have_no_team_and_line_up_with_their_header(
    golden: Opened, season: str, labels: list[str], players: int
) -> None:
    """The Teams card shows the teams. Every column after Player has a fixed width, so an empty
    header cell cannot be narrower than the cells under it."""
    shown, style, row_styles = players_card(golden(season).get("/admin/season"))
    assert shown == labels
    assert row_styles == [style] * players
    assert all(re.fullmatch(r"\d+px", track) for track in style.split(":")[1].split()[1:])


def test_decision_1_the_correctable_read_back_says_what_the_golfbox_box_takes(
    golden: Opened,
) -> None:
    line = "To correct a league index, type the player's Golfbox handicap. The index is 70% of it."
    assert line in html.unescape(golden("t3-first").get("/admin/season").text)
    assert line not in html.unescape(golden("t3").get("/admin/season").text)
    assert line not in html.unescape(golden("s9b").get("/admin/season").text)


@pytest.mark.parametrize(("golfbox", "refusal"), [("5.0", FIXED), ("abc", GOLFBOX_REFUSED)])
def test_r15_once_a_round_is_closed_no_league_index_is_corrected(
    golden: Opened, golden_engine: Engine, golfbox: str, refusal: str
) -> None:
    """A correction that is no number is refused as such (SPEC section 7)."""
    admin = golden("t3")
    response = admin.get("/admin/season")
    assert inputs(response, "golfbox") == []
    assert "Correct" not in SUBMIT.findall(response.text)
    assert FIXED in response.text
    before = everything(golden_engine)
    response = admin.post("/admin/season/index", data={"player": "ann", "golfbox": golfbox})
    assert response.status_code == 400
    assert warns(response) == [refusal]
    assert everything(golden_engine) == before


def test_r15_a_round_open_and_none_closed_leaves_league_indexes_correctable(
    golden: Opened, golden_engine: Engine
) -> None:
    admin = golden("t3-first")
    response = admin.get("/admin/season")
    assert inputs(response, "golfbox") == [""] * 8
    assert FIXED not in response.text
    admin.post("/admin/season/index", data={"player": "ann", "golfbox": "5.0"})
    facts = stored_season(golden_engine, "t3-first")
    assert facts is not None
    assert facts.seed_index_tenths["ann"] == 35


def test_decision_1_an_individual_season_has_no_correction(
    golden: Opened, golden_engine: Engine
) -> None:
    admin = golden("s9b")
    response = admin.get("/admin/season")
    assert inputs(response, "golfbox") == []
    assert FIXED not in response.text
    before = everything(golden_engine)
    response = admin.post("/admin/season/index", data={"player": "ann", "golfbox": "5.0"})
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/season"
    assert everything(golden_engine) == before


def test_d18_bay_settings_are_saved_on_the_read_back_after_a_round_is_closed(
    golden: Opened, golden_engine: Engine
) -> None:
    typed: Menus = [
        (" Game ", [("Putting ", " Auto\nFixed "), *GAME[1][1:]]),
        (COURSE[0], [*COURSE[1], (" ", "")]),
        (" Settings", [("Units ", " Meters")]),
        ("", [NEW_LINE]),
    ]
    admin = golden("t3")
    response = admin.post("/admin/season/bay", data=bay_fields(typed))
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/season"
    expected = (
        # The ends are trimmed and a line break inside the value is kept.
        BaySetting("Game", "Putting", "Auto\nFixed"),
        *T3.bay_settings[1:],
        BaySetting("Settings", "Units", "Meters"),
    )
    facts = stored_season(golden_engine, "t3")
    assert facts is not None
    assert facts.bay_settings == expected
    assert stored_lines(admin.get("/admin/season")) == expected
    assert stored_season(golden_engine, "s9b") == S9B


def test_section_7_the_read_back_reads_one_section_per_menu_game_first(
    golden: Opened, golden_engine: Engine
) -> None:
    game = [line for line in LINES if line.menu == "Game"]
    course = [line for line in LINES if line.menu == "Course"]
    interleaved = (course[0], game[0], course[1], game[1], game[2], *course[2:])
    change_bay_settings(golden_engine, "t3", interleaved)
    response = golden("t3").get("/admin/season")
    assert sections(response) == MENUS
    assert MENU_TEXT.findall(response.text) == ["Game", "Course"]
    assert [html.unescape(name) for name in SETTING_TEXT.findall(response.text)] == [
        line.setting for line in (*game, *course)
    ]
    assert "menu" not in boxes(response)
    assert "setting" not in boxes(response)
    assert values(response) == [line.value for line in (*game, *course)]


def test_d18_every_bay_line_removed_and_saved_stores_none(
    golden: Opened, golden_engine: Engine
) -> None:
    golden("t3").post("/admin/season/bay", data={})
    facts = stored_season(golden_engine, "t3")
    assert facts is not None
    assert facts.bay_settings == ()


def test_the_bay_forms_first_submit_button_is_the_invisible_redraw(golden: Opened) -> None:
    bay_form = BAY_FORM.findall(golden("t3").get("/admin/season").text)[0]
    first = BUTTON.findall(bay_form)[0]
    assert UNSEEN in first
    assert 'tabindex="-1"' in first
    assert NAME_AND_VALUE.findall(first)[0] == ("redraw", "form")
    assert SUBMIT.findall(bay_form)[-1] == "Save bay settings"


TYPED: Menus = [("A", [("a", "1"), ("b", "2")]), ("B", [("c", "3")])]


@pytest.mark.parametrize(
    ("pressed", "drawn"),
    [
        ({"redraw": "form"}, TYPED),
        ({"add": "0"}, [("A", [("a", "1"), ("b", "2"), NEW_LINE]), ("B", [("c", "3")])]),
        ({"add": "1"}, [("A", [("a", "1"), ("b", "2")]), ("B", [("c", "3"), NEW_LINE])]),
        ({"add_menu": "menu"}, [*TYPED, ("", [NEW_LINE])]),
        ({"remove": "0-1"}, [("A", [("a", "1")]), ("B", [("c", "3")])]),
        ({"remove": "1-0"}, [("A", [("a", "1"), ("b", "2")]), ("B", [])]),
    ],
)
def test_enter_add_a_setting_add_a_menu_and_remove_redraw_the_read_back_and_store_nothing(
    golden: Opened, golden_engine: Engine, pressed: dict[str, str], drawn: Menus
) -> None:
    before = everything(golden_engine)
    response = golden("t3").post("/admin/season/bay", data={**bay_fields(TYPED), **pressed})
    assert response.status_code == 200
    assert everything(golden_engine) == before
    assert sections(response) == drawn
    assert warns(response) == []
    assert BEST_N.findall(response.text) == ["4"]


def test_a_correction_while_the_season_is_not_stored_opens_the_form(
    fresh: FastAPI, admin: TestClient
) -> None:
    before = everything(fresh.state.engine)
    for response in (
        admin.post("/admin/season/index", data={"player": "Daniel", "golfbox": "9.4"}),
        admin.post("/admin/season/bay", data=a_form()),
    ):
        assert response.status_code == 303
        assert response.headers["location"] == "/admin/season"
    assert everything(fresh.state.engine) == before
