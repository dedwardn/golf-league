"""One open round's Set up the bay screen (SPEC section 7): its format, its tee, and the season's
bay settings, split into the Game menu's lines and each other menu.

It calls access.py and holds no rule of its own. Trackman keeps no handicap (D18), so nothing
here reads an index.
"""

from league.domain.access import takes_team_card
from league.domain.facts import BaySetting, SeasonFacts
from league.domain.results import BayMenu, BayRound

_GAME = "Game"


def _menus(settings: tuple[BaySetting, ...]) -> tuple[BayMenu, ...]:
    """Each menu but Game, in the order first written, with every line the admin gave it.

    A dict keeps first-insertion order, so an interleaved menu gathers its lines in one place.
    """
    lines: dict[str, list[BaySetting]] = {}
    for line in settings:
        if line.menu != _GAME:
            lines.setdefault(line.menu, []).append(line)
    return tuple(BayMenu(name, tuple(held)) for name, held in lines.items())


def bay_round(facts: SeasonFacts, number: int) -> BayRound | None:
    """The bay screen of the season's open round of that number.

    None for a round that is not open or does not exist, and in an individual season, whose
    screen is S21's.
    """
    round_ = next((r for r in facts.rounds if r.number == number and r.closed_at is None), None)
    if facts.mode != "team" or round_ is None:
        return None
    # SeasonFacts refuses a round of a team season without a format (R15).
    config = round_.format
    assert config is not None
    return BayRound(
        number,
        config.format,
        takes_team_card(round_),
        round_.tee.course,
        round_.tee.name,
        tuple(line for line in facts.bay_settings if line.menu == _GAME),
        _menus(facts.bay_settings),
    )
