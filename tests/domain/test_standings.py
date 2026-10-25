from fractions import Fraction

from league.domain.facts import Segment, StandingsRule
from league.domain.results import Award, DuelReason, RoundAwards, StandingsRow
from league.domain.standings import standings


def contest_award(
    competitor_id: str, points: int, key: str = "duel", reason: DuelReason = "win"
) -> Award:
    """One award from a contest, the kind a round total sums."""
    return Award(competitor_id, key, Fraction(points), reason)


def manual_award(competitor_id: str, points: int) -> Award:
    """One award the admin gave by hand, which no best N drops."""
    return Award(competitor_id, "longest-drive", Fraction(points), "manual")


def a_round(number: int, *awards: Award) -> RoundAwards:
    """One closed round: R10's tables are built from those, which the caller selects."""
    return RoundAwards(number, awards)


def test_r10_season_points_are_the_sum_of_round_totals() -> None:
    rounds = [
        a_round(
            1,
            contest_award("ann", 3),
            contest_award("ann", 1, "field"),
            contest_award("bob", 1),
        ),
        a_round(2, contest_award("ann", 1), contest_award("bob", 3)),
    ]
    assert standings(rounds, ["ann", "bob"], StandingsRule()) == (
        StandingsRow(1, "ann", Fraction(5)),
        StandingsRow(2, "bob", Fraction(4)),
    )


def test_r10_best_n_sums_what_there_is_when_fewer_rounds_were_played() -> None:
    rounds = [a_round(1, contest_award("ann", 3)), a_round(2, contest_award("ann", 2))]
    assert standings(rounds, ["ann"], StandingsRule(best_n=3)) == (
        StandingsRow(1, "ann", Fraction(5)),
    )


def test_r10_a_round_without_an_award_is_not_a_zero_that_displaces_a_worse_one() -> None:
    # Ann's best 2 of a 3 and a -1 is 2: round 3, where she has no award, offers no 0 to pick.
    rounds = [
        a_round(1, contest_award("ann", 3)),
        a_round(2, contest_award("ann", -1, reason="loss")),
        a_round(3, contest_award("bob", 1)),
    ]
    assert standings(rounds, ["ann", "bob"], StandingsRule(best_n=2)) == (
        StandingsRow(1, "ann", Fraction(2)),
        StandingsRow(2, "bob", Fraction(1)),
    )


def test_r10_best_n_keeps_a_manual_award_from_the_round_it_drops() -> None:
    # Best 1 of Ann's 5 and 1 is 5, and round 2's manual 10 is added to it rather than
    # chosen instead of it. Bob never scored, so his row is his manual award alone.
    rounds = [
        a_round(1, contest_award("ann", 5)),
        a_round(2, contest_award("ann", 1), manual_award("ann", 10), manual_award("bob", 1)),
    ]
    assert standings(rounds, ["ann", "bob"], StandingsRule(best_n=1)) == (
        StandingsRow(1, "ann", Fraction(15)),
        StandingsRow(2, "bob", Fraction(1)),
    )


def test_r10_best_n_keeps_a_negative_manual_award_the_same_way() -> None:
    rounds = [
        a_round(1, contest_award("ann", 5)),
        a_round(2, contest_award("ann", 1), manual_award("ann", -2)),
    ]
    assert standings(rounds, ["ann"], StandingsRule(best_n=1)) == (
        StandingsRow(1, "ann", Fraction(3)),
    )


def test_r10_a_seeded_player_who_has_not_played_has_a_row_at_zero() -> None:
    rounds = [a_round(1, contest_award("ann", 2))]
    assert standings(rounds, ["ann", "bob"], StandingsRule()) == (
        StandingsRow(1, "ann", Fraction(2)),
        StandingsRow(2, "bob", Fraction(0)),
    )


def test_r10_a_segment_counts_its_own_rounds_with_its_own_best_n() -> None:
    rounds = [
        a_round(1, contest_award("ann", 3)),
        a_round(2, contest_award("ann", 2)),
        a_round(3, contest_award("ann", 4)),
    ]
    autumn = Segment("autumn", 1, 2, best_n=1)
    rule = StandingsRule(best_n=3, segments=(autumn,))
    assert standings(rounds, ["ann"], rule, autumn) == (StandingsRow(1, "ann", Fraction(3)),)
    assert standings(rounds, ["ann"], rule) == (StandingsRow(1, "ann", Fraction(9)),)


def test_r10_level_points_share_a_position_and_skip_the_next() -> None:
    # 5, 5, 3, 3, 1 is a leaderboard's 1, 1, 3, 3, 5: a shared first skips second.
    rounds = [
        a_round(
            1,
            contest_award("ann", 5),
            contest_award("bob", 5),
            contest_award("cal", 3),
            contest_award("dee", 3),
            contest_award("eve", 1),
        )
    ]
    assert standings(rounds, ["ann", "bob", "cal", "dee", "eve"], StandingsRule()) == (
        StandingsRow(1, "ann", Fraction(5)),
        StandingsRow(1, "bob", Fraction(5)),
        StandingsRow(3, "cal", Fraction(3)),
        StandingsRow(3, "dee", Fraction(3)),
        StandingsRow(5, "eve", Fraction(1)),
    )
