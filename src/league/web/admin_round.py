"""Rounds: the season's rounds, and a round's screen with its round card read as text.

Routes are added by name, as in app.py, because vulture reads a decorated route as unused.
"""

from fastapi import APIRouter, Request, Response, status

from league.services.setup import stored_rounds
from league.web.admin import admin_refused, is_admin
from league.web.shared import local_time, notice


def _rounds(request: Request) -> Response:
    """Every round of the season, drafts included, each opening its screen."""
    if not is_admin(request):
        return admin_refused(request)
    state = request.app.state
    context = {"season": state.season_id, "rounds": stored_rounds(state.engine, state.season_id)}
    return state.templates.TemplateResponse(request, "admin-rounds.html", context)


def _round(request: Request, number: int) -> Response:
    """One round's screen, its round card read as text. Once the round opens its setup is fixed
    (R14)."""
    if not is_admin(request):
        return admin_refused(request)
    state = request.app.state
    rounds = stored_rounds(state.engine, state.season_id)
    found = next((stored for stored in rounds if stored.round.number == number), None)
    if found is None:
        return notice(request, "No such round.", status.HTTP_404_NOT_FOUND)
    context = {
        "season": state.season_id,
        "stored": found,
        "local_time": local_time,
    }
    return state.templates.TemplateResponse(request, "admin-round.html", context)


def round_router() -> APIRouter:
    """The Rounds routes, each behind the admin cookie."""
    router = APIRouter()
    router.add_api_route("/admin/rounds", _rounds)
    router.add_api_route("/admin/rounds/{number}", _round)
    return router
