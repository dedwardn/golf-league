"""A team's playing handicap and its score for a round, per format (R16, R17).

One team in one round: nothing here reads a season. In an own-ball round each player plays
off their own playing handicap at the format's allowance (R1), and their net cards come in
here as net cards. A shared-ball team card is netted at the team's playing handicap (R3), and
that net card is the team's score.
"""

from fractions import Fraction

from league.domain.configs import (
    Basis,
    BestballFormat,
    CombinedFormat,
    FoursomeFormat,
    GreensomeFormat,
    ScrambleFormat,
)
from league.domain.facts import Tee
from league.domain.results import NetCard
from league.domain.rounding import round_half_up
from league.domain.strokes import course_handicap, stableford_points


def team_playing_handicap(
    index_tenths: tuple[int, int],
    tee: Tee,
    config: ScrambleFormat | GreensomeFormat | FoursomeFormat,
) -> int:
    """The playing handicap a shared-ball team's team card is netted at (R16).

    The two course handicaps stay exact and the team's handicap is rounded once.
    """
    lower, higher = sorted(course_handicap(index, tee) for index in index_tenths)
    if config.format == "foursome":
        return round_half_up(Fraction(config.allowance, 100) * (lower + higher))
    return round_half_up(Fraction(config.low, 100) * lower + Fraction(config.high, 100) * higher)


def own_ball_score(
    nets: tuple[NetCard | None, NetCard | None],
    config: BestballFormat | CombinedFormat,
    basis: Basis,
    tee: Tee,
) -> NetCard | None:
    """The two players' net cards made into their team's score (R17).

    None for a player is one without an on-time card, which the caller filters, and then the
    team has no score: unlike R7's best ball side, R17 needs both cards. Combined on
    stableford sets each hole to par + 2 less the summed points, so R8, which reads points
    off a net card, sees exactly the summed points and not the points of the summed net.
    """
    a, b = nets
    if a is None or b is None:
        return None
    if config.format == "bestball":
        return NetCard(tuple(map(min, a.scores, b.scores)))
    if basis != "stableford":
        return NetCard(tuple(x + y for x, y in zip(a.scores, b.scores, strict=True)))
    points = zip(stableford_points(a, tee), stableford_points(b, tee), strict=True)
    return NetCard(tuple(par + 2 - x - y for par, (x, y) in zip(tee.pars, points, strict=True)))
