"""Correct on a round's Cards card: Check the card for that row, filled with its card (R13)."""

from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from test_admin import NOTICE, OPEN_YOUR_ADMIN_LINK, Visitor, a_player, a_wrong_cookie, no_cookie
from test_admin_round_cards import assert_opens, card_rows
from test_app import (
    ADMIN_TOKEN,
    DESIGN,
    HALF,
    HOLE,
    NAV,
    SUBMIT,
    TOTAL,
    WARN,
    an_app,
    check,
    form_of,
    screen,
)

from fixtures.database import a_copy, a_template, everything, load
from fixtures.team_season import t3_open

CAM = "/admin/rounds/1/cards/r1-cam/correct"
CLOSING_LINE = "A mistake after you submit is fixed by the admin."


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return a_template(tmp_path_factory.mktemp("template"), {"t3-open": t3_open()})


@pytest.fixture
def database(tmp_path: Path, template: Path) -> Iterator[Engine]:
    engine = a_copy(template, tmp_path)
    yield engine
    engine.dispose()


@pytest.fixture
def browse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, database: Engine
) -> Iterator[Callable[[str], TestClient]]:
    apps: list[FastAPI] = []

    def a_browser(season_id: str) -> TestClient:
        apps.append(an_app(monkeypatch, tmp_path / "league.db", season_id))
        return TestClient(apps[-1], follow_redirects=False)

    yield a_browser
    for app in apps:
        app.state.engine.dispose()


@pytest.fixture
def admin(browse: Callable[[str], TestClient]) -> TestClient:
    client = browse("t3-open")
    client.get(f"/admin/k/{ADMIN_TOKEN}")
    return client


def correct_of(row: list[str]) -> list[str]:
    """The Correct link in a row and what follows it, or nothing in a row without one."""
    return row[row.index("Correct") - 1 :] if "Correct" in row else []


def test_r13_correct_sits_before_void_in_each_row_with_a_card(admin: TestClient) -> None:
    rows = card_rows(admin.get("/admin/rounds/1"))
    assert rows[0] == [
        "cam",
        "76",
        "In Mon 5 Jan, 19:00",
        CAM,
        "Correct",
        "/admin/rounds/1/cards/r1-cam/void#row-cam",
        "Void",
    ]
    assert rows[3] == ["hal", "No card"]


@pytest.mark.parametrize(
    ("number", "holder", "card_id"),
    [
        pytest.param(3, "gold", "r3-gold", id="shared-ball"),
        pytest.param(5, "gold", "r5-gold", id="closed-round"),
    ],
)
def test_r13_correct_is_on_a_shared_ball_and_a_closed_rounds_rows(
    admin: TestClient, number: int, holder: str, card_id: str
) -> None:
    rows = card_rows(admin.get(f"/admin/rounds/{number}"))
    row = next(row for row in rows if row[0] == holder)
    assert correct_of(row)[:2] == [f"/admin/rounds/{number}/cards/{card_id}/correct", "Correct"]
    assert all(correct_of(row) for row in rows if row[1] != "No card")


def test_r13_correct_opens_check_the_card_filled_with_the_card(
    admin: TestClient, database: Engine
) -> None:
    before = everything(database)
    response = admin.get(CAM)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert everything(database) == before
    page = response.text
    cam = t3_open().rounds[0].cards["cam"]
    assert [value for *_, value, _, _ in HOLE.findall(page)] == [str(s) for s in cam.scores]
    assert screen(page)[:5] == [
        "\N{LEFTWARDS ARROW}",
        "Check the card",
        "Trinity Forest Golf Club",
        "White tee \N{MIDDLE DOT} Par 72",
        "cam's 18 holes",
    ]
    assert TOTAL.findall(page) == ["76"]
    assert SUBMIT.findall(page) == [""]
    assert CLOSING_LINE not in screen(page)
    assert 'href="/admin/rounds/1#row-cam" aria-label="Back"' in page
    assert f'method="post" action="{CAM}#row-cam">' in page
    assert f'formmethod="get" formaction="{CAM}">Check the card</button>' in page
    assert ("nav__item--on", "/admin/rounds", "Rounds") in [
        ("nav__item--on" if on else "", href, name) for on, href, name in NAV.findall(page)
    ]


def test_r13_a_correction_checked_with_an_empty_hole_outlines_it(admin: TestClient) -> None:
    page = admin.get(CAM, params=form_of(DESIGN) | {"h5": ""}).text
    assert [hole for hole, outlined, *_ in HOLE.findall(page) if outlined] == ["5"]
    assert WARN.findall(page) == ["Looks like an error on hole 5."]
    assert HALF.findall(page) == [("Out", ""), ("In", "")]
    assert SUBMIT.findall(page) == [" disabled"]


@pytest.mark.parametrize(
    ("number", "card_id", "holder"),
    [
        pytest.param(1, "r1-cam", "cam", id="open-round"),
        pytest.param(5, "r5-gold", "gold", id="closed-round"),
    ],
)
def test_r13_submit_card_replaces_the_scores_and_keeps_submitted_at(
    admin: TestClient, database: Engine, number: int, card_id: str, holder: str
) -> None:
    before = load(database, "t3-open")
    path = f"/admin/rounds/{number}/cards/{card_id}/correct"
    assert_opens(admin.post(path, data=form_of(DESIGN)), number)
    round_ = before.rounds[number - 1]
    held = "team_cards" if holder in round_.team_cards else "cards"
    cards = getattr(round_, held)
    corrected = replace(cards[holder], scores=DESIGN)
    rounds = tuple(
        replace(r, **{held: {**cards, holder: corrected}}) if r.number == number else r
        for r in before.rounds
    )
    assert load(database, "t3-open") == replace(before, rounds=rounds)


def test_r13_submit_card_with_a_hole_in_error_stores_nothing_and_redraws(
    admin: TestClient, database: Engine
) -> None:
    before = everything(database)
    response = admin.post(CAM, data=form_of(DESIGN) | {"h5": ""})
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert everything(database) == before
    page = response.text
    assert "cam's 18 holes" in screen(page)
    assert WARN.findall(page) == ["Looks like an error on hole 5."]
    assert f'method="post" action="{CAM}#row-cam">' in page
    assert ("/admin/rounds", "Rounds") in [(href, name) for _, href, name in NAV.findall(page)]


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/admin/rounds/1/cards/r1-nobody/correct", id="unknown-card"),
        pytest.param("/admin/rounds/1/cards/r3-gold/correct", id="another-rounds-card"),
        pytest.param("/admin/rounds/99/cards/r1-cam/correct", id="no-round"),
    ],
)
def test_r13_a_correction_no_row_holds_stores_nothing(
    admin: TestClient, database: Engine, path: str
) -> None:
    before = everything(database)
    number = int(path.split("/")[3])
    assert_opens(admin.get(path), number)
    assert_opens(admin.post(path, data=form_of(DESIGN)), number)
    assert everything(database) == before


@pytest.mark.parametrize("visitor", [no_cookie, a_player, a_wrong_cookie])
def test_correct_refuses_a_visit_without_the_admin_cookie(
    browse: Callable[[str], TestClient], database: Engine, visitor: Visitor
) -> None:
    browser = visitor(browse("t3-open"))
    before = everything(database)
    for response in (browser.get(CAM), browser.post(CAM, data=form_of(DESIGN))):
        assert response.status_code == 401
        assert NOTICE.findall(response.text) == [OPEN_YOUR_ADMIN_LINK]
    assert everything(database) == before


def test_section_7_the_players_check_the_card_is_unchanged(
    browse: Callable[[str], TestClient],
) -> None:
    page = check(browse, "hal", 1, form_of(DESIGN)).text
    assert "Your 18 holes" in screen(page)
    assert CLOSING_LINE in screen(page)
    assert '<form id="card" class="card" method="post" action="/rounds/1/cards">' in page
    assert not NAV.findall(page)
