import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from fixtures.database import golden_database, save_whole_season
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.facts import Segment, StandingsRule
from league.services.play import season_view
from league.services.runtime import utc_now
from league.services.setup import replace_link_token
from league.web.app import create_app

TOKENS_CSS = Path(__file__).parents[2] / "docs" / "design" / "tokens.css"

ROW = re.compile(
    r'<span class="meta"[^>]*>(\d+)</span>'
    r'<span class="grow"[^>]*>([^<]+)</span>'
    r'<span class="num"[^>]*>([^<]+)</span>'
)
TAB = re.compile(r'<a class="btn (btn--\w+) grow"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>')

S9B_TABLE = [
    ("1", "cam", "13.0"),
    ("2", "ann", "5.0"),
    ("2", "bob", "5.0"),
    ("2", "dee", "5.0"),
    ("5", "eve", "4.6"),
    ("6", "fay", "2.6"),
]
S9B_FIRST_HALF = [
    ("1", "cam", "13.0"),
    ("2", "ann", "5.0"),
    ("2", "bob", "5.0"),
    ("2", "dee", "5.0"),
    ("5", "eve", "4.0"),
    ("6", "fay", "2.0"),
]
T3_TABLE = [
    ("1", "red", "16.0"),
    ("2", "gold", "9.3"),
    ("3", "blue", "8.0"),
    ("4", "green", "4.8"),
]

Browser = Callable[[str], TestClient]


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    engine = golden_database(tmp_path)
    *closed, round_5 = T3.rounds
    round_1, *rest = S9B.rounds
    late_until = utc_now() + timedelta(days=1)
    amp_rule = StandingsRule(best_n=2, segments=(Segment("a & b", 1, 2),))
    with engine.begin() as connection:
        save_whole_season(
            connection,
            "round-5-open",
            replace(T3, rounds=(*closed, replace(round_5, closed_at=None))),
        )
        save_whole_season(
            connection,
            "late",
            replace(S9B, rounds=(replace(round_1, late_until=late_until), *rest)),
        )
        save_whole_season(connection, "amp", replace(S9B, standings_rule=amp_rule))
    yield engine
    engine.dispose()


def an_app(monkeypatch: pytest.MonkeyPatch, path: Path, season_id: str) -> FastAPI:
    monkeypatch.setenv("LEAGUE_DATABASE", str(path))
    monkeypatch.setenv("LEAGUE_SEASON", season_id)
    return create_app()


@pytest.fixture
def browser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, database: Engine) -> Iterator[Browser]:
    """Opens a browser that has followed no link yet on one season of the database."""
    apps: list[FastAPI] = []

    def a_browser(season_id: str) -> TestClient:
        apps.append(an_app(monkeypatch, tmp_path / "league.db", season_id))
        return TestClient(apps[-1], follow_redirects=False)

    yield a_browser
    for app in apps:
        app.state.engine.dispose()


def a_player(client: TestClient, player_id: str = "ann") -> TestClient:
    """That browser once it has opened the player's link."""
    client.get(f"/k/{player_id}-link")
    return client


def table(page: str) -> list[tuple[str, str, str]]:
    """Every row of a page's table, in order, as position, name and points."""
    return ROW.findall(page)


def test_link_sets_the_cookie_and_goes_to_standings(browser: Browser) -> None:
    response = browser("s9b").get("/k/ann-link")
    assert response.status_code == 303
    assert response.headers["location"] == "/standings"
    parts = {part.lower() for part in response.headers["set-cookie"].split("; ")}
    assert parts == {
        "link_token=ann-link",
        "httponly",
        "max-age=34560000",
        "path=/",
        "samesite=lax",
    }


def test_unknown_link_is_refused_and_sets_no_cookie(browser: Browser) -> None:
    response = browser("s9b").get("/k/nobody-link")
    assert response.status_code == 401
    assert response.text == "Open your personal link."
    assert "set-cookie" not in response.headers


def test_standings_without_a_cookie_is_refused(browser: Browser) -> None:
    response = browser("s9b").get("/standings")
    assert response.status_code == 401
    assert response.text == "Open your personal link."


def test_standings_with_a_cookie_nobody_holds_is_refused(browser: Browser) -> None:
    client = browser("s9b")
    client.cookies.set("link_token", "nobody-link")
    assert client.get("/standings").status_code == 401


def test_replaced_link_token_refuses_its_old_cookie(browser: Browser, database: Engine) -> None:
    client = a_player(browser("s9b"))
    assert client.get("/standings").status_code == 200
    new_token = replace_link_token(database, "ann")
    assert client.get("/standings").status_code == 401
    assert client.get("/k/ann-link").status_code == 401
    assert client.get(f"/k/{new_token}").status_code == 303
    assert client.get("/standings").status_code == 200


def test_r10_season_table_of_s9b(browser: Browser) -> None:
    assert table(a_player(browser("s9b")).get("/standings").text) == S9B_TABLE


def test_r10_segment_table_of_s9b(browser: Browser) -> None:
    client = a_player(browser("s9b"))
    assert TAB.findall(client.get("/standings").text) == [
        ("btn--primary", "/standings", "Season"),
        ("btn--ghost", "/standings?segment=first-half", "first-half"),
    ]
    page = client.get("/standings?segment=first-half").text
    assert table(page) == S9B_FIRST_HALF
    assert TAB.findall(page) == [
        ("btn--ghost", "/standings", "Season"),
        ("btn--primary", "/standings?segment=first-half", "first-half"),
    ]


def test_r10_segment_tab_links_a_name_that_needs_encoding(browser: Browser) -> None:
    client = a_player(browser("amp"))
    _, (_, href, _) = TAB.findall(client.get("/standings").text)
    assert table(client.get(href).text) == S9B_FIRST_HALF


def test_r15_team_table_of_t3(browser: Browser) -> None:
    assert table(a_player(browser("t3")).get("/standings").text) == T3_TABLE


def test_r10_open_round_is_in_no_table(browser: Browser) -> None:
    assert table(a_player(browser("round-5-open")).get("/standings").text) == [
        ("1", "red", "13.0"),
        ("2", "blue", "7.5"),
        ("3", "gold", "6.3"),
        ("4", "green", "2.8"),
    ]


def test_r12_two_viewers_read_the_same_table(browser: Browser, database: Engine) -> None:
    now = utc_now()
    # hal plays in no round of this season, so he holds no card: round 1, which still takes
    # late cards, is hidden from him as the open round 4 is. ann sees both.
    for player_id, seen in (("hal", [2, 3]), ("ann", [1, 2, 3, 4])):
        view = season_view(database, "late", player_id, now)
        assert [round_.awards.number for round_ in view.rounds] == seen
        page = a_player(browser("late"), player_id).get("/standings").text
        assert table(page) == S9B_TABLE


def test_unknown_segment_is_not_found(browser: Browser) -> None:
    assert a_player(browser("s9b")).get("/standings?segment=nowhere").status_code == 404


def test_page_links_the_stylesheet_and_it_is_served(browser: Browser) -> None:
    client = a_player(browser("s9b"))
    assert '<link rel="stylesheet" href="/static/app.css">' in client.get("/standings").text
    assert client.get("/static/app.css").content == TOKENS_CSS.read_bytes()


def test_api_pages_are_not_served(browser: Browser) -> None:
    client = browser("s9b")
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_create_app_migrates_a_new_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = an_app(monkeypatch, tmp_path / "new.db", "no-season")
    assert TestClient(app).get("/k/nobody").status_code == 401
    app.state.engine.dispose()
