"""Rounds: the season's rounds with Add a round, and a round's screen, whose round card is a form
for a new round and a draft, and text once the round opens (R14), whose state card takes the
one action the round's state allows (R13), and whose Cards card voids a card after asking (R13).

Routes are added by name, as in app.py, because vulture reads a decorated route as unused.
"""

from contextlib import suppress
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse

from league.domain.access import may_reopen
from league.domain.configs import (
    TEAM_ROUND_CONTESTS,
    TEAM_ROUND_FORMATS,
    BestballFormat,
    ContestConfig,
)
from league.domain.facts import StoredRound
from league.domain.round_cards import card_row
from league.services.clock import utc_now
from league.services.run import (
    close_round,
    open_round,
    reopen_round,
    round_cards_view,
    void_card,
)
from league.services.setup import (
    RoundSetup,
    change_round,
    create_round,
    stored_rounds,
    stored_tees,
)
from league.web.admin import admin_refused, is_admin
from league.web.shared import local_input, local_time, notice, typed_fields, utc_typed

_NO_TEE = "Pick a course and tee."
_WINDOW = "Opens and Closes are a date and a time."
# A new round, and a draft without a format, check the first row.
_FIRST = BestballFormat().format


@dataclass(frozen=True)
class _Typed:
    """The round card's form as typed, the tee as its course and tee name."""

    number: str
    course: str
    tee_name: str
    opens: str
    closes: str
    format: str


async def _round_form(request: Request) -> _Typed:
    """The form's fields. The tee select's value is the tee's query string, as its page link on
    Courses, so any character in a name survives. Without a stored tee the select sends none."""
    typed = typed_fields(await request.form(), ("number", "tee", "opens", "closes", "format"))
    tee = parse_qs(typed["tee"])
    course, tee_name = (tee["course"][0], tee["tee"][0]) if tee else ("", "")
    return _Typed(
        typed["number"], course, tee_name, typed["opens"], typed["closes"], typed["format"]
    )


def _setup(
    request: Request, number: int, typed: _Typed, contests: tuple[ContestConfig, ...]
) -> RoundSetup:
    """The round the form holds, at its checked format's defaults, or ValueError in the form's
    words."""
    if not typed.course:
        raise ValueError(_NO_TEE)
    return RoundSetup(
        season_id=request.app.state.season_id,
        number=number,
        course=typed.course,
        tee_name=typed.tee_name,
        opens_at=utc_typed(typed.opens, _WINDOW),
        closes_at=utc_typed(typed.closes, _WINDOW),
        contests=contests,
        format=TEAM_ROUND_FORMATS[typed.format],
    )


def _shown(stored: StoredRound) -> _Typed:
    """A draft's form filled as stored."""
    round_ = stored.round
    return _Typed(
        str(round_.number),
        round_.tee.course,
        round_.tee.name,
        local_input(stored.opens_at),
        local_input(stored.closes_at),
        _FIRST if round_.format is None else round_.format.format,
    )


def _round_screen(
    request: Request,
    stored: StoredRound | None,
    typed: _Typed | None,
    error: str | None,
    voiding: str | None = None,
) -> Response:
    """A round's screen: a new round's form while nothing is stored, a draft's form, or the card
    as text once it opens, with a refused save's error in one warn card. A stored round has its
    state card, and an open or closed one its Cards card. A draft shown without its form is asking
    to open, and the row whose card id is `voiding` asks to void it, while an id in none of the
    rows asks nothing. The round card is hidden while either asks."""
    state = request.app.state
    cards = (
        ()
        if stored is None
        else round_cards_view(state.engine, state.season_id, stored.round.number)
    )
    context = {
        "season": state.season_id,
        "stored": stored,
        "typed": typed,
        "tees": () if typed is None else stored_tees(state.engine),
        "defaults": TEAM_ROUND_FORMATS,
        "error": error,
        "local_time": local_time,
        "reopens": stored is not None and may_reopen(stored.round),
        "cards": cards,
        "voiding": None if voiding is None else card_row(cards, voiding),
    }
    code = status.HTTP_200_OK if error is None else status.HTTP_400_BAD_REQUEST
    return state.templates.TemplateResponse(request, "admin-round.html", context, status_code=code)


def _found(request: Request, number: int) -> StoredRound | None:
    rounds = stored_rounds(request.app.state.engine, request.app.state.season_id)
    return next((stored for stored in rounds if stored.round.number == number), None)


def round_page(number: int) -> Response:
    """The round's page, which a post or page the round does not allow opens."""
    return RedirectResponse(f"/admin/rounds/{number}", status.HTTP_303_SEE_OTHER)


def _rounds(request: Request) -> Response:
    """Every round of the season, drafts included, each opening its screen, under Add a round."""
    if not is_admin(request):
        return admin_refused(request)
    state = request.app.state
    context = {"season": state.season_id, "rounds": stored_rounds(state.engine, state.season_id)}
    return state.templates.TemplateResponse(request, "admin-rounds.html", context)


def _new_round(request: Request) -> Response:
    """A new round's form, numbered one more than the season's highest round, drafts included,
    fixed here and carried in the form, so a second tap of Save round is refused."""
    if not is_admin(request):
        return admin_refused(request)
    rounds = stored_rounds(request.app.state.engine, request.app.state.season_id)
    number = max((stored.round.number for stored in rounds), default=0) + 1
    return _round_screen(request, None, _Typed(str(number), "", "", "", "", _FIRST), None)


def _add_round(request: Request, typed: Annotated[_Typed, Depends(_round_form)]) -> Response:
    """Store the round as a draft with decision 6's contests and open its screen, or show the
    form as typed with the refusal. Nothing is stored on a refusal."""
    if not is_admin(request):
        return admin_refused(request)
    try:
        setup = _setup(request, int(typed.number), typed, TEAM_ROUND_CONTESTS)
        create_round(request.app.state.engine, setup)
    except ValueError as error:
        return _round_screen(request, None, typed, str(error))
    return round_page(setup.number)


def _round(request: Request, number: int) -> Response:
    """One round's screen: its round card a form while it is a draft, and text once it opens."""
    if not is_admin(request):
        return admin_refused(request)
    found = _found(request, number)
    if found is None:
        return notice(request, "No such round.", status.HTTP_404_NOT_FOUND)
    return _round_screen(request, found, _shown(found) if found.state == "draft" else None, None)


def _change(
    request: Request, number: int, typed: Annotated[_Typed, Depends(_round_form)]
) -> Response:
    """Change a draft through change_round, keeping its contests, and open its screen, or show the
    form as typed with the refusal. A round that is no draft, or that the season does not have,
    opens its page and stores nothing, since its setup is fixed (R14)."""
    if not is_admin(request):
        return admin_refused(request)
    found = _found(request, number)
    if found is None or found.state != "draft":
        return round_page(number)
    try:
        change_round(request.app.state.engine, _setup(request, number, typed, found.round.contests))
    except ValueError as error:
        return _round_screen(request, found, typed, str(error))
    return round_page(number)


def _ask_to_open(request: Request, number: int) -> Response:
    """Ask once before a draft opens, since opening cannot be undone, and store nothing. A round
    that is no draft, or that the season does not have, opens its page."""
    if not is_admin(request):
        return admin_refused(request)
    found = _found(request, number)
    if found is None or found.state != "draft":
        return round_page(number)
    return _round_screen(request, found, None, None)


def _ask_to_void(request: Request, number: int, card_id: str) -> Response:
    """Ask once before a card is voided, since a void cannot be undone, and store nothing. A
    card id in none of the round's rows makes no row ask. A draft, which has no cards, or a
    round the season does not have opens its page."""
    if not is_admin(request):
        return admin_refused(request)
    found = _found(request, number)
    if found is None or found.state == "draft":
        return round_page(number)
    return _round_screen(request, found, None, None, card_id)


# Each action opens the round's page, whose state card shows what the round's state now allows.
# A post the state does not allow, such as a second tap, is refused by its use case and stores
# nothing, so the page as it now stands is the answer and no refusal is worded.


def _open(request: Request, number: int) -> Response:
    if not is_admin(request):
        return admin_refused(request)
    with suppress(ValueError):
        open_round(request.app.state.engine, request.app.state.season_id, number)
    return round_page(number)


def _close(request: Request, number: int) -> Response:
    if not is_admin(request):
        return admin_refused(request)
    with suppress(ValueError):
        close_round(request.app.state.engine, request.app.state.season_id, number, utc_now())
    return round_page(number)


def _reopen(request: Request, number: int) -> Response:
    if not is_admin(request):
        return admin_refused(request)
    with suppress(ValueError):
        reopen_round(request.app.state.engine, request.app.state.season_id, number)
    return round_page(number)


def _void(request: Request, number: int, card_id: str) -> Response:
    if not is_admin(request):
        return admin_refused(request)
    with suppress(ValueError):
        void_card(request.app.state.engine, request.app.state.season_id, card_id)
    return round_page(number)


def round_router() -> APIRouter:
    """The Rounds routes, each behind the admin cookie. A new round's are added first, since
    `/admin/rounds/{number}` would otherwise take them."""
    router = APIRouter()
    router.add_api_route("/admin/rounds", _rounds)
    router.add_api_route("/admin/rounds/new", _new_round)
    router.add_api_route("/admin/rounds/new", _add_round, methods=["POST"])
    router.add_api_route("/admin/rounds/{number}", _round)
    router.add_api_route("/admin/rounds/{number}", _change, methods=["POST"])
    router.add_api_route("/admin/rounds/{number}/open", _ask_to_open)
    router.add_api_route("/admin/rounds/{number}/open", _open, methods=["POST"])
    router.add_api_route("/admin/rounds/{number}/close", _close, methods=["POST"])
    router.add_api_route("/admin/rounds/{number}/reopen", _reopen, methods=["POST"])
    router.add_api_route("/admin/rounds/{number}/cards/{card_id}/void", _ask_to_void)
    router.add_api_route("/admin/rounds/{number}/cards/{card_id}/void", _void, methods=["POST"])
    return router
