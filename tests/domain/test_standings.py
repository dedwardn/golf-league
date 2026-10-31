from fractions import Fraction

import pytest
from conftest import dropped, kept, lines

from league.domain.facts import Segment, StandingsRule
from league.domain.results import (
    Award,
    DuelReason,
    Gap,
    RoundAwards,
    StandingsRow,
    points_text,
)
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
    return RoundAwards(number, awards, ())


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
    assert lines(standings(rounds, ["ann", "bob"], StandingsRule())) == [
        (1, "ann", Fraction(5)),
        (2, "bob", Fraction(4)),
    ]


def test_r10_best_n_sums_what_there_is_when_fewer_rounds_were_played() -> None:
    rounds = [a_round(1, contest_award("ann", 3)), a_round(2, contest_award("ann", 2))]
    assert lines(standings(rounds, ["ann"], StandingsRule(best_n=3))) == [
        (1, "ann", Fraction(5)),
    ]


def test_r10_a_round_without_an_award_is_not_a_zero_that_displaces_a_worse_one() -> None:
    # Ann's best 2 of a 3 and a -1 is 2: round 3, where she has no award, offers no 0 to pick.
    rounds = [
        a_round(1, contest_award("ann", 3)),
        a_round(2, contest_award("ann", -1, reason="loss")),
        a_round(3, contest_award("bob", 1)),
    ]
    assert lines(standings(rounds, ["ann", "bob"], StandingsRule(best_n=2))) == [
        (1, "ann", Fraction(2)),
        (2, "bob", Fraction(1)),
    ]


def test_r10_best_n_keeps_a_manual_award_from_the_round_it_drops() -> None:
    # Best 1 of Ann's 5 and 1 is 5, and round 2's manual 10 is added to it rather than
    # chosen instead of it. Bob never scored, so his row is his manual award alone.
    rounds = [
        a_round(1, contest_award("ann", 5)),
        a_round(2, contest_award("ann", 1), manual_award("ann", 10), manual_award("bob", 1)),
    ]
    assert lines(standings(rounds, ["ann", "bob"], StandingsRule(best_n=1))) == [
        (1, "ann", Fraction(15)),
        (2, "bob", Fraction(1)),
    ]


def test_r10_best_n_keeps_a_negative_manual_award_the_same_way() -> None:
    rounds = [
        a_round(1, contest_award("ann", 5)),
        a_round(2, contest_award("ann", 1), manual_award("ann", -2)),
    ]
    assert lines(standings(rounds, ["ann"], StandingsRule(best_n=1))) == [
        (1, "ann", Fraction(3)),
    ]


def test_r10_a_seeded_player_who_has_not_played_has_a_row_at_zero() -> None:
    rounds = [a_round(1, contest_award("ann", 2))]
    assert lines(standings(rounds, ["ann", "bob"], StandingsRule())) == [
        (1, "ann", Fraction(2)),
        (2, "bob", Fraction(0)),
    ]


def test_r10_a_segment_counts_its_own_rounds_with_its_own_best_n() -> None:
    rounds = [
        a_round(1, contest_award("ann", 3)),
        a_round(2, contest_award("ann", 2)),
        a_round(3, contest_award("ann", 4)),
    ]
    autumn = Segment("autumn", 1, 2, best_n=1)
    rule = StandingsRule(best_n=3, segments=(autumn,))
    assert lines(standings(rounds, ["ann"], rule, autumn)) == [(1, "ann", Fraction(3))]
    assert lines(standings(rounds, ["ann"], rule)) == [(1, "ann", Fraction(9))]


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
    assert lines(standings(rounds, ["ann", "bob", "cal", "dee", "eve"], StandingsRule())) == [
        (1, "ann", Fraction(5)),
        (1, "bob", Fraction(5)),
        (3, "cal", Fraction(3)),
        (3, "dee", Fraction(3)),
        (5, "eve", Fraction(1)),
    ]


def test_r10_positions_read_exact_points_where_the_shown_points_are_equal() -> None:
    # Section 7: 4.64 and 4.61 both show 4.6, and bob is seeded second.
    rounds = [
        a_round(
            1,
            Award("ann", "duel", Fraction(461, 100), "win"),
            Award("bob", "duel", Fraction(464, 100), "win"),
        )
    ]
    rows = standings(rounds, ["ann", "bob"], StandingsRule())
    assert [(row.position, row.competitor_id, row.points_text) for row in rows] == [
        (1, "bob", "4.6"),
        (2, "ann", "4.6"),
    ]


@pytest.mark.parametrize(
    ("points", "text"),
    [
        (Fraction(37, 4), "9.3"),  # float rounding gives 9.2
        (Fraction(19, 4), "4.8"),
        (Fraction(23, 5), "4.6"),
        (Fraction(13, 5), "2.6"),
        (Fraction(8), "8.0"),
        (Fraction(0), "0.0"),
        (Fraction(-1, 4), "-0.2"),
        (Fraction(-5, 4), "-1.2"),
        (Fraction(-1, 20), "0.0"),  # the sign follows the rounded tenths, not the points
    ],
)
def test_points_text_rounds_half_up_to_one_decimal(points: Fraction, text: str) -> None:
    assert points_text(points) == text


def test_r10_best_n_marks_the_round_totals_it_drops() -> None:
    rounds = [
        a_round(1, contest_award("ann", 3)),
        a_round(2, contest_award("ann", 1)),
        a_round(3, contest_award("ann", 2)),
    ]
    (row,) = standings(rounds, ["ann"], StandingsRule(best_n=2))
    assert row.round_totals == (kept(3), dropped(1), kept(2))
    assert row.points == 5


def test_r10_a_table_without_best_n_drops_nothing() -> None:
    rounds = [a_round(1, contest_award("ann", 3)), a_round(2, contest_award("ann", 1))]
    (row,) = standings(rounds, ["ann"], StandingsRule())
    assert row.round_totals == (kept(3), kept(1))


def test_r10_a_segment_drops_by_its_own_best_n_over_its_own_rounds() -> None:
    rounds = [
        a_round(1, contest_award("ann", 3)),
        a_round(2, contest_award("ann", 2)),
        a_round(3, contest_award("ann", 4)),
    ]
    autumn = Segment("autumn", 1, 2, best_n=1)
    (row,) = standings(rounds, ["ann"], StandingsRule(best_n=3, segments=(autumn,)), autumn)
    assert row.round_totals == (kept(3), dropped(2))


def test_r10_a_round_not_scored_in_has_no_round_total() -> None:
    rounds = [a_round(1, contest_award("ann", 3)), a_round(2, contest_award("bob", 1))]
    row = standings(rounds, ["ann", "bob"], StandingsRule())[0]
    assert row.round_totals == (kept(3),)


def test_r10_a_round_with_only_a_manual_award_has_no_round_total_and_still_counts() -> None:
    rounds = [a_round(1, contest_award("ann", 3)), a_round(2, manual_award("ann", 2))]
    (row,) = standings(rounds, ["ann"], StandingsRule())
    assert row.round_totals == (kept(3),)
    assert row.points == 5


def test_r10_of_equal_round_totals_the_later_is_dropped() -> None:
    # R10 does not say which: the chips read the same, and a table needs one answer.
    rounds = [
        a_round(1, contest_award("ann", 2)),
        a_round(2, contest_award("ann", 3)),
        a_round(3, contest_award("ann", 2)),
    ]
    (row,) = standings(rounds, ["ann"], StandingsRule(best_n=2))
    assert row.round_totals == (kept(2), kept(3), dropped(2))


def test_r10_a_row_counts_the_rounds_it_holds_a_card_in() -> None:
    # bob's card in round 2 earned nothing, and it still counts.
    rounds = [
        RoundAwards(1, (contest_award("ann", 3),), ("ann", "bob")),
        RoundAwards(2, (contest_award("ann", 1),), ("ann", "bob")),
        RoundAwards(3, (contest_award("ann", 1),), ("ann",)),
    ]
    ann, bob = standings(rounds, ["ann", "bob"], StandingsRule())
    assert (ann.counted_cards, bob.counted_cards) == (3, 2)


def test_r10_a_segment_counts_cards_in_its_own_rounds() -> None:
    rounds = [RoundAwards(number, (), ("ann",)) for number in (1, 2, 3)]
    autumn = Segment("autumn", 2, 3)
    (row,) = standings(rounds, ["ann"], StandingsRule(segments=(autumn,)), autumn)
    assert row.counted_cards == 2


def table_on(points: dict[str, int]) -> tuple[StandingsRow, ...]:
    """The table of one round in which each competitor scored those points."""
    awards = [contest_award(competitor_id, value) for competitor_id, value in points.items()]
    return standings([a_round(1, *awards)], list(points), StandingsRule())


def test_section_7_the_gap_is_to_the_place_above() -> None:
    rows = table_on({"ann": 5, "bob": 3, "cal": 2})
    assert [row.gap for row in rows] == [None, Gap(Fraction(2), 1), Gap(Fraction(1), 2)]


def test_section_7_the_place_above_a_row_is_past_a_shared_position() -> None:
    rows = table_on({"ann": 6, "bob": 5, "cal": 5, "dee": 5, "eve": 1})
    assert [row.gap for row in rows] == [
        None,
        Gap(Fraction(1), 1),
        Gap(Fraction(1), 1),
        Gap(Fraction(1), 1),
        Gap(Fraction(4), 2),
    ]


def test_section_7_a_shared_first_has_no_gap() -> None:
    assert [row.gap for row in table_on({"ann": 5, "bob": 5})] == [None, None]


def test_section_7_a_gap_is_exact_before_it_is_shown() -> None:
    # 16.0 less 9.3 as shown is 6.7, and the exact 27/4 shows as 6.8 (T3's gold).
    assert Gap(Fraction(27, 4), 1).text == "6.8 to 1st"


@pytest.mark.parametrize(
    ("position", "text"),
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (10, "10th"),
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
        (30, "30th"),
    ],
)
def test_section_7_a_gap_names_the_place_above_as_an_ordinal(position: int, text: str) -> None:
    assert Gap(Fraction(1), position).text == f"1.0 to {text}"


def test_section_7_a_round_total_shows_to_one_decimal() -> None:
    assert kept(Fraction(9, 4)).points_text == "2.3"
