"""The golden team season of T3: four teams, five rounds, one per format, hand-computed.

Tee A has its rating equal to par, slope 113 and each hole's stroke index equal to its number.
So a course handicap is the index, a playing handicap at an allowance is that share of it rounded
half up, and it puts one stroke on holes 1 to that number. Every card is par except the holes
listed, each one over, unless a hole is given its own score.

How each number follows is worked out in docs/steps/T3.md.
"""

from datetime import datetime, timedelta
from fractions import Fraction

from league.domain.configs import (
    AllplayConfig,
    Basis,
    BestballFormat,
    CombinedFormat,
    FieldConfig,
    FoursomeFormat,
    GreensomeFormat,
    ScrambleFormat,
)
from league.domain.facts import (
    Card,
    IndexRule,
    ManualAward,
    RoundFacts,
    SeasonFacts,
    StandingsRule,
    Tee,
)

PARS = (4, 4, 3, 5) * 4 + (4, 4)
TEE_A = Tee(PARS, tuple(range(1, 19)), course_rating_tenths=720, slope=113)

# Each round is played on its own evening a week apart and closes at ten.
FIRST_EVENING = datetime(2026, 1, 5, 18, 0)


def _played(number: int) -> datetime:
    return FIRST_EVENING + timedelta(weeks=number - 1)


def _closed(number: int) -> datetime:
    return _played(number) + timedelta(hours=4)


def _card(
    card_id: str, submitted_at: datetime, over: range, scored: dict[int, int] | None = None
) -> Card:
    """Par on every hole except those in over, each one over, and the scored holes as given."""
    given = scored or {}
    scores = tuple(
        given.get(hole, par + 1 if hole in over else par) for hole, par in enumerate(PARS, start=1)
    )
    return Card(card_id, submitted_at, scores)


def _cards(number: int, over: dict[str, range]) -> dict[str, Card]:
    return {
        competitor_id: _card(f"r{number}-{competitor_id}", _played(number), holes)
        for competitor_id, holes in over.items()
    }


NONE = range(0)


def _allplay(basis: Basis) -> AllplayConfig:
    return AllplayConfig("allplay", basis, Fraction(3))


# hal has no card, so gold has no score: gus's 65 alone would have won as an R7 best ball side.
ROUND_1 = RoundFacts(
    number=1,
    tee=TEE_A,
    contests=(_allplay("total"),),
    cards=_cards(
        1,
        {
            "ann": range(15, 19),
            "bob": range(13, 19),
            "cam": range(15, 19),
            "dee": range(11, 19),
            "eve": range(14, 19),
            "fay": range(13, 19),
            "gus": NONE,
        },
    ),
    pairings={},
    manual=(),
    closed_at=_closed(1),
    format=BestballFormat(),
)

# R17: combined depends on the basis, so each contest builds its own team scores. hal's 9 on
# hole 18 costs gold three strokes on total and one point on stableford, which puts gold level
# with blue on points and last on total.
ROUND_2 = RoundFacts(
    number=2,
    tee=TEE_A,
    contests=(
        _allplay("stableford"),
        FieldConfig("field", "total", (Fraction(4), Fraction(3), Fraction(2), Fraction(1))),
    ),
    cards={
        **_cards(
            2,
            {
                "ann": range(15, 19),
                "bob": range(15, 19),
                "cam": range(10, 19),
                "dee": range(11, 19),
                "eve": range(11, 19),
                "fay": range(11, 19),
                "gus": range(9, 19),
            },
        ),
        "hal": _card("r2-hal", _played(2), range(8, 18), {18: 9}),
    },
    pairings={},
    manual=(),
    closed_at=_closed(2),
    format=CombinedFormat(),
)

# blue hands in no team card.
ROUND_3 = RoundFacts(
    number=3,
    tee=TEE_A,
    contests=(_allplay("total"),),
    cards={},
    pairings={},
    manual=(),
    closed_at=_closed(3),
    format=ScrambleFormat(),
    team_cards=_cards(3, {"red": NONE, "green": range(14, 19), "gold": range(15, 19)}),
)

# green's 64 comes in an hour after the close. Counted, it would win the round.
GREEN_LATE = _closed(4) + timedelta(hours=1)

ROUND_4 = RoundFacts(
    number=4,
    tee=TEE_A,
    contests=(_allplay("total"),),
    cards={},
    pairings={},
    manual=(),
    closed_at=_closed(4),
    format=GreensomeFormat(),
    team_cards={
        **_cards(4, {"red": NONE, "blue": range(13, 19), "gold": range(11, 19)}),
        "green": _card("r4-green", GREEN_LATE, NONE),
    },
)

# green has the lowest net total, 65, but gold the most points: R10's winner is not R15's.
# red's longest drive would make red's round total 7/2 and the round red's if it counted.
ROUND_5 = RoundFacts(
    number=5,
    tee=TEE_A,
    contests=(_allplay("stableford"),),
    cards={},
    pairings={},
    manual=(ManualAward("red", "longest-drive", Fraction(3)),),
    closed_at=_closed(5),
    format=FoursomeFormat(),
    team_cards={
        **_cards(5, {"red": NONE, "blue": range(15, 19), "green": range(17, 19)}),
        "gold": _card("r5-gold", _played(5), range(15, 18), {18: 8}),
    },
)

# Inserted red first: awards follow team id order, so a pipeline that kept the mapping's order
# would hand them out in a different one.
SEASON = SeasonFacts(
    rounds=(ROUND_1, ROUND_2, ROUND_3, ROUND_4, ROUND_5),
    seed_index_tenths={
        "ann": 20,
        "bob": 100,
        "cam": 40,
        "dee": 160,
        "eve": 60,
        "fay": 120,
        "gus": 80,
        "hal": 180,
    },
    provisional=frozenset(),
    index_rule=IndexRule(early_rate=70, early_cards=3, rate_down=50, rate_up=30),
    standings_rule=StandingsRule(best_n=4),
    teams={
        "ann": "red",
        "bob": "red",
        "cam": "blue",
        "dee": "blue",
        "eve": "green",
        "fay": "green",
        "gus": "gold",
        "hal": "gold",
    },
    mode="team",
)
