import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from fixtures.database import a_copy, a_template
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from fixtures.team_season import t3_open
from league.domain.facts import Segment, StandingsRule
from league.services.clock import utc_now
from league.services.play import season_view
from league.services.setup import replace_link_token
from league.store.save import save_player, save_window
from league.web.app import create_app

TOKENS_CSS = Path(__file__).parents[2] / "docs" / "design" / "tokens.css"
DASH = "\N{EN DASH}"

ROW = re.compile(
    r'<span class="meta"[^>]*>(\d+)</span>'
    r'<span class="grow"[^>]*>([^<]+)</span>'
    r'<span class="fine">([^<]+)</span>'
    r'<span class="num"[^>]*>([^<]+)</span>'
)
TAB = re.compile(r'<a class="btn (btn--\w+) grow"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>')
CELL = re.compile(
    r'<div class="hole"><span class="hole__n">(R\d+)</span>'
    r'<span class="chip( chip--dropped)?"[^>]*>([^<]+)</span></div>'
)
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
NAV = re.compile(r'<a class="nav__item( nav__item--on)?" href="([^"]+)">([^<]+)</a>')
NO_ROUND = "No round is open right now."

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


def test_home_without_a_cookie_is_refused(browser: Browser) -> None:
    response = browser("t3").get("/")
    assert response.status_code == 401
    assert response.text == "Open your personal link."


def test_home_with_a_cookie_nobody_holds_is_refused(browser: Browser) -> None:
    client = browser("t3")
    client.cookies.set("link_token", "nobody-link")
    assert client.get("/").status_code == 401


def test_home_links_the_stylesheet_and_names_the_season(browser: Browser) -> None:
    page = home_of(browser, "t3", "gus")
    assert '<link rel="stylesheet" href="/static/app.css">' in page
    assert SEASON_LABEL.findall(page) == ["t3"]


def test_section_7_the_home_tab_is_on_both_screens_and_marks_its_own(browser: Browser) -> None:
    client = a_player(browser("t3"))
    assert NAV.findall(client.get("/").text) == [
        (" nav__item--on", "/", "Home"),
        ("", "/standings", "Standings"),
    ]
    assert NAV.findall(client.get("/standings").text) == [
        ("", "/", "Home"),
        (" nav__item--on", "/standings", "Standings"),
    ]


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


def test_section_7_home_has_no_buttons_until_s15d_and_s16(browser: Browser) -> None:
    assert "btn" not in home_of(browser, "t3-open", "gus")


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
    assert season_card(page) == [("2nd", "5.0 points"), ("8.0", "to 1st")]


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
