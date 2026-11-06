"""The app: a personal link that sets the cookie, and one route per screen.

Everything a request needs sits on `app.state`, since nothing here is module-level state. Routes
are added by name because vulture reads a decorated route as unused.
"""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from league.domain.facts import HOLES
from league.services.clock import utc_now
from league.services.play import (
    Submission,
    bay_view,
    card_entry_view,
    home_view,
    player_for_link_token,
    season_view,
    submit_card,
)
from league.services.runtime import open_database

_HERE = Path(__file__).parent
_COOKIE = "link_token"
# Long enough to outlive the phone's browser closing; a browser caps a cookie at 400 days.
_COOKIE_MAX_AGE = 400 * 24 * 60 * 60
_ZONE = ZoneInfo("Europe/Oslo")


def _refused() -> Response:
    return PlainTextResponse("Open your personal link.", status.HTTP_401_UNAUTHORIZED)


def _link(request: Request, link_token: str) -> Response:
    """Open a player's personal link. Whoever opens it is that player (D7)."""
    if player_for_link_token(request.app.state.engine, link_token) is None:
        return _refused()
    response = RedirectResponse("/", status.HTTP_303_SEE_OTHER)
    response.set_cookie(_COOKIE, link_token, max_age=_COOKIE_MAX_AGE, httponly=True, samesite="lax")
    return response


def _viewer(request: Request) -> str | None:
    """The player the cookie names, read on every request so a replaced link stops at once."""
    link_token = request.cookies.get(_COOKIE)
    if link_token is None:
        return None
    return player_for_link_token(request.app.state.engine, link_token)


def _local_time(moment: datetime) -> str:
    """A stored naive UTC time on the league's clock, with its date, as a round runs for weeks."""
    local = moment.replace(tzinfo=UTC).astimezone(_ZONE)
    return f"{local:%a} {local.day} {local:%b}, {local:%H:%M}"


def _home(request: Request) -> Response:
    """The viewer's open rounds and their place in the season (SPEC section 7)."""
    viewer = _viewer(request)
    if viewer is None:
        return _refused()
    state = request.app.state
    view = home_view(state.engine, state.season_id, viewer, utc_now())
    context = {"view": view, "season": state.season_id, "local_time": _local_time}
    return state.templates.TemplateResponse(request, "home.html", context)


def _standings(request: Request, segment: str | None = None) -> Response:
    """The season's table, or one segment's (R10). Every viewer reads the same one (R12)."""
    viewer = _viewer(request)
    if viewer is None:
        return _refused()
    state = request.app.state
    view = season_view(state.engine, state.season_id, viewer, utc_now())
    tables = {table.name: table for table in view.segments}
    if segment is not None and segment not in tables:
        return PlainTextResponse("No such table.", status.HTTP_404_NOT_FOUND)
    table = None if segment is None else tables[segment]
    rows = view.standings if table is None else table.rows
    context = {
        "rows": rows,
        "best_n": view.best_n if table is None else table.best_n,
        "mine": next((row for row in rows if row.competitor_id == view.viewer_competitor), None),
        # No team's id is a seeded player's (R15), so "You" stays out of a team season (section 7).
        "you": view.viewer_competitor == viewer,
        "segments": tuple(tables),
        "segment": segment,
        "winners": tuple(round_ for round_ in reversed(view.rounds) if round_.winners),
    }
    return state.templates.TemplateResponse(request, "standings.html", context)


def _bay(request: Request, number: int) -> Response:
    """How to set up the simulator for one open round (SPEC section 7)."""
    viewer = _viewer(request)
    if viewer is None:
        return _refused()
    state = request.app.state
    bay = bay_view(state.engine, state.season_id, number)
    if bay is None:
        return PlainTextResponse("No such round.", status.HTTP_404_NOT_FOUND)
    return state.templates.TemplateResponse(request, "bay.html", {"bay": bay})


async def _scores(request: Request) -> tuple[int | None, ...]:
    """The form's scores, h1 to h18 in hole order, None where a hole is missing or no whole number.

    Their bound is Card's (R13): the screen outlines a hole it would refuse, and Card refuses it.
    """
    form = await request.form()
    scores: list[int | None] = []
    for hole in range(1, HOLES + 1):
        value = form.get(f"h{hole}")
        try:
            scores.append(int(value) if isinstance(value, str) else None)
        except ValueError:
            scores.append(None)
    return tuple(scores)


_Scores = Annotated[tuple[int | None, ...], Depends(_scores)]


def _card(request: Request, number: int, scores: tuple[int | None, ...]) -> Response:
    """Check the card with the scores typed so far, while the round takes the viewer's card."""
    viewer = _viewer(request)
    if viewer is None:
        return _refused()
    state = request.app.state
    submission = Submission(state.season_id, number, viewer, scores)
    entry = card_entry_view(state.engine, submission, utc_now())
    if entry is None:
        return PlainTextResponse("No such round.", status.HTTP_404_NOT_FOUND)
    return state.templates.TemplateResponse(request, "submit-confirm.html", {"entry": entry})


def _new_card(request: Request, number: int) -> Response:
    """Register card: the screen with 18 empty inputs (SPEC section 7)."""
    return _card(request, number, ())


def _check_card(request: Request, number: int, scores: _Scores) -> Response:
    """The same screen with the scores as typed, each hole in error outlined, as often as asked."""
    return _card(request, number, scores)


def _submit_card(request: Request, number: int, scores: _Scores) -> Response:
    """Hand the card in (R13, R15) and go home, where it reads "Card in".

    A hole in error brings the screen back with it outlined, so the route asks the screen's use
    case before the write (ARCHITECTURE's one exception). Any other refusal says why in the
    domain's own words.
    """
    viewer = _viewer(request)
    if viewer is None:
        return _refused()
    state = request.app.state
    now = utc_now()
    submission = Submission(state.season_id, number, viewer, scores)
    entry = card_entry_view(state.engine, submission, now)
    if entry is not None and entry.error_holes:
        context = {"entry": entry}
        return state.templates.TemplateResponse(
            request, "submit-confirm.html", context, status_code=status.HTTP_400_BAD_REQUEST
        )
    try:
        submit_card(state.engine, submission, now)
    except ValueError as error:
        return PlainTextResponse(str(error), status.HTTP_400_BAD_REQUEST)
    return RedirectResponse("/", status.HTTP_303_SEE_OTHER)


def create_app() -> FastAPI:
    """The app on the database file and the season its environment names (SPEC section 4)."""
    # No OpenAPI page: D2 rules out an API contract, and /docs would be open without a link.
    app = FastAPI(openapi_url=None)
    app.state.engine = open_database(Path(os.environ["LEAGUE_DATABASE"]))
    app.state.season_id = os.environ["LEAGUE_SEASON"]
    app.state.templates = Jinja2Templates(directory=_HERE / "templates")
    app.mount("/static", StaticFiles(directory=_HERE / "static"))
    app.add_api_route("/k/{link_token}", _link)
    app.add_api_route("/", _home)
    app.add_api_route("/standings", _standings)
    app.add_api_route("/rounds/{number}/bay", _bay)
    app.add_api_route("/rounds/{number}/cards/new", _new_card)
    app.add_api_route("/rounds/{number}/cards/check", _check_card, methods=["POST"])
    app.add_api_route("/rounds/{number}/cards", _submit_card, methods=["POST"])
    return app
