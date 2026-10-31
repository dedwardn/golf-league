"""The app: a personal link that sets the cookie, and one route per screen.

Everything a request needs sits on `app.state`, since nothing here is module-level state. Routes
are added by name because vulture reads a decorated route as unused.
"""

import os
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from league.services.clock import utc_now
from league.services.play import player_for_link_token, season_view
from league.services.runtime import open_database

_HERE = Path(__file__).parent
_COOKIE = "link_token"
# Long enough to outlive the phone's browser closing; a browser caps a cookie at 400 days.
_COOKIE_MAX_AGE = 400 * 24 * 60 * 60


def _refused() -> Response:
    return PlainTextResponse("Open your personal link.", status.HTTP_401_UNAUTHORIZED)


def _link(request: Request, link_token: str) -> Response:
    """Open a player's personal link. Whoever opens it is that player (D7)."""
    if player_for_link_token(request.app.state.engine, link_token) is None:
        return _refused()
    response = RedirectResponse("/standings", status.HTTP_303_SEE_OTHER)
    response.set_cookie(_COOKIE, link_token, max_age=_COOKIE_MAX_AGE, httponly=True, samesite="lax")
    return response


def _viewer(request: Request) -> str | None:
    """The player the cookie names, read on every request so a replaced link stops at once."""
    link_token = request.cookies.get(_COOKIE)
    if link_token is None:
        return None
    return player_for_link_token(request.app.state.engine, link_token)


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


def create_app() -> FastAPI:
    """The app on the database file and the season its environment names (SPEC section 4)."""
    # No OpenAPI page: D2 rules out an API contract, and /docs would be open without a link.
    app = FastAPI(openapi_url=None)
    app.state.engine = open_database(Path(os.environ["LEAGUE_DATABASE"]))
    app.state.season_id = os.environ["LEAGUE_SEASON"]
    app.state.templates = Jinja2Templates(directory=_HERE / "templates")
    app.mount("/static", StaticFiles(directory=_HERE / "static"))
    app.add_api_route("/k/{link_token}", _link)
    app.add_api_route("/standings", _standings)
    return app
