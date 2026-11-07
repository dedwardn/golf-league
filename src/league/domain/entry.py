"""One round's card entry for one viewer (SPEC section 7): its tee, the scores typed, and the
holes whose score Card would refuse.

It calls access.py, reads R13's bound from facts.py and holds no rule of its own. Card still
checks the card that is handed in, so the screen only says which holes it would refuse.
"""

from dataclasses import dataclass
from datetime import datetime

from league.domain.access import accepts_card, holds_card
from league.domain.facts import MAX_SCORE, MIN_SCORE, SeasonFacts

_OUT = 9


@dataclass(frozen=True)
class CardEntry:
    """Check the card for one viewer: the round's number, its tee, and the scores typed so far.

    `scores` is empty until the player first checks the card. A score is None where the hole
    was left empty or holds no whole number.
    """

    number: int
    course: str
    tee_name: str
    pars: tuple[int, ...]
    par_total: int
    scores: tuple[int | None, ...]

    @property
    def out_total(self) -> int:
        return sum(score for score in self.scores[:_OUT] if score is not None)

    @property
    def in_total(self) -> int:
        return sum(score for score in self.scores[_OUT:] if score is not None)

    @property
    def total(self) -> int:
        return sum(score for score in self.scores if score is not None)

    @property
    def error_holes(self) -> tuple[int, ...]:
        """The holes, in hole order, whose score is missing or outside R13's bound."""
        return tuple(
            hole
            for hole, score in enumerate(self.scores, start=1)
            if score is None or score < MIN_SCORE or score > MAX_SCORE
        )

    @property
    def ready(self) -> bool:
        """Typed with no hole in error, so its totals show and it may be submitted."""
        return bool(self.scores) and not self.error_holes

    @property
    def error_text(self) -> str:
        """The warn line, as "Looks like an error on holes 5, 9 and 12."."""
        *rest, last = (str(hole) for hole in self.error_holes)
        holes = f"holes {', '.join(rest)} and {last}" if rest else f"hole {last}"
        return f"Looks like an error on {holes}."


@dataclass(frozen=True)
class CardIn:
    """The viewer's card, or in a shared-ball round their team's team card, is already in.

    The screen then opens the round page, which shows the round's result (R12).
    """


def card_entry(
    facts: SeasonFacts, number: int, viewer_id: str, now: datetime, scores: tuple[int | None, ...]
) -> CardEntry | CardIn | None:
    """The entry for the season's round of that number, while it takes the viewer's card now.

    CardIn once the card the viewer hands in is in, open round or closed (R15). None for a round
    that does not take it otherwise (R13) or does not exist, and in an individual season, whose
    screens are S21's.
    """
    round_ = next((round_ for round_ in facts.rounds if round_.number == number), None)
    if facts.mode != "team" or round_ is None:
        return None
    if holds_card(viewer_id, round_, facts.teams):
        return CardIn()
    if not accepts_card(viewer_id, round_, facts, now):
        return None
    tee = round_.tee
    return CardEntry(number, tee.course, tee.name, tee.pars, tee.par_total, scores)
