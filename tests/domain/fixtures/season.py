"""The golden season of S9b: six players, four rounds, every contest kind, hand-computed.

Tee A has its rating equal to par, slope 113 and each hole's stroke index equal to its number.
So a playing handicap is allowance times index rounded half up, it puts one stroke on holes 1
to that number, and a differential is ten times the gross over par. Every card is par except
the holes listed, each one over, so the R4 cap never bites.

How each number follows is worked out in docs/steps/S9b.md.
"""

from datetime import datetime, timedelta
from fractions import Fraction

from league.domain.configs import AllplayConfig, DuelConfig, FieldConfig, TeamBonusConfig
from league.domain.facts import (
    Card,
    IndexRule,
    ManualAward,
    Pairing,
    RoundFacts,
    SeasonFacts,
    Segment,
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


def _card(number: int, player_id: str, over: range, submitted_at: datetime) -> Card:
    """Par on every hole except those in over, each one over par."""
    scores = tuple(par + 1 if hole in over else par for hole, par in enumerate(PARS, start=1))
    return Card(f"r{number}-{player_id}", submitted_at, scores)


def _cards(number: int, over: dict[str, range]) -> dict[str, Card]:
    return {
        player_id: _card(number, player_id, holes, _played(number))
        for player_id, holes in over.items()
    }


NONE = range(0)

# Inserted fay first: round 1's field awards follow its entries, so a pipeline that kept the
# mapping's order rather than player id order would hand them out in a different order.
ROUND_1 = RoundFacts(
    number=1,
    tee=TEE_A,
    contests=(
        FieldConfig("field", "total", (Fraction(10), Fraction(6), Fraction(3), Fraction(1))),
    ),
    cards=_cards(
        1,
        {
            "fay": range(1, 19),
            "eve": range(3, 19),
            "dee": range(7, 19),
            "cam": range(13, 19),
            "bob": range(15, 19),
            "ann": NONE,
        },
    ),
    pairings={},
    manual=(ManualAward("eve", "longest-drive", Fraction(2)),),
    closed_at=_closed(1),
)

# dee's card comes in an hour after round 2 closes, and a week before her round-3 card: the
# index table depends on that order, because R6 replays a late card like any counted card.
DEE_LATE = _closed(2) + timedelta(hours=1)

ROUND_2 = RoundFacts(
    number=2,
    tee=TEE_A,
    contests=(
        DuelConfig(
            "duel",
            "stableford",
            points_win=Fraction(3),
            points_draw=Fraction(1),
            points_loss=Fraction(0),
            side="single",
            allowance=90,
        ),
    ),
    cards={
        **_cards(
            2,
            {
                "ann": NONE,
                "bob": range(15, 19),
                "cam": range(12, 19),
                "eve": range(4, 19),
                "fay": range(1, 19),
            },
        ),
        "dee": _card(2, "dee", range(8, 19), DEE_LATE),
    },
    pairings={
        "duel": (
            Pairing(("ann",), ("fay",)),
            Pairing(("bob",), ("eve",)),
            Pairing(("cam",), ("dee",)),
        )
    },
    manual=(),
    closed_at=_closed(2),
)

ROUND_3 = RoundFacts(
    number=3,
    tee=TEE_A,
    contests=(AllplayConfig("allplay", "total", Fraction(2)),),
    cards=_cards(
        3,
        {
            "ann": NONE,
            "bob": range(16, 19),
            "cam": range(12, 19),
            "dee": range(8, 19),
            "eve": range(3, 19),
            "fay": range(1, 19),
        },
    ),
    pairings={},
    manual=(),
    closed_at=_closed(3),
)

# Open, so its awards reach no table. dee's manual award carries the duel's own key: a
# teambonus that summed manual awards would give west 24 and the bonus.
ROUND_4 = RoundFacts(
    number=4,
    tee=TEE_A,
    contests=(
        DuelConfig(
            "bb",
            "total",
            points_win=Fraction(4),
            points_draw=Fraction(2),
            points_loss=Fraction(0),
            side="bestball",
            reference_rounds=(3,),
        ),
        TeamBonusConfig("bonus", source="bb", bonus=Fraction(3)),
        FieldConfig(
            "field",
            "total",
            (Fraction(12), Fraction(8), Fraction(6), Fraction(4), Fraction(2)),
            allowance=75,
        ),
    ),
    cards=_cards(
        4,
        {
            "ann": NONE,
            "bob": range(15, 19),
            "cam": range(12, 19),
            "dee": range(1, 13),
            "eve": range(3, 19),
            "fay": range(3, 19),
        },
    ),
    pairings={"bb": (Pairing(("ann", "bob"), ("dee", "eve")), Pairing(("cam", "fay")))},
    manual=(ManualAward("dee", "bb", Fraction(20)),),
    closed_at=None,
)

SEASON = SeasonFacts(
    rounds=(ROUND_1, ROUND_2, ROUND_3, ROUND_4),
    seed_index_tenths={"ann": 0, "bob": 40, "cam": 80, "dee": 120, "eve": 160, "fay": 180},
    provisional=frozenset(),
    index_rule=IndexRule(early_rate=70, early_cards=3, rate_down=50, rate_up=30),
    standings_rule=StandingsRule(best_n=2, segments=(Segment("first-half", 1, 2),)),
    teams={
        "ann": "east",
        "bob": "east",
        "cam": "east",
        "dee": "west",
        "eve": "west",
        "fay": "west",
    },
)
