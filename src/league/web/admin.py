"""The admin's link, the admin cookie and the admin's screens (D19).

Routes are added by name, as in app.py, because vulture reads a decorated route as unused.
"""

import secrets
from collections.abc import Iterable, Mapping
from decimal import Decimal, DecimalException
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse

from league.domain.results import tenths_text
from league.domain.tees import HOLES, Tee
from league.services.setup import (
    change_tee,
    create_player,
    create_tee,
    link_tokens,
    replace_link_token,
    stored_tee,
)
from league.web.shared import COOKIE_MAX_AGE, notice

_COOKIE = "admin_token"
_RATING = "The course rating is a number with one decimal, such as 71.8."
_WHOLE = "Slope, par and stroke index are whole numbers."
_NINES = (("Front nine", range(1, 10)), ("Back nine", range(10, HOLES + 1)))
_TEE_FIELDS = (
    "course",
    "tee",
    "rating",
    "slope",
    *(f"par{hole}" for hole in range(1, HOLES + 1)),
    *(f"si{hole}" for hole in range(1, HOLES + 1)),
)


def _is_admin_token(request: Request, token: str) -> bool:
    """Compared as bytes, since compare_digest refuses a str that is not ASCII."""
    return secrets.compare_digest(token.encode(), request.app.state.admin_token.encode())


def _admin(request: Request) -> bool:
    """Whether the admin cookie holds the deployment's secret, read on every request so a
    changed secret stops the old link at once."""
    token = request.cookies.get(_COOKIE)
    return token is not None and _is_admin_token(request, token)


def _refused(request: Request) -> Response:
    return notice(request, "Open your admin link.", status.HTTP_401_UNAUTHORIZED)


def _link(request: Request, admin_token: str) -> Response:
    """Open the admin's link. Whoever opens it is the admin (D19)."""
    if not _is_admin_token(request, admin_token):
        return _refused(request)
    response = RedirectResponse("/admin/tees", status.HTTP_303_SEE_OTHER)
    response.set_cookie(_COOKIE, admin_token, max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax")
    return response


def _typed(form: Mapping[str, object], fields: Iterable[str]) -> dict[str, str]:
    """Every field of a form as typed, empty where it is missing."""
    return {name: value if isinstance(value := form.get(name), str) else "" for name in fields}


async def _form(request: Request) -> dict[str, str]:
    return _typed(await request.form(), _TEE_FIELDS)


def _tenths(text: str) -> int:
    """A course rating read exactly, so "72" is 720 and "71.85" is refused. A comma is a decimal
    mark as a dot is, since a phone's number keyboard in Norway shows one."""
    try:
        tenths = Decimal(text.replace(",", ".")) * 10
    except DecimalException:
        raise ValueError(_RATING) from None
    if not tenths.is_finite() or tenths != tenths.to_integral_value():
        raise ValueError(_RATING)
    return int(tenths)


def _whole(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise ValueError(_WHOLE) from None


def _tee(typed: Mapping[str, str]) -> Tee:
    """The tee the form holds, or ValueError: the form's words for a field that is no number,
    the rating's first, and otherwise Tee's own (R13)."""
    rating = _tenths(typed["rating"])
    slope = _whole(typed["slope"])
    pars = tuple(_whole(typed[f"par{hole}"]) for hole in range(1, HOLES + 1))
    stroke_indexes = tuple(_whole(typed[f"si{hole}"]) for hole in range(1, HOLES + 1))
    return Tee(typed["course"].strip(), typed["tee"].strip(), pars, stroke_indexes, rating, slope)


def _tee_screen(
    request: Request,
    values: Mapping[str, str],
    changing: bool,
    stored: Tee | None,
    error: str | None,
) -> Response:
    """Add a course and tee, or a stored tee's page with its par, or either with a refused save's
    error in place of the note and no par, since the form as typed is no stored tee (SPEC
    section 7)."""
    context = {
        "season": request.app.state.season_id,
        "values": values,
        "changing": changing,
        "stored": stored,
        "error": error,
        "nines": _NINES,
    }
    code = status.HTTP_200_OK if error is None else status.HTTP_400_BAD_REQUEST
    return request.app.state.templates.TemplateResponse(
        request, "admin-tee.html", context, status_code=code
    )


def _save_tee(request: Request, typed: Mapping[str, str], changing: bool) -> Response:
    """Store the tee through create_tee, or change it through change_tee, and open its page, or
    show the form as typed with the refusal. Nothing is stored on a refusal."""
    try:
        tee = _tee(typed)
        if changing:
            change_tee(request.app.state.engine, tee)
        else:
            create_tee(request.app.state.engine, tee)
    except ValueError as error:
        return _tee_screen(request, typed, changing, None, str(error))
    # Course and tee go in the query, since a course may hold a slash.
    query = urlencode({"course": tee.course, "tee": tee.name})
    return RedirectResponse(f"/admin/tees/change?{query}", status.HTTP_303_SEE_OTHER)


def _new_tee(request: Request) -> Response:
    if not _admin(request):
        return _refused(request)
    return _tee_screen(request, _typed({}, _TEE_FIELDS), False, None, None)


def _add_tee(request: Request, typed: Annotated[dict[str, str], Depends(_form)]) -> Response:
    if not _admin(request):
        return _refused(request)
    return _save_tee(request, typed, changing=False)


def _shown(tee: Tee) -> dict[str, str]:
    """The tee form filled with a stored tee."""
    return {
        "course": tee.course,
        "tee": tee.name,
        "rating": tenths_text(tee.course_rating_tenths),
        "slope": str(tee.slope),
        **{f"par{hole}": str(par) for hole, par in enumerate(tee.pars, 1)},
        **{f"si{hole}": str(index) for hole, index in enumerate(tee.stroke_indexes, 1)},
    }


def _stored_tee_page(request: Request, course: str, tee: str) -> Response:
    """A stored tee's numbers, which change while R14 allows. Course and tee identify it, so
    they are read-only."""
    if not _admin(request):
        return _refused(request)
    found = stored_tee(request.app.state.engine, course, tee)
    if found is None:
        return notice(request, "No such tee.", status.HTTP_404_NOT_FOUND)
    return _tee_screen(request, _shown(found), True, found, None)


def _change_tee(request: Request, typed: Annotated[dict[str, str], Depends(_form)]) -> Response:
    if not _admin(request):
        return _refused(request)
    return _save_tee(request, typed, changing=True)


async def _player_form(request: Request) -> dict[str, str]:
    return _typed(await request.form(), ("name", "player"))


def _player_screen(
    request: Request, tokens: Mapping[str, str], name: str, shown: str | None, error: str | None
) -> Response:
    """Add a player, on a player's page with their link, or with a refused add's error and the
    name as typed (SPEC section 7). The link is the full URL the player opens, shown as text, since
    the admin's own browser would sign in as the player if it followed it."""
    context = {
        "season": request.app.state.season_id,
        "name": name,
        "player": shown,
        "link": None if shown is None else f"{request.base_url}k/{tokens[shown]}",
        "roster": list(tokens),
        "error": error,
    }
    code = status.HTTP_200_OK if error is None else status.HTTP_400_BAD_REQUEST
    return request.app.state.templates.TemplateResponse(
        request, "admin-player.html", context, status_code=code
    )


def _the_page_of(player_id: str) -> Response:
    # The player goes in the query, since a name may hold a slash.
    query = urlencode({"player": player_id})
    return RedirectResponse(f"/admin/players/link?{query}", status.HTTP_303_SEE_OTHER)


def _no_such_player(request: Request) -> Response:
    return notice(request, "No such player.", status.HTTP_404_NOT_FOUND)


def _players(request: Request) -> Response:
    if not _admin(request):
        return _refused(request)
    return _player_screen(request, link_tokens(request.app.state.engine), "", None, None)


def _add_player(
    request: Request, typed: Annotated[dict[str, str], Depends(_player_form)]
) -> Response:
    """Store the player through create_player and open their page, or show the name as typed with
    the refusal. The name is trimmed at the ends and keeps its case. The roster is read before the
    write, as for a write whose screen shows its own errors."""
    if not _admin(request):
        return _refused(request)
    engine = request.app.state.engine
    tokens = link_tokens(engine)
    player_id = typed["name"].strip()
    try:
        create_player(engine, player_id)
    except ValueError as error:
        return _player_screen(request, tokens, typed["name"], None, str(error))
    return _the_page_of(player_id)


def _player_page(request: Request, player: str) -> Response:
    if not _admin(request):
        return _refused(request)
    tokens = link_tokens(request.app.state.engine)
    if player not in tokens:
        return _no_such_player(request)
    return _player_screen(request, tokens, "", player, None)


def _new_link(
    request: Request, typed: Annotated[dict[str, str], Depends(_player_form)]
) -> Response:
    """Replace the player's link token, so the old link finds nobody at once."""
    if not _admin(request):
        return _refused(request)
    try:
        replace_link_token(request.app.state.engine, typed["player"])
    except ValueError:
        return _no_such_player(request)
    return _the_page_of(typed["player"])


def admin_router() -> APIRouter:
    """The admin's routes, each behind the admin cookie but the link that sets it."""
    router = APIRouter()
    router.add_api_route("/admin/k/{admin_token}", _link)
    router.add_api_route("/admin/tees", _new_tee)
    router.add_api_route("/admin/tees", _add_tee, methods=["POST"])
    router.add_api_route("/admin/tees/change", _stored_tee_page)
    router.add_api_route("/admin/tees/change", _change_tee, methods=["POST"])
    router.add_api_route("/admin/players", _players)
    router.add_api_route("/admin/players", _add_player, methods=["POST"])
    router.add_api_route("/admin/players/link", _player_page)
    router.add_api_route("/admin/players/link", _new_link, methods=["POST"])
    return router
