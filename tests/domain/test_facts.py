from dataclasses import replace
from fractions import Fraction

import pytest
from conftest import PARS, STROKE_INDEXES, TEE, a_card, a_duel, a_field, an_index_rule

from league.domain.configs import BestballFormat, ContestConfig, TeamBonusConfig
from league.domain.facts import (
    ManualAward,
    Pairing,
    RoundFacts,
    SeasonFacts,
    Segment,
    StandingsRule,
    Tee,
)


def a_tee(
    pars: tuple[int, ...] = PARS,
    stroke_indexes: tuple[int, ...] = STROKE_INDEXES,
) -> Tee:
    return Tee(pars, stroke_indexes, course_rating_tenths=732, slope=131)


def test_r13_a_well_formed_tee_and_card_are_accepted() -> None:
    tee = a_tee()
    assert tee.par_total == 72
    assert a_card((4,) * 18).scores == (4,) * 18


def test_r13_tee_needs_eighteen_pars() -> None:
    with pytest.raises(ValueError, match="18 pars"):
        a_tee(pars=PARS[:17])


def test_r13_tee_pars_are_three_to_six() -> None:
    with pytest.raises(ValueError, match="3 to 6"):
        a_tee(pars=(7, *PARS[1:]))


def test_r13_tee_needs_eighteen_stroke_indexes() -> None:
    with pytest.raises(ValueError, match="18 stroke indexes"):
        a_tee(stroke_indexes=STROKE_INDEXES[:17])


def test_r13_tee_stroke_indexes_are_one_to_eighteen_once_each() -> None:
    with pytest.raises(ValueError, match="1 to 18"):
        a_tee(stroke_indexes=(1, *STROKE_INDEXES[2:], 1))


def test_r13_card_needs_eighteen_scores() -> None:
    with pytest.raises(ValueError, match="18 scores"):
        a_card((4,) * 17)


def test_r13_card_scores_are_one_or_more() -> None:
    with pytest.raises(ValueError, match="1 or more"):
        a_card((0,) + (4,) * 17)


def test_r5_index_rule_rates_of_zero_and_one_hundred_are_legal() -> None:
    # A rate of 0 freezes the index, 100 makes it follow the differential exactly.
    rule = an_index_rule(early_rate=0, early_cards=0, rate_down=100, rate_up=100)
    assert rule.rate_down == 100


def test_r5_index_rule_rates_are_not_negative() -> None:
    with pytest.raises(ValueError, match="0 to 100"):
        an_index_rule(rate_down=-1)


def test_r5_index_rule_rates_are_not_above_one_hundred() -> None:
    with pytest.raises(ValueError, match="0 to 100"):
        an_index_rule(early_rate=101)


def test_r5_index_rule_early_cards_is_zero_or_more() -> None:
    with pytest.raises(ValueError, match="0 or more"):
        an_index_rule(early_cards=-1)


def test_r9_a_pairing_has_at_least_one_side() -> None:
    with pytest.raises(ValueError, match="at least one side"):
        Pairing(())


def test_r10_best_n_is_one_or_more() -> None:
    with pytest.raises(ValueError, match="1 or more"):
        StandingsRule(best_n=0)
    with pytest.raises(ValueError, match="1 or more"):
        Segment("autumn", 1, 2, best_n=0)


def test_r10_a_segment_ends_no_earlier_than_it_starts() -> None:
    # One round is a legal segment: the range includes both ends.
    Segment("autumn", 2, 2)
    with pytest.raises(ValueError, match="no earlier than its first"):
        Segment("autumn", 3, 2)


def test_r10_a_segment_starts_at_round_1_or_later() -> None:
    # A range below round 1 would match no round and quietly give an empty table.
    with pytest.raises(ValueError, match="first round is 1 or more"):
        Segment("autumn", 0, 2)


def test_r10_segment_names_are_unique() -> None:
    with pytest.raises(ValueError, match="unique"):
        StandingsRule(segments=(Segment("autumn", 1, 2), Segment("autumn", 3, 4)))


def a_round(contests: tuple[ContestConfig, ...], number: int = 1, tee: Tee = TEE) -> RoundFacts:
    """A round with no cards, which is all a check on its contests needs."""
    return RoundFacts(number, tee, contests, {}, {}, (), None)


def a_season(*rounds: RoundFacts) -> SeasonFacts:
    return SeasonFacts(rounds, {}, frozenset(), an_index_rule(), StandingsRule(), {})


def test_r9_a_contest_key_repeated_in_a_round_is_an_error() -> None:
    with pytest.raises(ValueError, match="key"):
        a_round((a_duel("same"), a_field("same")))


def test_r9_a_teambonus_source_that_names_no_duel_contest_of_the_round_is_an_error() -> None:
    # A field contest exists under that key, so a check for "names some contest" passes it.
    with pytest.raises(ValueError, match="duel contest"):
        a_round((a_field(), TeamBonusConfig("bonus", source="field", bonus=Fraction(1))))
    with pytest.raises(ValueError, match="duel contest"):
        a_round((a_duel(), TeamBonusConfig("bonus", source="nothing", bonus=Fraction(1))))


def test_r13_a_round_number_repeated_in_a_season_is_an_error() -> None:
    with pytest.raises(ValueError, match="number"):
        a_season(a_round((), number=1), a_round((), number=1))


def test_r15_a_mode_outside_individual_and_team_is_an_error() -> None:
    with pytest.raises(ValueError, match="mode is individual or team"):
        replace(a_season(), mode="teams")


def test_r7_a_reference_round_on_another_tee_is_an_error() -> None:
    other_tee = Tee(PARS, STROKE_INDEXES, course_rating_tenths=732, slope=120)
    with pytest.raises(ValueError, match="another tee"):
        a_season(
            a_round((), number=1, tee=other_tee),
            a_round((a_duel(reference_rounds=(1,)),), number=2),
        )


def test_r7_a_reference_round_that_is_no_round_of_the_season_is_an_error() -> None:
    with pytest.raises(ValueError, match="no round of the season"):
        a_season(a_round((a_duel(reference_rounds=(9,)),)))


def test_r7_a_reference_round_later_than_its_own_round_is_an_error() -> None:
    with pytest.raises(ValueError, match="later"):
        a_season(
            a_round((a_duel(reference_rounds=(2,)),), number=1),
            a_round((), number=2),
        )


def test_r7_a_reference_round_named_twice_is_an_error() -> None:
    with pytest.raises(ValueError, match="distinct"):
        a_season(
            a_round((), number=1),
            a_round((a_duel(reference_rounds=(1, 1)),), number=2),
        )


PAIRS = {"ann": "red", "bob": "red", "cam": "blue", "dee": "blue"}


def a_team_season(
    teams: dict[str, str] = PAIRS,
    seeded: tuple[str, ...] = tuple(PAIRS),
    round_: RoundFacts | None = None,
) -> SeasonFacts:
    """A team season of those seeded players and teams, with one bestball round of a field."""
    played = round_ or replace(a_round((a_field(),)), format=BestballFormat())
    return SeasonFacts(
        (played,),
        dict.fromkeys(seeded, 100),
        frozenset(),
        an_index_rule(),
        StandingsRule(),
        teams,
        mode="team",
    )


def test_r15_a_team_season_refuses_a_seeded_player_outside_a_team() -> None:
    with pytest.raises(ValueError, match="in no team"):
        a_team_season(seeded=(*PAIRS, "eve"))


def test_r15_a_team_season_refuses_a_team_not_of_two() -> None:
    with pytest.raises(ValueError, match="two players"):
        a_team_season(teams={**PAIRS, "dee": "red"})
    # Every seeded player is in a team, so only the size can refuse it.
    with pytest.raises(ValueError, match="two players"):
        a_team_season(teams={**PAIRS, "eve": "green"}, seeded=(*PAIRS, "eve"))


def test_r15_a_team_season_refuses_a_contest_other_than_field_or_allplay() -> None:
    with pytest.raises(ValueError, match="field or allplay"):
        a_team_season(round_=replace(a_round((a_duel(),)), format=BestballFormat()))


def test_r15_a_team_season_refuses_a_round_without_a_format() -> None:
    with pytest.raises(ValueError, match="has no format"):
        a_team_season(round_=a_round((a_field(),)))


def test_r9_a_manual_award_for_an_unseeded_player_is_an_error() -> None:
    award = ManualAward("zed", "longest-drive", Fraction(2))
    with pytest.raises(ValueError, match="names no competitor"):
        a_season(replace(a_round(()), manual=(award,)))


def test_r9_a_manual_award_in_a_team_season_names_a_team() -> None:
    # ann is seeded and in red, but in a team season red holds the row her award would need.
    award = ManualAward("ann", "longest-drive", Fraction(2))
    played = replace(a_round((a_field(),)), format=BestballFormat(), manual=(award,))
    with pytest.raises(ValueError, match="names no competitor"):
        a_team_season(round_=played)
