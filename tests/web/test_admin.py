import html
import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from test_app import ADMIN_TOKEN, an_app

from fixtures.database import golden_database
from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from league.domain.facts import Tee
from league.services.setup import create_tee, stored_tee

OPEN_YOUR_ADMIN_LINK = "Open your admin link."
NOTE = "Name the course and tee exactly as Trackman lists them"
RATING = "The course rating is a number with one decimal, such as 71.8."
WHOLE = "Slope, par and stroke index are whole numbers."
INPUT = re.compile(r'<input [^>]*name="([^"]+)" value="([^"]*)"')
READONLY = re.compile(r'<input [^>]*name="([^"]+)" value="[^"]*" readonly>')
WARN = re.compile(r'<p class="card card--warn help"[^>]*>([^<]+)</p>')
NOTICE = re.compile(r'<p class="card card--sunken help"[^>]*>([^<]+)</p>')
HEADING = re.compile(r'<h1 class="h1"[^>]*>([^<]+)</h1>')
PAR = re.compile(r'<span class="meta">Par</span><span class="num"[^>]*>(\d+)</span>')
NINES = re.compile(r'<div class="tablehead"[^>]*><span>(\w+ nine)</span>')
CHECK = "Stroke index uses 1 to 18 once each"
S9B_TEE = S9B.rounds[0].tee
WHITE = T3.rounds[0].tee
# Drawn in docs/design/admin-tee.html, whose course and tee T3 stores as White.
DESIGN = Tee(
    "Trinity Forest Golf Club",
    "White",
    (4, 5, 3, 4, 5, 4, 4, 3, 4, 5, 3, 4, 4, 4, 4, 5, 3, 4),
    (12, 8, 18, 2, 6, 10, 14, 16, 4, 7, 11, 13, 3, 15, 9, 5, 17, 1),
    718,
    129,
)
BLACK = replace(DESIGN, name="Black")
# Shares no number with the design or the fixtures, whose tees all have par 72.
UNDRAWN = Tee(
    "Cabot Citrus Farms Karoo",
    "Blue",
    (4, 4, 3, 5) * 4 + (5, 4),
    tuple(range(18, 0, -1)),
    694,
    118,
)
FIELDS = (
    "course",
    "tee",
    "rating",
    "slope",
    *(f"par{hole}" for hole in range(1, 19)),
    *(f"si{hole}" for hole in range(1, 19)),
)

Visitor = Callable[[TestClient], TestClient]


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[FastAPI]:
    """The app on both golden seasons."""
    golden_database(tmp_path).dispose()
    app = an_app(monkeypatch, tmp_path / "league.db", "t3")
    yield app
    app.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """A browser that has followed no link yet."""
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def admin(client: TestClient) -> TestClient:
    """That browser once it has opened the admin's link."""
    client.get(f"/admin/k/{ADMIN_TOKEN}")
    return client


def a_form(tee: Tee, rating: str = "", slope: str = "") -> dict[str, str]:
    """The tee form filled with the tee, its rating or slope as typed when one is given."""
    whole, tenth = divmod(tee.course_rating_tenths, 10)
    return {
        "course": tee.course,
        "tee": tee.name,
        "rating": rating or f"{whole}.{tenth}",
        "slope": slope or str(tee.slope),
        **{f"par{hole}": str(par) for hole, par in enumerate(tee.pars, 1)},
        **{f"si{hole}": str(index) for hole, index in enumerate(tee.stroke_indexes, 1)},
    }


def the_page_of(tee: Tee) -> str:
    return f"/admin/tees/change?{urlencode({'course': tee.course, 'tee': tee.name})}"


def values(response: Response) -> dict[str, str]:
    return {name: html.unescape(value) for name, value in INPUT.findall(response.text)}


def warns(response: Response) -> list[str]:
    return [html.unescape(text) for text in WARN.findall(response.text)]


def stored(app: FastAPI, tee: Tee) -> Tee | None:
    return stored_tee(app.state.engine, tee.course, tee.name)


def test_admin_link_sets_the_cookie_and_lands_on_tees(client: TestClient) -> None:
    response = client.get(f"/admin/k/{ADMIN_TOKEN}")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/tees"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/admin/tees").status_code == 200


@pytest.mark.parametrize("path", ["/admin/k/wrong", "/admin/k/%C3%B8", "/admin/k/ann-link"])
def test_a_wrong_admin_link_is_refused_and_sets_no_cookie(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 401
    assert NOTICE.findall(response.text) == [OPEN_YOUR_ADMIN_LINK]
    assert "set-cookie" not in response.headers


def no_cookie(client: TestClient) -> TestClient:
    return client


def a_player(client: TestClient) -> TestClient:
    client.get("/k/ann-link")
    return client


def a_wrong_cookie(client: TestClient) -> TestClient:
    client.cookies.set("admin_token", "wrong")
    return client


@pytest.mark.parametrize("visitor", [no_cookie, a_player, a_wrong_cookie])
def test_admin_pages_refuse_a_visit_without_the_admin_cookie(
    app: FastAPI, client: TestClient, visitor: Visitor
) -> None:
    create_tee(app.state.engine, UNDRAWN)
    browser = visitor(client)
    responses = [
        browser.get("/admin/tees"),
        browser.post("/admin/tees", data=a_form(BLACK)),
        browser.get(the_page_of(UNDRAWN)),
        browser.post("/admin/tees/change", data=a_form(UNDRAWN, slope="140")),
    ]
    for response in responses:
        assert response.status_code == 401
        assert NOTICE.findall(response.text) == [OPEN_YOUR_ADMIN_LINK]
    assert stored(app, BLACK) is None
    assert stored(app, UNDRAWN) == UNDRAWN


def test_add_a_tee_opens_an_empty_form(admin: TestClient) -> None:
    response = admin.get("/admin/tees")
    assert HEADING.findall(response.text) == ["Add a course and tee"]
    assert values(response) == dict.fromkeys(FIELDS, "")
    assert READONLY.findall(response.text) == []
    assert NOTE in warns(response)[0]
    assert PAR.findall(response.text) == []


def test_the_tee_screen_has_the_player_pages_width(app: FastAPI, admin: TestClient) -> None:
    """Drawn for the phone first, in one column under the season's name."""
    create_tee(app.state.engine, UNDRAWN)
    for path in ("/admin/tees", the_page_of(UNDRAWN)):
        text = admin.get(path).text
        assert '<main class="page stack">' in text
        assert "page--wide" not in text
        assert "t3 &middot; Admin" in text


def test_add_a_tee_stores_the_design_tee_and_opens_its_page(
    app: FastAPI, admin: TestClient
) -> None:
    """Under the name Black, since T3 stores the design's course and tee as White."""
    response = admin.post("/admin/tees", data=a_form(BLACK, rating="71.8"))
    assert response.status_code == 303
    assert response.headers["location"] == the_page_of(BLACK)
    assert stored(app, BLACK) == BLACK


def test_a_course_holding_a_slash_and_an_ampersand_opens_its_own_page(
    app: FastAPI, admin: TestClient
) -> None:
    tee = replace(UNDRAWN, course="Pebble & Spyglass / Links")
    response = admin.post("/admin/tees", data=a_form(tee))
    assert stored(app, tee) == tee
    page = admin.get(response.headers["location"])
    assert page.status_code == 200
    assert values(page)["course"] == "Pebble & Spyglass / Links"


def test_a_stored_tee_reads_back_its_numbers(app: FastAPI, admin: TestClient) -> None:
    create_tee(app.state.engine, UNDRAWN)
    response = admin.get(the_page_of(UNDRAWN))
    assert HEADING.findall(response.text) == ["Change a tee"]
    shown = values(response)
    assert (shown["course"], shown["tee"], shown["rating"], shown["slope"]) == (
        "Cabot Citrus Farms Karoo",
        "Blue",
        "69.4",
        "118",
    )
    assert [shown[f"par{hole}"] for hole in range(1, 19)] == [str(par) for par in UNDRAWN.pars]
    assert [shown[f"si{hole}"] for hole in range(1, 19)] == [str(i) for i in range(18, 0, -1)]
    assert PAR.findall(response.text) == ["73"]
    assert NINES.findall(response.text) == ["Front nine", "Back nine"]
    assert CHECK in response.text


def test_a_stored_tee_has_its_course_and_tee_read_only(app: FastAPI, admin: TestClient) -> None:
    create_tee(app.state.engine, UNDRAWN)
    assert READONLY.findall(admin.get(the_page_of(UNDRAWN)).text) == ["course", "tee"]


REPEATED = a_form(BLACK) | {"si18": "12"}
PAR_7 = a_form(BLACK) | {"par1": "7"}


@pytest.mark.parametrize(
    ("form", "refusal"),
    [
        pytest.param(REPEATED, "stroke indexes are 1 to 18, once each", id="r13-repeated-index"),
        pytest.param(PAR_7, "every par is 3 to 6", id="r13-par-of-7"),
        pytest.param(a_form(BLACK, rating="71.85"), RATING, id="rating-71.85"),
        pytest.param(a_form(BLACK, rating="abc"), RATING, id="rating-abc"),
        pytest.param(a_form(BLACK, rating="nan"), RATING, id="rating-nan"),
        pytest.param(a_form(BLACK, rating="1e999999"), RATING, id="rating-overflow"),
        pytest.param(a_form(BLACK, slope="12x"), WHOLE, id="slope-no-number"),
        pytest.param(a_form(BLACK, rating="abc", slope="12x"), RATING, id="rating-read-first"),
        pytest.param(a_form(BLACK) | {"course": " "}, "a tee has a course name", id="no-course"),
        pytest.param(
            a_form(BLACK, slope="99999999999999999999"), "a slope is 55 to 155", id="r13-huge-slope"
        ),
        pytest.param(a_form(BLACK, slope="0"), "a slope is 55 to 155", id="r13-slope-0"),
        pytest.param(
            a_form(BLACK, rating="1e20"), "a course rating is 50.0 to 90.0", id="r13-huge-rating"
        ),
    ],
)
def test_a_refused_tee_shows_the_form_as_typed_with_its_refusal(
    app: FastAPI, admin: TestClient, form: dict[str, str], refusal: str
) -> None:
    response = admin.post("/admin/tees", data=form)
    assert response.status_code == 400
    assert warns(response) == [refusal]
    assert values(response) == form
    assert PAR.findall(response.text) == []
    assert stored(app, BLACK) is None


def test_a_missing_field_is_refused_as_no_number(app: FastAPI, admin: TestClient) -> None:
    form = a_form(BLACK)
    del form["si9"]
    response = admin.post("/admin/tees", data=form)
    assert warns(response) == [WHOLE]
    assert values(response)["si9"] == ""
    assert stored(app, BLACK) is None


def test_course_and_tee_are_trimmed_at_the_ends(app: FastAPI, admin: TestClient) -> None:
    form = a_form(BLACK) | {"course": "  Trinity Forest Golf Club ", "tee": " Black  "}
    response = admin.post("/admin/tees", data=form)
    assert response.headers["location"] == the_page_of(BLACK)
    assert stored(app, BLACK) == BLACK


def test_a_second_tee_of_one_course_and_name_is_refused(app: FastAPI, admin: TestClient) -> None:
    response = admin.post("/admin/tees", data=a_form(DESIGN))
    assert response.status_code == 400
    assert warns(response) == ["tee White of Trinity Forest Golf Club is already stored"]
    assert stored(app, DESIGN) == WHITE


@pytest.mark.parametrize(("rating", "tenths"), [("72.0", 720), ("72", 720), ("71.80", 718)])
def test_change_a_tee_rerates_it(app: FastAPI, admin: TestClient, rating: str, tenths: int) -> None:
    create_tee(app.state.engine, UNDRAWN)
    response = admin.post("/admin/tees/change", data=a_form(UNDRAWN, rating=rating))
    assert response.status_code == 303
    assert response.headers["location"] == the_page_of(UNDRAWN)
    assert stored(app, UNDRAWN) == replace(UNDRAWN, course_rating_tenths=tenths)


def test_r14_a_tee_with_a_card_is_not_changed(app: FastAPI, admin: TestClient) -> None:
    response = admin.post("/admin/tees/change", data=a_form(S9B_TEE, slope="140"))
    assert response.status_code == 400
    assert warns(response) == ["tee White of Old Links has a card on it"]
    assert READONLY.findall(response.text) == ["course", "tee"]
    assert PAR.findall(response.text) == []
    assert CHECK not in response.text
    assert stored(app, S9B_TEE) == S9B_TEE


def test_a_change_of_a_tee_nobody_stored_is_refused(app: FastAPI, admin: TestClient) -> None:
    response = admin.post("/admin/tees/change", data=a_form(UNDRAWN))
    assert response.status_code == 400
    assert warns(response) == ["no tee Blue of Cabot Citrus Farms Karoo"]
    assert stored(app, UNDRAWN) is None


def test_the_page_of_a_tee_nobody_stored_reads_no_such_tee(admin: TestClient) -> None:
    response = admin.get(the_page_of(UNDRAWN))
    assert response.status_code == 404
    assert NOTICE.findall(response.text) == ["No such tee."]
