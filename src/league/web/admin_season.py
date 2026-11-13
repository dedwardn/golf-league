"""Season setup: the form that creates the season the deployment names, and that season read back
once it is stored, with its corrections (SPEC section 7).

Routes are added by name, as in app.py, because vulture reads a decorated route as unused.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse

from league.domain.access import seed_index_locked
from league.domain.facts import BaySetting, SeasonFacts, StandingsRule
from league.domain.index import PROPOSED_INDEX_RULE, SEED_SHARE, seed_index_tenths
from league.domain.results import tenths_text
from league.domain.teams import team_members
from league.services.setup import (
    change_bay_settings,
    correct_seed_index,
    create_season,
    link_tokens,
    stored_season,
)
from league.web.admin import admin_refused, is_admin, tenths_typed, whole_typed

_GOLFBOX = "A Golfbox handicap is a number with one decimal, such as 8.6."
_BEST_N = "Best rounds count is a whole number."
_TEAM = "A team has a name and two players."
_EMPTY = ("", "", "")

_Row = tuple[str, str, str]


@dataclass(frozen=True)
class _Typed:
    """Season setup's form as typed: each player with their Golfbox handicap, each team row as
    its name and two players, and each bay line as its menu, setting and value."""

    best_n: str
    players: tuple[str, ...]
    golfboxes: tuple[str, ...]
    teams: tuple[_Row, ...]
    lines: tuple[_Row, ...]


def _empty_form(roster: Sequence[str]) -> _Typed:
    """Every stored player without a Golfbox handicap, and as many team rows as the roster can
    form, so no row needs adding."""
    teams = (_EMPTY,) * (len(roster) // 2)
    return _Typed("", tuple(roster), ("",) * len(roster), teams, (_EMPTY,))


@dataclass(frozen=True)
class _Posted:
    """The form as typed, and whether Enter, Add a line or a line's Remove sent it, which only
    redraws it."""

    typed: _Typed
    redraw: bool
    add_line: bool
    remove_line: int | None


def _texts(values: Sequence[object]) -> tuple[str, ...]:
    return tuple(value if isinstance(value, str) else "" for value in values)


async def _season_form(request: Request) -> _Posted:
    """The form's repeated fields, each list in the order the screen drew it."""
    form = await request.form()

    def listed(name: str) -> tuple[str, ...]:
        return _texts(form.getlist(name))

    remove = form.get("remove")
    typed = _Typed(
        best_n=_texts([form.get("best_n")])[0],
        players=listed("player"),
        golfboxes=listed("golfbox"),
        teams=tuple(zip(listed("team"), listed("first"), listed("second"), strict=True)),
        lines=tuple(zip(listed("menu"), listed("setting"), listed("value"), strict=True)),
    )
    removed = None if not isinstance(remove, str) else int(remove)
    return _Posted(typed, form.get("redraw") is not None, form.get("add") is not None, removed)


def _seed(golfbox: str) -> int:
    """The seed index a Golfbox handicap as typed gives at the seed share (decision 1). Golfbox
    writes a plus handicap, index -1.2, as "+1.2", and never shows a "-", so one is no number."""
    text = golfbox.strip()
    number = text.removeprefix("+")
    if "+" in number or "-" in number:
        raise ValueError(_GOLFBOX)
    tenths = tenths_typed(number, _GOLFBOX)
    return seed_index_tenths(-tenths if text.startswith("+") else tenths)


def _seeds(typed: _Typed) -> dict[str, int]:
    """Each player with a Golfbox handicap and the seed index it gives. A player whose handicap
    is left empty is not in the season (the owner, at S17c1's plan)."""
    seeds: dict[str, int] = {}
    for player_id, golfbox in zip(typed.players, typed.golfboxes, strict=True):
        if golfbox.strip():
            seeds[player_id] = _seed(golfbox)
    return seeds


def _teams(rows: Sequence[_Row]) -> dict[str, str]:
    """Each player of a team row to its team. A player-to-team mapping cannot hold a player in
    two teams, so the form refuses one before SeasonFacts would read a team of one."""
    teams: dict[str, str] = {}
    for name, first, second in rows:
        if (name.strip(), first, second) == _EMPTY:
            continue
        if not name.strip() or not first or not second or first == second:
            raise ValueError(_TEAM)
        for player_id in (first, second):
            if player_id in teams:
                raise ValueError(f"{player_id} is in two teams.")
            teams[player_id] = name.strip()
    return teams


def _bay_settings(lines: Sequence[_Row]) -> tuple[BaySetting, ...]:
    """The lines as written, trimmed at the ends, with an empty one dropped (D18)."""
    trimmed = (tuple(text.strip() for text in line) for line in lines)
    return tuple(BaySetting(*line) for line in trimmed if line != _EMPTY)


def _season(typed: _Typed) -> SeasonFacts:
    """The team season the form holds, or ValueError in the form's words or the domain's."""
    best_n = typed.best_n.strip()
    return SeasonFacts(
        rounds=(),
        seed_index_tenths=_seeds(typed),
        provisional=frozenset(),
        index_rule=PROPOSED_INDEX_RULE,
        standings_rule=StandingsRule(best_n=whole_typed(best_n, _BEST_N) if best_n else None),
        teams=_teams(typed.teams),
        mode="team",
        bay_settings=_bay_settings(typed.lines),
    )


def _form_screen(request: Request, typed: _Typed, error: str | None) -> Response:
    context = {
        "season": request.app.state.season_id,
        "seed_share": SEED_SHARE,
        "typed": typed,
        "players": list(zip(typed.players, typed.golfboxes, strict=True)),
        "error": error,
    }
    code = status.HTTP_200_OK if error is None else status.HTTP_400_BAD_REQUEST
    return request.app.state.templates.TemplateResponse(
        request, "admin-season.html", context, status_code=code
    )


def _stored_form(facts: SeasonFacts) -> _Typed:
    """The read-back's fields as stored: no Golfbox handicap, since none is stored, and the bay
    lines as written."""
    lines = tuple((line.menu, line.setting, line.value) for line in facts.bay_settings)
    return _Typed("", (), (), (), lines)


def _read_back(
    request: Request, facts: SeasonFacts, typed: _Typed, error: str | None = None
) -> Response:
    """The stored season: its players in id order, each with their league index and a Golfbox
    handicap as typed while a correction may be typed, its teams in team id order, and its bay
    lines as typed."""
    golfboxes = dict(zip(typed.players, typed.golfboxes, strict=True))
    players = [
        (player_id, tenths_text(facts.seed_index_tenths[player_id]), golfboxes.get(player_id, ""))
        for player_id in sorted(facts.seed_index_tenths)
    ]
    teams = [(team, sorted(members)) for team, members in sorted(team_members(facts.teams).items())]
    fixed = seed_index_locked(facts)
    context = {
        "season": request.app.state.season_id,
        "seed_share": SEED_SHARE,
        "stored": facts,
        "best_n": facts.standings_rule.best_n or "Every round",
        "players": players,
        "teams": teams,
        "fixed": fixed,
        # Decision 1 settles the seed share a correction is read through for a team season only.
        "correctable": facts.mode == "team" and not fixed,
        "typed": typed,
        "error": error,
    }
    code = status.HTTP_200_OK if error is None else status.HTTP_400_BAD_REQUEST
    return request.app.state.templates.TemplateResponse(
        request, "admin-season.html", context, status_code=code
    )


def _season_page(request: Request) -> Response:
    """The stored season read back, or while nobody stored it, the form with every stored
    player."""
    if not is_admin(request):
        return admin_refused(request)
    engine = request.app.state.engine
    facts = stored_season(engine, request.app.state.season_id)
    if facts is not None:
        return _read_back(request, facts, _stored_form(facts))
    return _form_screen(request, _empty_form(list(link_tokens(engine))), None)


def _redrawn(posted: _Posted) -> _Typed | None:
    """The form as typed, with the line Add a line adds or a line's Remove takes away, or None
    when Save season sent it."""
    typed = posted.typed
    if posted.redraw:
        return typed
    if posted.add_line:
        return replace(typed, lines=(*typed.lines, _EMPTY))
    if posted.remove_line is not None:
        lines = typed.lines[: posted.remove_line] + typed.lines[posted.remove_line + 1 :]
        return replace(typed, lines=lines)
    return None


def _save_season(request: Request, posted: Annotated[_Posted, Depends(_season_form)]) -> Response:
    """Store the season through create_season and read it back, or show the form as typed with
    the refusal. Enter, Add a line and a line's Remove only redraw the form, and store nothing."""
    if not is_admin(request):
        return admin_refused(request)
    redrawn = _redrawn(posted)
    if redrawn is not None:
        return _form_screen(request, redrawn, None)
    try:
        create_season(request.app.state.engine, request.app.state.season_id, _season(posted.typed))
    except ValueError as error:
        return _form_screen(request, posted.typed, str(error))
    return _opened()


def _opened() -> Response:
    return RedirectResponse("/admin/season", status.HTTP_303_SEE_OTHER)


def _correct_index(request: Request, posted: Annotated[_Posted, Depends(_season_form)]) -> Response:
    """Correct one player's seed index from the Golfbox handicap typed in their row, read as Save
    season reads one (decision 1), or show the read-back with that row as typed and the refusal.
    While no season is stored, or the season is an individual one, which decision 1 does not seed,
    there is nothing to correct, so Season setup opens."""
    if not is_admin(request):
        return admin_refused(request)
    engine, season_id = request.app.state.engine, request.app.state.season_id
    facts = stored_season(engine, season_id)
    if facts is None or facts.mode != "team":
        return _opened()
    [(player_id, golfbox)] = zip(posted.typed.players, posted.typed.golfboxes, strict=True)
    try:
        correct_seed_index(engine, season_id, player_id, _seed(golfbox))
    except ValueError as error:
        typed = replace(_stored_form(facts), players=(player_id,), golfboxes=(golfbox,))
        return _read_back(request, facts, typed, str(error))
    return _opened()


def _change_bay_settings(
    request: Request, posted: Annotated[_Posted, Depends(_season_form)]
) -> Response:
    """Store the read-back's bay lines, at any time (D18), or redraw the read-back with them as
    typed when Enter, Add a line or a line's Remove sent them."""
    if not is_admin(request):
        return admin_refused(request)
    engine, season_id = request.app.state.engine, request.app.state.season_id
    facts = stored_season(engine, season_id)
    if facts is None:
        return _opened()
    redrawn = _redrawn(posted)
    if redrawn is not None:
        return _read_back(request, facts, redrawn)
    change_bay_settings(engine, season_id, _bay_settings(posted.typed.lines))
    return _opened()


def season_router() -> APIRouter:
    """Season setup's routes, each behind the admin cookie."""
    router = APIRouter()
    router.add_api_route("/admin/season", _season_page)
    router.add_api_route("/admin/season", _save_season, methods=["POST"])
    router.add_api_route("/admin/season/index", _correct_index, methods=["POST"])
    router.add_api_route("/admin/season/bay", _change_bay_settings, methods=["POST"])
    return router
