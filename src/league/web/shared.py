"""What the player's routes and the admin's both use: the notice for a refusal, and how long a
cookie they set lasts."""

from fastapi import Request, Response

# Long enough to outlive the browser closing; a browser caps a cookie at 400 days.
COOKIE_MAX_AGE = 400 * 24 * 60 * 60


def notice(request: Request, message: str, status_code: int) -> Response:
    """The one screen for every refusal a player meets, and for an admin page that cannot be
    opened, with a way back home (SPEC section 7)."""
    context = {"message": message}
    return request.app.state.templates.TemplateResponse(
        request, "notice.html", context, status_code=status_code
    )
