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
    r'<span class="fine">([^<]+)</span>'
    r'<span class="num"[^>]*>([^<]+)</span>'
)
TAB = re.compile(r'<a class="btn (btn--\w+) grow"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>')
CHIP = re.compile(r'<span class="chip( chip--dropped)?">([^<]+)</span>')
GAP = re.compile(r'<span class="fine" style="color:var\(--win\)">([^<]+)</span>')
BEST_N = re.compile(r'<p class="fine"[^>]*>([^<]+)</p>')
WINNER = re.compile(
    r'<span class="fine" style="width:52px">([^<]+)</span>'
    r'<span class="grow">([^<]+)</span>'
    r'<span class="meta">([^<]+)</span>'
)

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
    # First-half has two rounds at the season's best 2, so only these tell the rules apart.
    tight_rule = StandingsRule(
        best_n=2, segments=(Segment("one", 1, 1, best_n=1), Segment("tight", 1, 3, best_n=1))
    )
    hal_seeded = {**S9B.seed_index_tenths, "hal": 100}
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
        save_whole_season(connection, "tight", replace(S9B, standings_rule=tight_rule))
        save_whole_season(connection, "no-rounds", replace(S9B, rounds=()))
        save_whole_season(connection, "hal-seeded", replace(S9B, seed_index_tenths=hal_seeded))
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
    return [(position, name, points) for position, name, _, points in ROW.findall(page)]


def counts(page: str) -> list[str]:
    """Every row's count of rounds, in order."""
    return [count for _, _, count, _ in ROW.findall(page)]


def chips(page: str) -> list[tuple[bool, str]]:
    """The viewer's round totals, in order, as whether they are dropped and the points."""
    return [(bool(mark), points) for mark, points in CHIP.findall(page)]


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
    assert table(a_player(browser("s9b"), "hal").get("/standings").text) == S9B_TABLE


def test_r10_segment_table_of_s9b(browser: Browser) -> None:
    client = a_player(browser("s9b"), "hal")
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
    client = a_player(browser("amp"), "hal")
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
    as_ann = [("2", "You", "5.0") if row[1] == "ann" else row for row in S9B_TABLE]
    for player_id, seen, expected in (("hal", [2, 3], S9B_TABLE), ("ann", [1, 2, 3, 4], as_ann)):
        view = season_view(database, "late", player_id, now)
        assert [round_.awards.number for round_ in view.rounds] == seen
        page = a_player(browser("late"), player_id).get("/standings").text
        assert table(page) == expected


def test_r10_every_row_shows_its_counted_cards(browser: Browser) -> None:
    client = a_player(browser("tight"), "hal")
    assert counts(client.get("/standings").text) == ["3 rounds"] * 6
    assert counts(client.get("/standings?segment=one").text) == ["1 round"] * 6


def test_r15_a_teams_count_is_the_rounds_it_has_a_score_in(browser: Browser) -> None:
    assert counts(a_player(browser("t3")).get("/standings").text) == [
        "5 rounds",
        "4 rounds",
        "4 rounds",
        "4 rounds",
    ]


def test_section_7_the_viewers_row_is_marked_and_reads_you(browser: Browser) -> None:
    # ann shares second, so a mark that read the position would land on three rows.
    page = a_player(browser("s9b")).get("/standings").text
    assert page.count("card--mine") == 1
    assert table(page)[1] == ("2", "You", "5.0")


def test_r15_the_viewers_team_is_marked_under_its_name(browser: Browser) -> None:
    page = a_player(browser("t3")).get("/standings").text
    assert page.count("card--mine") == 1
    assert table(page) == T3_TABLE


def test_section_7_a_viewer_outside_the_season_has_no_row_of_their_own(browser: Browser) -> None:
    page = a_player(browser("s9b"), "hal").get("/standings").text
    assert "card--mine" not in page
    assert not BEST_N.findall(page)


def test_r10_the_viewer_reads_their_round_totals_with_dropped_ones_marked(
    browser: Browser,
) -> None:
    page = a_player(browser("s9b")).get("/standings").text
    assert chips(page) == [(False, "2.0"), (False, "3.0"), (True, "0.6")]


def test_r15_a_team_reads_its_round_totals_and_best_n_line(browser: Browser) -> None:
    page = a_player(browser("t3")).get("/standings").text
    assert chips(page) == [
        (False, "0.8"),
        (False, "7.0"),
        (False, "2.3"),
        (False, "3.0"),
        (True, "0.5"),
    ]
    assert BEST_N.findall(page) == ["Your best 4 rounds count. 5 rounds played."]


def test_r10_each_tab_marks_what_its_own_table_drops(browser: Browser) -> None:
    client = a_player(browser("tight"))
    assert chips(client.get("/standings?segment=tight").text) == [
        (True, "2.0"),
        (False, "3.0"),
        (True, "0.6"),
    ]
    assert chips(client.get("/standings?segment=one").text) == [(False, "2.0")]


def test_section_7_the_viewer_reads_the_gap_to_the_place_above(browser: Browser) -> None:
    assert GAP.findall(a_player(browser("s9b")).get("/standings").text) == ["8.0 to 1st"]


def test_section_7_a_team_reads_the_exact_gap(browser: Browser) -> None:
    assert GAP.findall(a_player(browser("t3"), "gus").get("/standings").text) == ["6.8 to 1st"]


def test_section_7_the_leader_has_chips_and_no_gap(browser: Browser) -> None:
    page = a_player(browser("s9b"), "cam").get("/standings").text
    assert chips(page)
    assert not GAP.findall(page)


def test_section_7_a_season_with_nothing_closed_has_no_foot_and_no_winners(
    browser: Browser,
) -> None:
    page = a_player(browser("no-rounds")).get("/standings").text
    assert counts(page) == ["0 rounds"] * 6
    assert "card__foot" not in page
    assert "Round winners" not in page


def test_section_7_a_gap_alone_shows_no_rounds_label(browser: Browser) -> None:
    page = a_player(browser("hal-seeded"), "hal").get("/standings").text
    assert GAP.findall(page) == ["2.6 to 6th"]
    assert counts(page)[-1] == "0 rounds"
    assert not chips(page)
    assert ">Rounds<" not in page


def test_section_7_the_best_n_line_reads_the_viewers_own_count(browser: Browser) -> None:
    page = a_player(browser("s9b")).get("/standings").text
    assert BEST_N.findall(page) == ["Your best 2 rounds count. 3 rounds played."]


def test_section_7_a_segment_has_the_best_n_line_of_its_own_best_n(browser: Browser) -> None:
    client = a_player(browser("tight"))
    assert BEST_N.findall(client.get("/standings?segment=tight").text) == [
        "Your best round counts. 3 rounds played."
    ]
    assert BEST_N.findall(client.get("/standings?segment=one").text) == [
        "Your best round counts. 1 round played."
    ]


def test_section_7_a_table_without_best_n_has_no_line(browser: Browser) -> None:
    page = a_player(browser("s9b")).get("/standings?segment=first-half").text
    assert not BEST_N.findall(page)


def test_r10_closed_rounds_show_their_winners_newest_first(browser: Browser) -> None:
    # Round 4 is open. Round 3 is a tie.
    assert WINNER.findall(a_player(browser("s9b")).get("/standings").text) == [
        ("Round 3", "bob, dee", "71 net"),
        ("Round 2", "eve", "71 net"),
        ("Round 1", "cam", "70 net"),
    ]


def test_r15_a_team_rounds_winners_show_their_round_total(browser: Browser) -> None:
    assert WINNER.findall(a_player(browser("t3")).get("/standings").text) == [
        ("Round 5", "gold", "3.0 points"),
        ("Round 4", "red", "3.0 points"),
        ("Round 3", "gold, red", "2.3 points"),
        ("Round 2", "red", "7.0 points"),
        ("Round 1", "blue", "3.0 points"),
    ]


def test_section_7_every_tab_shows_every_closed_rounds_winners(browser: Browser) -> None:
    page = a_player(browser("tight")).get("/standings?segment=one").text
    assert [number for number, _, _ in WINNER.findall(page)] == ["Round 3", "Round 2", "Round 1"]


def test_r12_a_hidden_round_shows_no_winner(browser: Browser) -> None:
    # hal has no card and round 1 still takes late cards. ann has one and sees its winner.
    hal = a_player(browser("late"), "hal").get("/standings").text
    assert [number for number, _, _ in WINNER.findall(hal)] == ["Round 3", "Round 2"]
    ann = a_player(browser("late")).get("/standings").text
    assert [number for number, _, _ in WINNER.findall(ann)] == ["Round 3", "Round 2", "Round 1"]


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
