"""What the player's routes and the admin's both use: the notice for a refusal, how long a
cookie they set lasts, and a stored time as local time."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import Request, Response

# Long enough to outlive the browser closing; a browser caps a cookie at 400 days.
COOKIE_MAX_AGE = 400 * 24 * 60 * 60
_ZONE = ZoneInfo("Europe/Oslo")


def local_time(moment: datetime) -> str:
    """A stored naive UTC time on the league's clock, with its date, as a round runs for weeks."""
    local = moment.replace(tzinfo=UTC).astimezone(_ZONE)
    return f"{local:%a} {local.day} {local:%b}, {local:%H:%M}"


def notice(request: Request, message: str, status_code: int) -> Response:
    """The one screen for every refusal a player meets, and for an admin page that cannot be
    opened, with a way back home (SPEC section 7)."""
    context = {"message": message}
    return request.app.state.templates.TemplateResponse(
        request, "notice.html", context, status_code=status_code
    )
