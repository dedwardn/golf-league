"""Check the card for a row of a round's Cards card, as the admin corrects its counted card or
team card (R13).

Routes are added by name, as in app.py, because vulture reads a decorated route as unused.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from league.domain.entry import CardEntry
from league.services.run import correct_card, correction_view
from league.web.admin import admin_refused, is_admin
from league.web.admin_round import round_page
from league.web.shared import NO_STORE, form_scores, query_scores


def _screen(request: Request, entry: CardEntry, status_code: int) -> Response:
    """The admin's Check the card, which posts back to the path it was opened on."""
    context = {"entry": entry, "admin": True}
    return request.app.state.templates.TemplateResponse(
        request, "submit-confirm.html", context, status_code=status_code, headers=NO_STORE
    )


def _correction(request: Request, number: int, card_id: str) -> Response:
    """Correct: Check the card filled with the card's scores, and checked again with the scores
    in its query, as the player's is. A card no row of the round holds opens the round's page."""
    if not is_admin(request):
        return admin_refused(request)
    scores = query_scores(request)
    state = request.app.state
    entry = correction_view(state.engine, state.season_id, number, card_id, scores)
    if entry is None:
        return round_page(number)
    return _screen(request, entry, status.HTTP_200_OK)


def _correct(
    request: Request,
    number: int,
    card_id: str,
    scores: Annotated[tuple[int | None, ...], Depends(form_scores)],
) -> Response:
    """Replace the card's hole scores, keeping its submitted_at (R13), and open the round's page,
    or show the screen with its holes in error and store nothing. The screen is asked first, so a
    card it finds in the round with 18 scores in R13's bound leaves correct_card nothing to
    refuse."""
    if not is_admin(request):
        return admin_refused(request)
    state = request.app.state
    entry = correction_view(state.engine, state.season_id, number, card_id, scores)
    if entry is None:
        return round_page(number)
    if entry.error_holes:
        return _screen(request, entry, status.HTTP_400_BAD_REQUEST)
    typed = tuple(score for score in scores if score is not None)
    correct_card(state.engine, state.season_id, card_id, typed)
    return round_page(number)


def card_router() -> APIRouter:
    """Correct's routes, each behind the admin cookie."""
    router = APIRouter()
    router.add_api_route("/admin/rounds/{number}/cards/{card_id}/correct", _correction)
    router.add_api_route(
        "/admin/rounds/{number}/cards/{card_id}/correct", _correct, methods=["POST"]
    )
    return router
