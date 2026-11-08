import html
import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine

from fixtures.database import a_copy, a_template, load
from fixtures.season import SEASON as S9B
from fixtures.team_season import PARS, t3_open
from fixtures.team_season import SEASON as T3
from league.domain.facts import Segment, StandingsRule
from league.services.clock import utc_now
from league.services.play import season_view
from league.services.setup import replace_link_token
from league.store.save import save_player, save_window
from league.web.app import create_app

TOKENS_CSS = Path(__file__).parents[2] / "docs" / "design" / "tokens.css"
DASH = "\N{EN DASH}"
ADMIN_TOKEN = "admin-secret"

ROW = re.compile(
    r'<span class="meta"[^>]*>(\d+)</span>'
    r'<span class="grow"[^>]*>([^<]+)</span>'
    r'<span class="fine">([^<]+)</span>'
    r'<span class="num"[^>]*>([^<]+)</span>'
)
TAB = re.compile(r'<a class="btn (btn--\w+) grow"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>')
CELL = re.compile(
    r'<a class="hole"[^>]*><span class="hole__n">(R\d+)</span>'
    r'<span class="chip( chip--dropped)?"[^>]*>([^<]+)</span></a>'
)
GRID_LINK = re.compile(r'<a class="hole" href="(/rounds/\d+)"')
WINNER_LINK = re.compile(r'<a class="row" href="(/rounds/\d+)"')
GAP = re.compile(r'<span class="fine" style="color:var\(--win\)">([^<]+)</span>')
BEST_N = re.compile(r'<p class="fine"[^>]*>([^<]+)</p>')
WINNER = re.compile(
    r'<span class="fine" style="width:52px">([^<]+)</span>'
    r'<span class="grow">([^<]+)</span>'
    r'<span class="meta">([^<]+)</span>'
)

ROUND_BLOCK = re.compile(r'(?=<section class="card">)')
ROUND_HEAD = re.compile(
    r'<span class="label grow" style="color:var\(--brass\)">([^<]+)</span>'
    r'<span style="color:var\(--brass\)[^>]*>([^<]+)</span>'
)
COURSE = re.compile(r'<h1 class="h1"[^>]*>([^<]+)</h1>')
TEE_AND_CLOSE = re.compile(r'<div class="meta"[^>]*>([^<]+) &middot; (Closes [^<]+)</div>')
FORMAT_LINE = re.compile(r'<p class="help card--sunken"[^>]*>([^<]+)</p>')
PLAYER_ROW = re.compile(
    r'<div class="row"><span class="grow" style="font-size:15px">([^<]+)</span>'
    r'<span class="meta">([^<]+)</span>'
    r'<span class="pill pill--(\w+)">([^<]+)</span></div>'
)
FOOT = re.compile(r'<div class="card__foot fine">([^<]+)</div>')
SEASON_LABEL = re.compile(r'<span class="label">([^<]+)</span>')
SEASON_CARD = re.compile(r'<a class="card row" href="/standings"[^>]*>(.*?)</a>', re.DOTALL)
SEASON_PLACE = re.compile(
    r'<span class="num num--m">([^<]+)</span><span class="meta">([^<]+)</span>'
)
SEASON_GAP = re.compile(
    r'<div class="num num--m"[^>]*>([^<]+)</div><div class="meta">([^<]+)</div>'
)
ROUND_LINK = re.compile(r'<a href="(/rounds/\d+)"')
BUTTON = re.compile(r'<a class="btn ([\w -]+)" href="([^"]+)">([^<]+)</a>')
TEXT = re.compile(r">([^<>]+)<")
NAV = re.compile(r'<a class="nav__item( nav__item--on)?" href="([^"]+)">([^<]+)</a>')
NO_ROUND = "No round is open right now."
OPEN_YOUR_LINK = "Open your personal link from the group chat."
NOT_OPEN = "That round isn't open."
NOTICE = re.compile(
    r'<p class="card card--sunken help"[^>]*>([^<]+)</p>\s*'
    r'<a class="btn btn--primary btn--block" href="/">Home</a>'
)
HOLE = re.compile(
    r'<div class="hole"><span class="hole__n">(\d+)</span>'
    r'<input class="hole__score( hole__score--check)?" name="(h\d+)" value="([^"]*)" '
    r'inputmode="numeric" aria-label="([^"]+)"><span class="hole__par">([^<]+)</span></div>'
)
WARN = re.compile(r'<p class="card card--warn help"[^>]*>([^<]+)</p>')
SUBMIT = re.compile(
    r'<button class="btn btn--primary btn--block"[^>]*id="submit-card"( disabled)?>'
)
HALF = re.compile(r'<span class="label grow">(Out|In)</span><span class="meta">([^<]*)</span>')
TOTAL = re.compile(r'<span class="meta grow">Total</span><span class="num num--m">([^<]+)</span>')

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


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    *closed, round_5 = T3.rounds
    round_1, *rest = S9B.rounds
    late_until = utc_now() + timedelta(days=1)
    amp_rule = StandingsRule(best_n=2, segments=(Segment("a & b", 1, 2),))
    # First-half has two rounds at the season's best 2, so only these tell the rules apart.
    tight_rule = StandingsRule(
        best_n=2,
        segments=(
            Segment("one", 1, 1, best_n=1),
            Segment("tight", 1, 3, best_n=1),
            Segment("later", 2, 3),
        ),
    )
    hal_seeded = {**S9B.seed_index_tenths, "hal": 100}
    round_3 = T3.rounds[2]
    round_4 = S9B.rounds[3]
    held = round_4.cards
    without_ann = replace(round_4, cards={k: card for k, card in held.items() if k != "ann"})
    only_ann = replace(round_4, cards={"ann": held["ann"]})
    late = replace(S9B, rounds=(replace(round_1, late_until=late_until), *rest))
    seasons = {
        "round-5-open": replace(T3, rounds=(*closed, replace(round_5, closed_at=None))),
        "late": late,
        "amp": replace(S9B, standings_rule=amp_rule),
        "tight": replace(S9B, standings_rule=tight_rule),
        "no-rounds": replace(S9B, rounds=()),
        "hal-seeded": replace(late, seed_index_tenths=hal_seeded),
        "t3-open": t3_open(),
        "all-open": replace(T3, rounds=tuple(replace(r, closed_at=None) for r in T3.rounds)),
        "one-stroke": replace(t3_open(), seed_index_tenths={**T3.seed_index_tenths, "ann": 10}),
        "one-team-card": replace(
            T3,
            rounds=(
                *T3.rounds[:2],
                replace(round_3, closed_at=None, team_cards={"red": round_3.team_cards["red"]}),
                *T3.rounds[3:],
            ),
        ),
        "s9b-open": replace(S9B, rounds=(*S9B.rounds[:3], without_ann)),
        "one-card": replace(S9B, rounds=(*S9B.rounds[:3], only_ann)),
    }
    return a_template(tmp_path_factory.mktemp("template"), seasons)


@pytest.fixture
def database(template: Path, tmp_path: Path) -> Iterator[Engine]:
    engine = a_copy(template, tmp_path)
    yield engine
    engine.dispose()


def an_app(monkeypatch: pytest.MonkeyPatch, path: Path, season_id: str) -> FastAPI:
    monkeypatch.setenv("LEAGUE_DATABASE", str(path))
    monkeypatch.setenv("LEAGUE_SEASON", season_id)
    monkeypatch.setenv("LEAGUE_ADMIN_TOKEN", ADMIN_TOKEN)
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


def cells(page: str) -> list[tuple[str, bool, str]]:
    """The viewer's grid, in order, as each cell's round, whether it is dropped and its total."""
    return [(number, bool(mark), points) for number, mark, points in CELL.findall(page)]


def blocks(page: str) -> list[str]:
    """The page's round blocks in order, without what stands above the first."""
    return ROUND_BLOCK.split(page.split("<nav", maxsplit=1)[0])[1:]


def season_card(page: str) -> list[tuple[str, str]]:
    """The page's season card as its place, then its gap when it has one."""
    return [
        pair
        for card in SEASON_CARD.findall(page)
        for pair in (*SEASON_PLACE.findall(card), *SEASON_GAP.findall(card))
    ]


def home_of(browser: Browser, season_id: str, player_id: str) -> str:
    return a_player(browser(season_id), player_id).get("/").text


def screen(page: str) -> list[str]:
    """Every line of text inside the page's main, top to bottom, as a reader sees it."""
    main = page.split("<main", maxsplit=1)[1].split("</main>", maxsplit=1)[0]
    return [html.unescape(text).strip() for text in TEXT.findall(main) if text.strip()]


def notice(response: Response) -> tuple[int, str]:
    """A refusal's status and its notice's message, read only where Home links home."""
    (message,) = NOTICE.findall(response.text)
    return response.status_code, html.unescape(message)


def set_close(engine: Engine, season_id: str, number: int, closes_at: datetime) -> None:
    with engine.begin() as connection:
        save_window(connection, season_id, number, closes_at - timedelta(days=14), closes_at)


def test_link_sets_the_cookie_and_goes_home(browser: Browser) -> None:
    response = browser("s9b").get("/k/ann-link")
    assert response.status_code == 303
    assert response.headers["location"] == "/"
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
    assert notice(response) == (401, OPEN_YOUR_LINK)
    assert "set-cookie" not in response.headers


def test_standings_without_a_cookie_is_refused(browser: Browser) -> None:
    assert notice(browser("s9b").get("/standings")) == (401, OPEN_YOUR_LINK)


def test_standings_with_a_cookie_nobody_holds_is_refused(browser: Browser) -> None:
    client = browser("s9b")
    client.cookies.set("link_token", "nobody-link")
    assert notice(client.get("/standings")) == (401, OPEN_YOUR_LINK)


def test_replaced_link_token_refuses_its_old_cookie(browser: Browser, database: Engine) -> None:
    client = a_player(browser("s9b"))
    assert client.get("/standings").status_code == 200
    new_token = replace_link_token(database, "ann")
    assert notice(client.get("/standings")) == (401, OPEN_YOUR_LINK)
    assert notice(client.get("/k/ann-link")) == (401, OPEN_YOUR_LINK)
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
    # Round 4 is open, so it has no cell.
    page = a_player(browser("s9b")).get("/standings").text
    assert cells(page) == [("R1", False, "2.0"), ("R2", False, "3.0"), ("R3", True, "0.6")]


def test_r15_a_team_reads_its_round_totals_and_best_n_line(browser: Browser) -> None:
    page = a_player(browser("t3")).get("/standings").text
    assert cells(page) == [
        ("R1", False, "0.8"),
        ("R2", False, "7.0"),
        ("R3", False, "2.3"),
        ("R4", False, "3.0"),
        ("R5", True, "0.5"),
    ]
    assert BEST_N.findall(page) == ["Your best 4 rounds count. 5 rounds played."]


def test_r10_each_tab_marks_what_its_own_table_drops(browser: Browser) -> None:
    client = a_player(browser("tight"))
    assert cells(client.get("/standings?segment=tight").text) == [
        ("R1", True, "2.0"),
        ("R2", False, "3.0"),
        ("R3", True, "0.6"),
    ]
    assert cells(client.get("/standings?segment=one").text) == [("R1", False, "2.0")]
    assert cells(client.get("/standings?segment=later").text) == [
        ("R2", False, "3.0"),
        ("R3", False, "0.6"),
    ]


def test_section_7_the_viewer_reads_the_gap_to_the_place_above(browser: Browser) -> None:
    assert GAP.findall(a_player(browser("s9b")).get("/standings").text) == ["8.0 to 1st"]


def test_section_7_gold_reads_its_grid_and_the_gap_as_shown(browser: Browser) -> None:
    page = a_player(browser("t3"), "gus").get("/standings").text
    assert cells(page) == [
        ("R1", False, DASH),
        ("R2", False, "2.5"),
        ("R3", False, "2.3"),
        ("R4", False, "1.5"),
        ("R5", False, "3.0"),
    ]
    assert GAP.findall(page) == ["6.7 to 1st"]


def test_section_7_the_leader_has_a_grid_and_no_gap(browser: Browser) -> None:
    page = a_player(browser("s9b"), "cam").get("/standings").text
    assert cells(page)
    assert not GAP.findall(page)


def test_section_7_a_season_with_nothing_closed_has_no_foot_and_no_winners(
    browser: Browser,
) -> None:
    page = a_player(browser("no-rounds")).get("/standings").text
    assert counts(page) == ["0 rounds"] * 6
    assert "card__foot" not in page
    assert "Round winners" not in page


def test_r12_a_round_hidden_from_the_viewer_keeps_its_cell(browser: Browser) -> None:
    # hal has no card and round 1 still takes late cards: its winner is hidden, its cell is not.
    page = a_player(browser("hal-seeded"), "hal").get("/standings").text
    assert [number for number, _, _ in WINNER.findall(page)] == ["Round 3", "Round 2"]
    assert cells(page) == [("R1", False, DASH), ("R2", False, DASH), ("R3", False, DASH)]
    assert GAP.findall(page) == ["2.6 to 6th"]
    assert counts(page)[-1] == "0 rounds"


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


def test_section_7_each_round_in_the_viewers_grid_links_to_its_round_page(
    browser: Browser,
) -> None:
    page = a_player(browser("t3")).get("/standings").text
    assert GRID_LINK.findall(page) == [f"/rounds/{number}" for number in range(1, 6)]


def test_section_7_a_segment_tabs_grid_links_its_own_rounds(browser: Browser) -> None:
    page = a_player(browser("tight")).get("/standings?segment=later").text
    assert GRID_LINK.findall(page) == ["/rounds/2", "/rounds/3"]


def test_section_7_each_row_of_round_winners_links_to_its_round_page(browser: Browser) -> None:
    page = a_player(browser("t3")).get("/standings").text
    assert WINNER_LINK.findall(page) == [f"/rounds/{number}" for number in range(5, 0, -1)]
    # R12 hides round 1 from hal, so a link counted down from the rows would miss.
    hal = a_player(browser("late"), "hal").get("/standings").text
    assert WINNER_LINK.findall(hal) == ["/rounds/3", "/rounds/2"]


def test_section_7_a_closed_rounds_result_opens_from_standings_while_a_round_is_open(
    browser: Browser,
) -> None:
    client = a_player(browser("round-5-open"))
    page = client.get("/standings").text
    assert GRID_LINK.findall(page) == [f"/rounds/{number}" for number in range(1, 5)]
    assert WINNER_LINK.findall(page) == [f"/rounds/{number}" for number in range(4, 0, -1)]
    assert "/rounds/5" not in page
    result = client.get(WINNER_LINK.findall(page)[0])
    assert result.status_code == 200
    assert [team for _, team, _, _, _ in RANKED.findall(result.text)] == ["red", "gold", "blue"]


def test_home_without_a_cookie_is_refused(browser: Browser) -> None:
    assert notice(browser("t3").get("/")) == (401, OPEN_YOUR_LINK)


def test_home_with_a_cookie_nobody_holds_is_refused(browser: Browser) -> None:
    client = browser("t3")
    client.cookies.set("link_token", "nobody-link")
    assert notice(client.get("/")) == (401, OPEN_YOUR_LINK)


def test_home_links_the_stylesheet_and_names_the_season(browser: Browser) -> None:
    page = home_of(browser, "t3", "gus")
    assert '<link rel="stylesheet" href="/static/app.css">' in page
    assert SEASON_LABEL.findall(page) == ["t3"]


def nav(page: str) -> list[tuple[str, str, bool]]:
    """The nav bar's tabs in order, as each one's text, link and whether it is marked."""
    return [(text, href, bool(on)) for on, href, text in NAV.findall(page)]


def tabs(marked: str) -> list[tuple[str, str, bool]]:
    links = {"Home": "/", "Round": "/round", "Standings": "/standings"}
    return [(text, href, text == marked) for text, href in links.items()]


def test_section_7_every_player_screen_has_the_round_tab_and_marks_its_own(
    browser: Browser,
) -> None:
    """hal's round 1 on t3_open is before playing, and his round 2 is its result."""
    client = a_player(browser("t3-open"), "hal")
    assert nav(client.get("/").text) == tabs("Home")
    assert nav(client.get("/standings").text) == tabs("Standings")
    assert TEAM_ROW.findall(client.get("/rounds/1").text)
    assert nav(client.get("/rounds/1").text) == tabs("Round")
    assert RANKED.findall(client.get("/rounds/2").text)
    assert nav(client.get("/rounds/2").text) == tabs("Round")


def test_section_7_each_open_round_on_home_links_to_its_round_page(
    browser: Browser, database: Engine
) -> None:
    with database.begin() as connection:
        save_player(connection, "ivy", "ivy-link")
    for player_id in ("hal", "ivy"):
        first, third = blocks(home_of(browser, "t3-open", player_id))
        assert ROUND_LINK.findall(first) == ["/rounds/1"]
        assert ROUND_LINK.findall(third) == ["/rounds/3"]


@pytest.mark.parametrize(
    ("season_id", "number"),
    [("t3-open", 1), ("round-5-open", 5), ("t3", 5)],
    ids=["oldest open", "the one open", "latest closed"],
)
def test_section_7_the_round_tab_opens_the_oldest_open_round_else_the_latest_closed(
    browser: Browser, season_id: str, number: int
) -> None:
    response = a_player(browser(season_id), "hal").get("/round")
    assert (response.status_code, response.headers["location"]) == (303, f"/rounds/{number}")


def test_section_7_the_round_tab_without_a_round_reads_the_notice(browser: Browser) -> None:
    assert notice(a_player(browser("no-rounds")).get("/round")) == (404, NO_ROUND)


def test_round_tab_without_a_cookie_is_refused(browser: Browser) -> None:
    assert notice(browser("t3-open").get("/round")) == (401, OPEN_YOUR_LINK)


def test_section_7_every_format_has_its_name_and_line(browser: Browser) -> None:
    page = home_of(browser, "all-open", "ann")
    assert [label for label, _ in ROUND_HEAD.findall(page)] == [
        "Round 1 &middot; Best ball",
        "Round 2 &middot; Combined",
        "Round 3 &middot; Scramble",
        "Round 4 &middot; Greensome",
        "Round 5 &middot; Foursome",
    ]
    assert FORMAT_LINE.findall(page) == [
        "You each play your own round. The better net score on each hole counts.",
        "You each play your own round. Both scores count on every hole.",
        "Play together on one bay. Both tee off, pick the best shot, both play from there. "
        "One card for the team.",
        "Play together on one bay. Both tee off, pick one drive, then take turns. "
        "One card for the team.",
        "Play together on one bay with one ball, taking turns. One card for the team.",
    ]


def test_section_7_open_rounds_show_oldest_first_with_their_number_course_and_tee(
    browser: Browser,
) -> None:
    """Rounds 1 and 3 are on two tees of one course."""
    first, third = blocks(home_of(browser, "t3-open", "gus"))
    assert ROUND_HEAD.findall(first)[0][0] == "Round 1 &middot; Best ball"
    assert COURSE.findall(first) == ["Trinity Forest Golf Club"]
    assert [tee for tee, _ in TEE_AND_CLOSE.findall(first)] == ["White tee"]
    assert ROUND_HEAD.findall(third)[0][0] == "Round 3 &middot; Scramble"
    assert COURSE.findall(third) == ["Trinity Forest Golf Club"]
    assert [tee for tee, _ in TEE_AND_CLOSE.findall(third)] == ["Blue tee"]


def test_section_7_own_ball_rows_read_each_player_with_their_strokes_and_card(
    browser: Browser,
) -> None:
    gus, _ = blocks(home_of(browser, "t3-open", "gus"))
    assert PLAYER_ROW.findall(gus) == [
        ("gus", "7 strokes", "win", "Card in"),
        ("hal", "15 strokes", "muted", "Not yet"),
    ]
    hal, _ = blocks(home_of(browser, "t3-open", "hal"))
    assert PLAYER_ROW.findall(hal) == [
        ("hal", "15 strokes", "muted", "Not yet"),
        ("gus", "7 strokes", "win", "Card in"),
    ]


def test_section_7_one_stroke_is_singular(browser: Browser) -> None:
    ann, _ = blocks(home_of(browser, "one-stroke", "ann"))
    assert PLAYER_ROW.findall(ann)[0] == ("ann", "1 stroke", "win", "Card in")


def test_section_7_a_shared_ball_round_has_one_team_row(browser: Browser) -> None:
    _, gold = blocks(home_of(browser, "t3-open", "gus"))
    assert PLAYER_ROW.findall(gold) == [("Team", "6 strokes", "win", "Card in")]
    _, blue = blocks(home_of(browser, "t3-open", "cam"))
    assert PLAYER_ROW.findall(blue) == [("Team", "4 strokes", "muted", "Not yet")]


def test_section_7_home_shows_no_team_name_index_par_or_slope(browser: Browser) -> None:
    page = home_of(browser, "t3-open", "gus")
    for word in ("gold", "Index", "Par ", "Slope"):
        assert word not in page


def test_section_7_home_offers_register_card_beside_the_bay_until_the_card_is_in(
    browser: Browser,
) -> None:
    """hal has no card in round 1, and gold's team card is in for round 3."""
    assert BUTTON.findall(home_of(browser, "t3-open", "hal")) == [
        ("btn--ghost", "/rounds/1/bay", "Set up the bay"),
        ("btn--primary", "/rounds/1/cards/new", "Register card"),
        ("btn--ghost", "/rounds/3/bay", "Set up the bay"),
    ]
    assert BUTTON.findall(home_of(browser, "t3-open", "gus")) == [
        ("btn--ghost", "/rounds/1/bay", "Set up the bay"),
        ("btn--ghost", "/rounds/3/bay", "Set up the bay"),
    ]


def test_section_7_the_foot_reads_both_cards_only_in_an_own_ball_round(browser: Browser) -> None:
    hal_1, hal_3 = blocks(home_of(browser, "t3-open", "hal"))
    assert FOOT.findall(hal_1) == [
        "Your team needs both cards to score. 3 of 4 teams have a score."
    ]
    assert FOOT.findall(hal_3) == ["3 of 4 teams have a score."]


def test_section_7_one_team_with_a_score_is_singular(browser: Browser) -> None:
    assert FOOT.findall(home_of(browser, "one-team-card", "ann")) == ["1 of 4 teams has a score."]


def test_section_7_an_individual_season_reads_who_has_played(browser: Browser) -> None:
    assert FOOT.findall(home_of(browser, "s9b", "ann")) == ["6 of 6 have played."]
    assert FOOT.findall(home_of(browser, "s9b-open", "ann")) == [
        "5 of 6 have played. Scores unlock when yours is in."
    ]
    assert FOOT.findall(home_of(browser, "one-card", "ann")) == ["1 of 6 has played."]


def test_section_7_an_individual_season_has_no_format_or_rows(browser: Browser) -> None:
    page = home_of(browser, "s9b", "ann")
    assert ROUND_HEAD.findall(page)[0][0] == "Round 4"
    assert not FORMAT_LINE.findall(page)
    assert not PLAYER_ROW.findall(page)
    assert "/bay" not in page
    assert season_card(page) == [("2nd", "5.0 points"), ("8.0", "to 1st")]
    assert "/cards/new" not in home_of(browser, "s9b-open", "ann")


def test_section_7_a_viewer_outside_the_season_reads_the_round_and_the_count(
    browser: Browser, database: Engine
) -> None:
    page = home_of(browser, "s9b", "hal")
    assert FOOT.findall(page) == ["6 of 6 have played."]
    assert not season_card(page)
    with database.begin() as connection:
        save_player(connection, "ivy", "ivy-link")
    outside = home_of(browser, "t3-open", "ivy")
    assert FOOT.findall(outside) == ["3 of 4 teams have a score.", "3 of 4 teams have a score."]
    assert ROUND_HEAD.findall(outside)[0][0] == "Round 1"
    assert not PLAYER_ROW.findall(outside)
    assert "/bay" not in outside
    assert "/cards/new" not in outside
    assert not season_card(outside)


def test_section_7_with_no_open_round_home_says_so_above_the_season_card(
    browser: Browser,
) -> None:
    page = home_of(browser, "t3", "gus")
    assert page.index(NO_ROUND) < page.index('class="card row"')
    assert season_card(page) == [("2nd", "9.3 points"), ("6.7", "to 1st")]


def test_section_7_the_leader_has_no_gap(browser: Browser) -> None:
    page = home_of(browser, "t3", "ann")
    assert season_card(page) == [("1st", "16.0 points")]
    assert ">to " not in page


def test_section_7_the_season_card_stands_once_below_the_rounds_and_links_to_standings(
    browser: Browser,
) -> None:
    page = home_of(browser, "t3-open", "gus")
    assert page.count('<a class="card row" href="/standings"') == 1
    assert page.rindex("card__foot") < page.index('class="card row"')
    assert NO_ROUND not in page


def test_section_7_time_left_reads_against_the_clock(browser: Browser, database: Engine) -> None:
    set_close(database, "t3-open", 1, utc_now() + timedelta(days=4, hours=1))
    first, third = blocks(home_of(browser, "t3-open", "gus"))
    assert ROUND_HEAD.findall(first)[0][1] == "4 days left"
    assert ROUND_HEAD.findall(third)[0][1] == "Closing soon"


@pytest.mark.parametrize(
    ("closes_at", "expected"),
    [
        pytest.param(datetime(2026, 11, 15, 21, 0), "Closes Sun 15 Nov, 22:00", id="winter"),
        pytest.param(datetime(2026, 7, 12, 20, 0), "Closes Sun 12 Jul, 22:00", id="summer"),
        pytest.param(datetime(2026, 2, 1, 21, 0), "Closes Sun 1 Feb, 22:00", id="a one digit day"),
    ],
)
def test_section_7_the_close_shows_in_local_time_with_its_date(
    browser: Browser, database: Engine, closes_at: datetime, expected: str
) -> None:
    set_close(database, "t3-open", 1, closes_at)
    first, _ = blocks(home_of(browser, "t3-open", "gus"))
    assert [close for _, close in TEE_AND_CLOSE.findall(first)] == [expected]


MULLIGANS = (
    "Mulligans: Always. Only for an obvious technical fault, such as a shot the sim misread or "
    "didn't pick up."
)
SEASON_LINES = [
    "Pins: Medium",
    MULLIGANS,
    "Putting: Auto, Fixed",
    "Course",
    "Wind: Off",
    "Fairway firmness: Medium",
    "Green firmness: Medium",
    "Green stimp: 9",
    "Leave every other setting as it is.",
]
OWN_BALL_BAY = [
    "\N{LEFTWARDS ARROW}",
    "Round 1 \N{MIDDLE DOT} Best ball",
    "Course: Trinity Forest Golf Club",
    "Players",
    "Add everyone playing. For each player:",
    "Tee: White",
    "HCP index: leave as it is",
    "Game",
    "Game type: Individual, Stroke (Gross)",
    "Holes: All",
    *SEASON_LINES,
    "After the round, enter your Gross row from the scorecard.",
]
SHARED_BALL_BAY = [
    "\N{LEFTWARDS ARROW}",
    "Round 3 \N{MIDDLE DOT} Scramble",
    "Course: Trinity Forest Golf Club",
    "Players",
    "Add both of you to one team. For each player:",
    "Tee: Blue",
    "HCP index: leave as it is",
    "Game",
    "Game type: 2 player teams, Scramble, Stroke (Gross)",
    "Holes: All",
    *SEASON_LINES,
    "After the round, one of you enters the team's Gross row.",
]


def bay_of(browser: Browser, season_id: str, number: int, player_id: str = "gus") -> Response:
    return a_player(browser(season_id), player_id).get(f"/rounds/{number}/bay")


@pytest.mark.parametrize(
    ("number", "expected"),
    [pytest.param(1, OWN_BALL_BAY, id="own-ball"), pytest.param(3, SHARED_BALL_BAY, id="shared")],
)
def test_section_7_the_bay_reads_trackmans_menus_in_order_then_the_closing_lines(
    browser: Browser, number: int, expected: list[str]
) -> None:
    """The tee's name stands apart from its course, and every Game and Course line as written."""
    assert screen(bay_of(browser, "t3-open", number).text) == expected


@pytest.mark.parametrize(
    ("number", "players", "game_type"),
    [
        (1, "Add everyone playing.", "Individual, Stroke (Gross)"),
        (2, "Add everyone playing.", "Individual, Stroke (Gross)"),
        (3, "Add both of you to one team.", "2 player teams, Scramble, Stroke (Gross)"),
        (4, "Add both of you to one team.", "2 player teams, Greensome, Stroke (Gross)"),
        (5, "Add both of you to one team.", "2 player teams, Foursome, Stroke (Gross)"),
    ],
)
def test_section_7_every_format_has_its_players_line_and_game_type(
    browser: Browser, number: int, players: str, game_type: str
) -> None:
    lines = screen(bay_of(browser, "all-open", number).text)
    assert lines[4] == f"{players} For each player:"
    assert lines[8:10] == [f"Game type: {game_type}", "Holes: All"]


def test_section_7_a_round_without_a_bay_is_not_found(browser: Browser) -> None:
    assert notice(bay_of(browser, "t3-open", 2, "ann")) == (404, NOT_OPEN)
    assert notice(bay_of(browser, "t3-open", 9, "ann")) == (404, NOT_OPEN)


def test_bay_without_a_cookie_is_refused(browser: Browser) -> None:
    assert notice(browser("t3-open").get("/rounds/1/bay")) == (401, OPEN_YOUR_LINK)


def test_section_7_a_league_player_outside_the_season_reads_the_bay(
    browser: Browser, database: Engine
) -> None:
    with database.begin() as connection:
        save_player(connection, "ivy", "ivy-link")
    assert screen(bay_of(browser, "t3-open", 1, "ivy").text) == OWN_BALL_BAY


# The design's card: out 41, in 40, and no two neighbouring holes alike in a way that hides a
# swap of hole order.
DESIGN = (4, 5, 3, 5, 6, 5, 5, 4, 4, 5, 3, 4, 5, 4, 6, 5, 3, 5)


def form_of(scores: tuple[int, ...]) -> dict[str, str]:
    return {f"h{hole}": str(score) for hole, score in enumerate(scores, start=1)}


def check(browser: Browser, player_id: str, number: int, form: dict[str, str]) -> Response:
    """Check the card: the same screen asked for again with the scores in its query."""
    return a_player(browser("t3-open"), player_id).get(f"/rounds/{number}/cards/new", params=form)


def hand_in(browser: Browser, player_id: str, number: int, form: dict[str, str]) -> Response:
    return a_player(browser("t3-open"), player_id).post(f"/rounds/{number}/cards", data=form)


def test_section_7_register_card_opens_18_empty_inputs_with_hole_and_par(
    browser: Browser,
) -> None:
    """T3's pars run 4, 4, 3, 5, so a par one hole off shows."""
    page = a_player(browser("t3-open"), "hal").get("/rounds/1/cards/new").text
    assert HOLE.findall(page) == [
        (str(hole), "", f"h{hole}", "", f"Hole {hole}, par {par}", f"par {par}")
        for hole, par in enumerate(PARS, start=1)
    ]
    assert screen(page)[:6] == [
        "\N{LEFTWARDS ARROW}",
        "Check the card",
        "Trinity Forest Golf Club",
        "White tee \N{MIDDLE DOT} Par 72",
        "Your 18 holes",
        "Out",
    ]
    assert HALF.findall(page) == [("Out", ""), ("In", "")]
    out, in_ = page.split('<span class="label grow">In</span>')
    assert [hole for hole, *_ in HOLE.findall(out)] == [str(hole) for hole in range(1, 10)]
    assert [hole for hole, *_ in HOLE.findall(in_)] == [str(hole) for hole in range(10, 19)]
    assert not TOTAL.findall(page)
    assert '<form id="card" class="card" method="post" action="/rounds/1/cards">' in page
    assert 'formmethod="get" formaction="/rounds/1/cards/new">Check the card</button>' in page


def test_section_7_check_the_card_reads_back_the_scores_with_out_in_and_total(
    browser: Browser,
) -> None:
    page = check(browser, "hal", 1, form_of(DESIGN)).text
    assert [value for _, _, _, value, _, _ in HOLE.findall(page)] == [str(s) for s in DESIGN]
    assert HALF.findall(page) == [("Out", "41"), ("In", "40")]
    assert TOTAL.findall(page) == ["81"]
    assert "White tee \N{MIDDLE DOT} Par 72" in screen(page)
    assert not WARN.findall(page)


def test_section_7_a_changed_hole_checked_again_reads_its_new_totals(browser: Browser) -> None:
    changed = form_of(DESIGN) | {"h5": "3"}
    page = check(browser, "hal", 1, changed).text
    assert HALF.findall(page) == [("Out", "38"), ("In", "40")]
    assert TOTAL.findall(page) == ["78"]


def outlined(page: str) -> list[str]:
    """The holes the screen outlines as in error, in hole order."""
    return [hole for hole, check, *_ in HOLE.findall(page) if check]


def test_section_7_an_empty_hole_is_outlined_and_named_with_no_totals(browser: Browser) -> None:
    response = check(browser, "hal", 1, form_of(DESIGN) | {"h5": ""})
    assert response.status_code == 200
    assert outlined(response.text) == ["5"]
    assert WARN.findall(response.text) == ["Looks like an error on hole 5."]
    assert HALF.findall(response.text) == [("Out", ""), ("In", "")]
    assert not TOTAL.findall(response.text)


def test_r13_a_score_over_19_and_one_that_is_no_number_are_named_in_hole_order(
    browser: Browser,
) -> None:
    """The kinds come in that order, so listing non-numbers first would read 12 and 5."""
    page = check(browser, "hal", 1, form_of(DESIGN) | {"h5": "20", "h12": "x"}).text
    assert outlined(page) == ["5", "12"]
    assert WARN.findall(page) == ["Looks like an error on holes 5 and 12."]
    assert HALF.findall(page) == [("Out", ""), ("In", "")]
    assert not TOTAL.findall(page)
    assert [value for _, _, name, value, _, _ in HOLE.findall(page) if name == "h12"] == [""]


def test_r13_a_score_of_19_checks_clean(browser: Browser) -> None:
    page = check(browser, "hal", 1, form_of(DESIGN) | {"h1": "19"}).text
    assert not outlined(page)
    assert not WARN.findall(page)


def test_section_7_a_hole_missing_from_the_form_is_outlined(browser: Browser) -> None:
    assert outlined(check(browser, "hal", 1, form_of(DESIGN[:17])).text) == ["18"]


def test_section_7_a_check_with_every_hole_empty_outlines_all_18(browser: Browser) -> None:
    """Only a request with no query at all is the screen before its first check."""
    empty = {f"h{hole}": "" for hole in range(1, 19)}
    assert outlined(check(browser, "hal", 1, empty).text) == [str(hole) for hole in range(1, 19)]


def test_section_7_card_entry_screens_are_never_stored(browser: Browser) -> None:
    """Back then asks the server again, which opens the round page once the card is in."""
    screens = (
        a_player(browser("t3-open"), "hal").get("/rounds/1/cards/new"),
        check(browser, "hal", 1, form_of(DESIGN)),
        hand_in(browser, "hal", 1, form_of(DESIGN) | {"h5": "0"}),
    )
    assert [(screen.status_code, screen.headers["cache-control"]) for screen in screens] == [
        (200, "no-store"),
        (200, "no-store"),
        (400, "no-store"),
    ]


def test_section_7_submit_card_is_enabled_only_after_a_clean_check(browser: Browser) -> None:
    empty = a_player(browser("t3-open"), "hal").get("/rounds/1/cards/new").text
    assert SUBMIT.findall(empty) == [" disabled"]
    assert SUBMIT.findall(check(browser, "hal", 1, form_of(DESIGN) | {"h5": "0"}).text) == [
        " disabled"
    ]
    assert SUBMIT.findall(check(browser, "hal", 1, form_of(DESIGN)).text) == [""]


def test_r15_card_entry_opens_the_round_page_once_the_card_is_in(browser: Browser) -> None:
    """gus's own card, red's team card for ann, and hal's card in closed round 2."""
    entries = (
        a_player(browser("t3-open"), "gus").get("/rounds/1/cards/new"),
        check(browser, "ann", 3, form_of(DESIGN)),
        check(browser, "ann", 1, form_of(DESIGN)),
        a_player(browser("t3-open"), "hal").get("/rounds/2/cards/new"),
    )
    assert [(entry.status_code, entry.headers["location"]) for entry in entries] == [
        (303, "/rounds/1"),
        (303, "/rounds/3"),
        (303, "/rounds/1"),
        (303, "/rounds/2"),
    ]


def test_r13_no_card_entry_for_a_closed_round_without_the_card_or_an_absent_one(
    browser: Browser,
) -> None:
    assert notice(a_player(browser("t3"), "hal").get("/rounds/1/cards/new")) == (404, NOT_OPEN)
    assert notice(a_player(browser("t3-open"), "hal").get("/rounds/9/cards/new")) == (
        404,
        NOT_OPEN,
    )


def test_r13_a_submitted_card_is_stored_and_lands_on_the_round_and_reads_card_in_on_home(
    browser: Browser, database: Engine
) -> None:
    response = hand_in(browser, "hal", 1, form_of(DESIGN))
    assert (response.status_code, response.headers["location"]) == (303, "/rounds/1")
    assert load(database, "t3-open").rounds[0].cards["hal"].scores == DESIGN
    hal, _ = blocks(home_of(browser, "t3-open", "hal"))
    assert PLAYER_ROW.findall(hal)[0] == ("hal", "15 strokes", "win", "Card in")


def test_r15_a_shared_ball_card_is_the_teams_and_reads_card_in_for_the_partner(
    browser: Browser, database: Engine
) -> None:
    assert hand_in(browser, "cam", 3, form_of(DESIGN)).status_code == 303
    round_3 = load(database, "t3-open").rounds[2]
    assert round_3.team_cards["blue"].scores == DESIGN
    assert "cam" not in round_3.cards
    _, dee = blocks(home_of(browser, "t3-open", "dee"))
    assert PLAYER_ROW.findall(dee) == [("Team", "4 strokes", "win", "Card in")]


@pytest.mark.parametrize(
    ("changes", "holes", "warn"),
    [
        pytest.param({"h1": "0"}, ["1"], "Looks like an error on hole 1.", id="zero"),
        pytest.param(
            {"h9": "five", "h10": "20"},
            ["9", "10"],
            "Looks like an error on holes 9 and 10.",
            id="no number and twenty",
        ),
    ],
)
def test_r13_a_submit_with_a_hole_in_error_shows_the_screen_and_stores_nothing(
    browser: Browser, database: Engine, changes: dict[str, str], holes: list[str], warn: str
) -> None:
    before = load(database, "t3-open")
    response = hand_in(browser, "hal", 1, form_of(DESIGN) | changes)
    assert response.status_code == 400
    assert outlined(response.text) == holes
    assert WARN.findall(response.text) == [warn]
    assert SUBMIT.findall(response.text) == [" disabled"]
    assert load(database, "t3-open") == before


@pytest.mark.parametrize("number", [1, 3], ids=["own ball", "shared ball"])
def test_r13_a_second_card_reads_already_in_on_the_notice(
    browser: Browser, database: Engine, number: int
) -> None:
    before = load(database, "t3-open")
    assert notice(hand_in(browser, "ann", number, form_of(DESIGN))) == (
        400,
        f"Your card for round {number} is already in. Ask the admin if it needs a correction.",
    )
    assert load(database, "t3-open") == before


def test_r13_a_card_from_outside_the_season_is_refused_in_the_domains_words(
    browser: Browser, database: Engine
) -> None:
    with database.begin() as connection:
        save_player(connection, "ivy", "ivy-link")
    before = load(database, "t3-open")
    response = hand_in(browser, "ivy", 1, form_of(DESIGN))
    assert notice(response) == (400, "round 1 does not take this card")
    assert load(database, "t3-open") == before


def test_card_entry_without_a_cookie_is_refused(browser: Browser) -> None:
    client = browser("t3-open")
    assert notice(client.get("/rounds/1/cards/new")) == (401, OPEN_YOUR_LINK)
    assert notice(client.get("/rounds/1/cards/new", params=form_of(DESIGN))) == (
        401,
        OPEN_YOUR_LINK,
    )
    assert notice(client.post("/rounds/1/cards", data=form_of(DESIGN))) == (401, OPEN_YOUR_LINK)


TEAM_ROW = re.compile(
    r'<div class="card( card--mine)? row"[^>]*><span class="grow"[^>]*>([^<]+)</span>'
    r'<span class="pill pill--(\w+)">([^<]+)</span></div>'
)
HIDDEN = "Scores stay hidden until your card is in, so nobody plays knowing the number they need."


def round_of(browser: Browser, season_id: str, number: int, player_id: str) -> Response:
    return a_player(browser(season_id), player_id).get(f"/rounds/{number}")


def test_section_7_hal_reads_round_1_before_playing_with_gold_one_of_two_cards(
    browser: Browser, database: Engine
) -> None:
    set_close(database, "t3-open", 1, datetime(2026, 11, 15, 21, 0))
    page = round_of(browser, "t3-open", 1, "hal").text
    assert screen(page) == [
        "Round 1",
        "Closes Sun 15 Nov, 22:00",
        HIDDEN,
        "Teams with a score",
        "3 of 4",
        "blue",
        "Score in",
        "gold",
        "1 of 2 cards",
        "green",
        "Score in",
        "red",
        "Score in",
        "Register card",
    ]
    assert TEAM_ROW.findall(page) == [
        ("", "blue", "win", "Score in"),
        (" card--mine", "gold", "muted", "1 of 2 cards"),
        ("", "green", "win", "Score in"),
        ("", "red", "win", "Score in"),
    ]
    assert BUTTON.findall(page) == [
        ("btn--primary btn--block", "/rounds/1/cards/new", "Register card")
    ]
    assert nav(page) == tabs("Round")


def test_section_7_cam_reads_round_3_before_playing_with_blue_not_yet(browser: Browser) -> None:
    page = round_of(browser, "t3-open", 3, "cam").text
    assert screen(page)[3:] == [
        "Teams with a score",
        "3 of 4",
        "blue",
        "Not yet",
        "gold",
        "Score in",
        "green",
        "Score in",
        "red",
        "Score in",
        "Register card",
    ]
    assert TEAM_ROW.findall(page)[0] == (" card--mine", "blue", "muted", "Not yet")
    assert BUTTON.findall(page) == [
        ("btn--primary btn--block", "/rounds/3/cards/new", "Register card")
    ]


def test_section_7_a_viewer_outside_the_season_reads_the_rows_without_register_card(
    browser: Browser, database: Engine
) -> None:
    with database.begin() as connection:
        save_player(connection, "ivy", "ivy-link")
    page = round_of(browser, "t3-open", 1, "ivy").text
    assert HIDDEN not in screen(page)
    assert [(mine, name, pill) for mine, name, _, pill in TEAM_ROW.findall(page)] == [
        ("", "blue", "Score in"),
        ("", "gold", "1 of 2 cards"),
        ("", "green", "Score in"),
        ("", "red", "Score in"),
    ]
    assert BUTTON.findall(page) == []


@pytest.mark.parametrize(
    ("season_id", "number", "player_id"), [("t3-open", 6, "hal"), ("s9b-open", 4, "ann")]
)
def test_section_7_a_round_not_in_the_season_or_of_an_individual_season_is_not_found(
    browser: Browser, season_id: str, number: int, player_id: str
) -> None:
    """Round 6 does not exist, and an individual season's round page is S21's."""
    assert notice(round_of(browser, season_id, number, player_id)) == (404, NOT_OPEN)


RANKED = re.compile(
    r'<div class="row"( style="color:var\(--brass\)")?><span style="width:118px">([^<]+)</span>'
    r'<span class="bar grow"><span class="bar__fill( bar__fill--mine)?" style="width:(\d+)%">'
    r"</span></span><span[^>]*>(\d+)</span></div>"
)


def test_section_7_gus_reads_round_5s_result_with_gold_beating_every_team(
    browser: Browser,
) -> None:
    page = round_of(browser, "t3", 5, "gus").text
    assert screen(page) == [
        "Round 5",
        "Trinity Forest Golf Club · Blue",
        "gold",
        "Foursome",
        "64",
        "team net",
        "No hole counts worse than net double bogey.",
        "Team",
        "79 gross · 13 strokes",
        "Against everyone",
        "3 of 3",
        "teams beaten",
        "gold",
        "64",
        "green",
        "65",
        "blue",
        "66",
        "red",
        "66",
        "Round 5 points",
        "3.0",
        "3rd → 2nd",
        "6.7 to 1st",
    ]
    assert RANKED.findall(page) == [
        (' style="color:var(--brass)"', "gold", " bar__fill--mine", "100", "64"),
        ("", "green", "", "67", "65"),
        ("", "blue", "", "17", "66"),
        ("", "red", "", "17", "66"),
    ]
    assert nav(page) == tabs("Round")


def test_section_7_hal_reads_round_2_with_his_row_before_his_partners(browser: Browser) -> None:
    lines = screen(round_of(browser, "t3", 2, "hal").text)
    assert lines[4:11] == [
        "141",
        "team net",
        "No hole counts worse than net double bogey.",
        "hal",
        "87 gross · 18 strokes",
        "gus",
        "82 gross · 8 strokes",
    ]
    assert lines[11:14] == ["Against everyone", "1.5 of 3", "teams beaten"]
    assert lines[-4:] == ["Round 2 points", "2.5", "4th → 4th", "0.3 to 3rd"]


def test_section_7_gus_reads_round_1_without_a_score_and_his_place_after_it(
    browser: Browser,
) -> None:
    lines = screen(round_of(browser, "t3", 1, "gus").text)
    assert lines[2:8] == [
        "gold",
        "Best ball",
        "No score this round.",
        "gus",
        "72 gross · 7 strokes",
        "hal",
    ]
    assert lines[8] == "No card · 15 strokes"
    assert lines[9:11] == ["Against everyone", "blue"]
    assert lines[-5:] == [
        "gold have no score this round.",
        "Round 1 points",
        DASH,
        "4th",
        "0.8 to 2nd",
    ]


def test_r12_ann_reads_open_round_3_with_its_points_and_no_place(browser: Browser) -> None:
    lines = screen(round_of(browser, "t3-open", 3, "ann").text)
    assert lines[9:12] == ["Against everyone", "1.5 of 2", "teams beaten"]
    assert lines[-3:] == ["blue have no score this round.", "Round 3 points", "2.3"]


def test_section_7_a_viewer_outside_the_season_reads_the_ranking_alone(
    browser: Browser, database: Engine
) -> None:
    with database.begin() as connection:
        save_player(connection, "ivy", "ivy-link")
    lines = screen(round_of(browser, "t3", 1, "ivy").text)
    assert lines == [
        "Round 1",
        "Trinity Forest Golf Club · White",
        "Against everyone",
        "blue",
        "66",
        "green",
        "67",
        "red",
        "67",
        "gold have no score this round.",
    ]


def test_r9_a_lone_team_reads_that_no_other_team_has_a_score(browser: Browser) -> None:
    lines = screen(round_of(browser, "one-team-card", 3, "ann").text)
    assert lines[9:] == [
        "Against everyone",
        "No other team has a score yet.",
        "blue, gold and green have no score this round.",
        "Round 3 points",
        DASH,
    ]


def test_round_without_a_cookie_is_refused(browser: Browser) -> None:
    assert notice(browser("t3-open").get("/rounds/1")) == (401, OPEN_YOUR_LINK)


def test_unknown_segment_is_not_found(browser: Browser) -> None:
    response = a_player(browser("s9b")).get("/standings?segment=nowhere")
    assert notice(response) == (404, "No such table.")


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
