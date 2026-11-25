"""What the player's routes and the admin's both use: the notice for a refusal, how long a
cookie they set lasts, a stored time as local time, which the admin also types, and Check the
card's 18 scores as typed, with the header that keeps its screens out of the browser's store,
and what the admin's route modules share: a form's fields as typed."""

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import Request, Response

from league.domain.tees import HOLES

# Long enough to outlive the browser closing; a browser caps a cookie at 400 days.
COOKIE_MAX_AGE = 400 * 24 * 60 * 60
_ZONE = ZoneInfo("Europe/Oslo")
# A date and time input's value, written and read in one format, so a date alone is refused.
_INPUT = "%Y-%m-%dT%H:%M"
# Check the card is asked for again after Back, so the server answers what is stored now.
NO_STORE: Mapping[str, str] = {"Cache-Control": "no-store"}


def local_time(moment: datetime) -> str:
    """A stored naive UTC time on the league's clock, with its date, as a round runs for weeks."""
    local = moment.replace(tzinfo=UTC).astimezone(_ZONE)
    return f"{local:%a} {local.day} {local:%b}, {local:%H:%M}"


def local_input(moment: datetime) -> str:
    """A stored naive UTC time as a date and time input's value, in local time."""
    return moment.replace(tzinfo=UTC).astimezone(_ZONE).strftime(_INPUT)


def utc_typed(text: str, message: str) -> datetime:
    """A date and time input's value, typed in local time, as naive UTC, or ValueError with the
    message. The zone, not a fixed offset, so a time in summer is read in summer time."""
    try:
        typed = datetime.strptime(text, _INPUT)
    except ValueError:
        raise ValueError(message) from None
    return typed.replace(tzinfo=_ZONE).astimezone(UTC).replace(tzinfo=None)


def typed_fields(form: Mapping[str, object], fields: Iterable[str]) -> dict[str, str]:
    """Every field of a form as typed, empty where it is missing."""
    return {name: value if isinstance(value := form.get(name), str) else "" for name in fields}


def notice(request: Request, message: str, status_code: int) -> Response:
    """The one screen for every refusal a player meets, and for an admin page that cannot be
    opened, with a way back home (SPEC section 7)."""
    context = {"message": message}
    return request.app.state.templates.TemplateResponse(
        request, "notice.html", context, status_code=status_code
    )


def _hole_scores(values: Mapping[str, object]) -> tuple[int | None, ...]:
    """The scores h1 to h18 in hole order, None where a hole is missing or no whole number.

    Their bound is Card's (R13): the screen outlines a hole it would refuse, and Card refuses it.
    """
    scores: list[int | None] = []
    for hole in range(1, HOLES + 1):
        value = values.get(f"h{hole}")
        try:
            scores.append(int(value) if isinstance(value, str) else None)
        except ValueError:
            scores.append(None)
    return tuple(scores)


def query_scores(request: Request) -> tuple[int | None, ...]:
    """Check the card's scores in the query, or none before the first check."""
    query = request.query_params
    return _hole_scores(query) if query else ()


async def form_scores(request: Request) -> tuple[int | None, ...]:
    return _hole_scores(await request.form())
