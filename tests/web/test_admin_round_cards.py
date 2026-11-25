"""The Cards card on a round's screen, with Void asking once in its row (R13, R15)."""

import html
import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine
from test_admin import NOTICE, OPEN_YOUR_ADMIN_LINK, Visitor, a_player, a_wrong_cookie, no_cookie
from test_admin_round import a_draft, actions, state
from test_app import ADMIN_TOKEN, an_app

from fixtures.database import a_copy, a_template, everything, load
from fixtures.team_season import t3_open

# Each row of the Cards card is one line with its id, whose texts and paths read in order.
ROW = re.compile(
    r'^\s*<div id="([^"]+)" class="card card--sunken[^"]*" style="padding:10px 12px">(.*)$', re.M
)
TOKEN = re.compile(r'(?:href|action)="([^"]+)"|>([^<>]+)<')
CARDS = '<div class="label" style="margin-bottom:10px">Cards</div>'
ROUND_CARD = '<div class="label">The round</div>'
OPEN_ASK = "now? Players can hand in cards"
VOID_ANN = (
    "Void ann's card? It stops counting and cannot be undone. "
    "ann can hand in a new one while the round is open."
)
ANN = "/admin/rounds/1/cards/r1-ann/void"
# The fragment that opens the page on ann's row. A redirect without one keeps the posted URL's.
AT_ANN = "#row-ann"

Admin = Callable[[str], TestClient]


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
def admin(browse: Callable[[str], TestClient]) -> Admin:
    def an_admin(season_id: str) -> TestClient:
        client = browse(season_id)
        client.get(f"/admin/k/{ADMIN_TOKEN}")
        return client

    return an_admin


def card_rows(response: Response) -> list[list[str]]:
    """Each row of the Cards card as its texts and the paths it links or posts to, in order."""
    return [
        [
            html.unescape(path or text)
            for path, text in TOKEN.findall(line)
            if (path or text).strip()
        ]
        for _, line in ROW.findall(response.text)
    ]


def row_ids(response: Response) -> list[str]:
    return [row_id for row_id, _ in ROW.findall(response.text)]


def assert_opens(response: Response, number: int) -> None:
    assert response.status_code == 303
    assert response.headers["location"] == f"/admin/rounds/{number}"


def test_r15_the_cards_card_sits_under_the_state_card_and_above_the_round_card(
    admin: Admin,
) -> None:
    text = admin("t3-open").get("/admin/rounds/1").text
    assert text.index('<span class="pill ') < text.index(CARDS) < text.index(ROUND_CARD)


@pytest.mark.parametrize(
    ("number", "holders"),
    [
        pytest.param(1, ["cam", "dee", "gus", "hal", "eve", "fay", "ann", "bob"], id="own-ball"),
        pytest.param(3, ["blue", "gold", "green", "red"], id="shared-ball"),
    ],
)
def test_each_row_has_an_id_from_its_holder(admin: Admin, number: int, holders: list[str]) -> None:
    """From the holder, not the card, so a voided row keeps the id its Void opened it on."""
    response = admin("t3-open").get(f"/admin/rounds/{number}")
    assert row_ids(response) == [f"row-{holder}" for holder in holders]


def test_r15_an_own_ball_rounds_cards_list_every_player_in_team_order(admin: Admin) -> None:
    rows = card_rows(admin("t3-open").get("/admin/rounds/1"))
    assert [row[0] for row in rows] == ["cam", "dee", "gus", "hal", "eve", "fay", "ann", "bob"]
    assert rows[0] == [
        "cam",
        "76",
        "In Mon 5 Jan, 19:00",
        "/admin/rounds/1/cards/r1-cam/correct",
        "Correct",
        "/admin/rounds/1/cards/r1-cam/void#row-cam",
        "Void",
    ]
    assert rows[3] == ["hal", "No card"]


def test_r15_a_shared_ball_rounds_cards_list_every_team(admin: Admin) -> None:
    rows = card_rows(admin("t3-open").get("/admin/rounds/3"))
    assert [row[:3] for row in rows] == [
        ["blue", "No card"],
        ["gold", "76", "In Mon 19 Jan, 19:00"],
        ["green", "77", "In Mon 19 Jan, 19:00"],
        ["red", "72", "In Mon 19 Jan, 19:00"],
    ]
    assert rows[1][3:] == [
        "/admin/rounds/3/cards/r3-gold/correct",
        "Correct",
        "/admin/rounds/3/cards/r3-gold/void#row-gold",
        "Void",
    ]


def test_r13_a_closed_rounds_late_card_reads_as_any_counted_card(admin: Admin) -> None:
    """green's team card for round 4 came in an hour after the close."""
    rows = card_rows(admin("t3").get("/admin/rounds/4"))
    assert [row[:3] for row in rows] == [
        ["blue", "78", "In Mon 26 Jan, 19:00"],
        ["gold", "80", "In Mon 26 Jan, 19:00"],
        ["green", "72", "In Tue 27 Jan, 00:00"],
        ["red", "72", "In Mon 26 Jan, 19:00"],
    ]


def test_r13_void_asks_once_in_its_row_and_stores_nothing(admin: Admin, database: Engine) -> None:
    before = everything(database)
    response = admin("t3-open").get(ANN)
    assert response.status_code == 200
    assert everything(database) == before
    rows = card_rows(response)
    assert rows[6] == [
        "ann",
        "76",
        VOID_ANN,
        ANN + AT_ANN,
        "Yes, void it",
        "/admin/rounds/1" + AT_ANN,
        "Cancel",
    ]
    assert row_ids(response)[6] == "row-ann"
    assert response.text.count("Void ann&#39;s card?") == 1
    assert [row[-1] for i, row in enumerate(rows) if i not in (3, 6)] == ["Void"] * 6
    assert [name for _, name, _ in state(response)] == ["Open"]
    assert actions(response) == [
        ("/admin/rounds/1/close", "Close round"),
        (ANN + AT_ANN, "Yes, void it"),
    ]
    assert OPEN_ASK not in response.text
    assert ROUND_CARD not in response.text


@pytest.mark.parametrize(
    ("season_id", "number", "card_id"),
    [
        pytest.param("t3-open", 1, "r1-ann", id="open-round"),
        pytest.param("t3", 5, "r5-gold", id="closed-round"),
    ],
)
def test_r13_yes_voids_that_card_alone(
    admin: Admin, database: Engine, season_id: str, number: int, card_id: str
) -> None:
    """Yes posts to the void path with its row's fragment, and the redirect names none, so the
    browser keeps the posted fragment and opens the round's page on that row."""
    before = load(database, season_id)
    client = admin(season_id)
    assert_opens(client.post(f"/admin/rounds/{number}/cards/{card_id}/void"), number)
    round_ = before.rounds[number - 1]
    held = {**round_.cards, **round_.team_cards}
    holder = next(key for key, card in held.items() if card.card_id == card_id)
    voided = replace(
        round_,
        cards={key: card for key, card in round_.cards.items() if key != holder},
        team_cards={key: card for key, card in round_.team_cards.items() if key != holder},
    )
    rounds = tuple(voided if r.number == number else r for r in before.rounds)
    assert load(database, season_id) == replace(before, rounds=rounds)
    page = client.get(f"/admin/rounds/{number}")
    assert [holder, "No card"] in card_rows(page)
    assert f"row-{holder}" in row_ids(page)


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(ANN, id="second-yes"),
        pytest.param("/admin/rounds/1/cards/r1-nobody/void", id="unknown-card"),
        pytest.param("/admin/rounds/99/cards/r1-ann/void", id="second-yes-under-no-round"),
    ],
)
def test_r13_a_void_that_is_not_allowed_stores_nothing(
    admin: Admin, database: Engine, path: str
) -> None:
    client = admin("t3-open")
    client.post(ANN)
    before = everything(database)
    assert_opens(client.post(path), int(path.split("/")[3]))
    assert everything(database) == before


def test_r13_the_ask_for_an_unknown_card_asks_in_no_row(admin: Admin, database: Engine) -> None:
    before = everything(database)
    response = admin("t3-open").get("/admin/rounds/1/cards/r1-nobody/void")
    assert response.status_code == 200
    assert everything(database) == before
    assert ROUND_CARD in response.text
    assert "Yes, void it" not in response.text
    assert [row[-1] for row in card_rows(response) if row[1] != "No card"] == ["Void"] * 7


@pytest.mark.parametrize("number", [pytest.param(6, id="draft"), pytest.param(99, id="no-round")])
def test_r13_the_ask_on_a_draft_or_no_round_opens_its_page(
    admin: Admin, database: Engine, number: int
) -> None:
    a_draft(database)
    before = everything(database)
    assert_opens(admin("t3").get(f"/admin/rounds/{number}/cards/r1-ann/void"), number)
    assert everything(database) == before


@pytest.mark.parametrize(
    ("season_id", "path"),
    [
        pytest.param("t3", "/admin/rounds/6", id="draft"),
        pytest.param("t3", "/admin/rounds/6/open", id="open-round-asking"),
        pytest.param("t3", "/admin/rounds/new", id="new-round"),
        pytest.param("s9b", "/admin/rounds/1", id="individual-season"),
    ],
)
def test_r15_no_cards_card_on_a_draft_a_new_round_or_an_individual_season(
    admin: Admin, database: Engine, season_id: str, path: str
) -> None:
    a_draft(database)
    response = admin(season_id).get(path)
    assert response.status_code == 200
    assert CARDS not in response.text
    assert card_rows(response) == []


@pytest.mark.parametrize("visitor", [no_cookie, a_player, a_wrong_cookie])
def test_void_refuses_a_visit_without_the_admin_cookie(
    browse: Callable[[str], TestClient], database: Engine, visitor: Visitor
) -> None:
    browser = visitor(browse("t3-open"))
    before = everything(database)
    for response in (browser.get(ANN), browser.post(ANN)):
        assert response.status_code == 401
        assert NOTICE.findall(response.text) == [OPEN_YOUR_ADMIN_LINK]
    assert everything(database) == before
