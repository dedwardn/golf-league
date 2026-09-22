from fractions import Fraction

from conftest import CLOSED_AT, LATE, net_total

from league.domain.contests import teambonus_awards
from league.domain.facts import TeamBonusConfig
from league.domain.results import Award

BONUS = Fraction(2)


def a_teambonus(multiplier: int = 1) -> TeamBonusConfig:
    """Two points to the team that won most in the duel contest called duel."""
    return TeamBonusConfig(key="teambonus", source="duel", bonus=BONUS, multiplier=multiplier)


def duel_award(player_id: str, points: int) -> Award:
    """One award of the duel contest the teambonus reads."""
    return Award(player_id, "duel", Fraction(points), "win")


def test_r9_teambonus_gives_the_bonus_to_every_on_time_member_of_the_top_team() -> None:
    teams = {"ann": "red", "bob": "red", "cal": "blue", "dee": "blue"}
    entries = [net_total(72, name) for name in teams]
    source = [
        duel_award("ann", 1),
        duel_award("bob", 1),
        duel_award("cal", 0),
        duel_award("dee", 0),
    ]
    assert teambonus_awards(entries, CLOSED_AT, source, teams, a_teambonus()) == (
        Award("ann", "teambonus", BONUS, "bonus"),
        Award("bob", "teambonus", BONUS, "bonus"),
    )


def test_r9_teambonus_two_teams_level_at_the_top_get_half_each() -> None:
    teams = {"ann": "red", "bob": "red", "cal": "blue"}
    entries = [net_total(72, name) for name in teams]
    source = [duel_award("ann", 1), duel_award("bob", 0), duel_award("cal", 1)]
    assert teambonus_awards(entries, CLOSED_AT, source, teams, a_teambonus()) == (
        Award("ann", "teambonus", Fraction(1), "bonus"),
        Award("bob", "teambonus", Fraction(1), "bonus"),
        Award("cal", "teambonus", Fraction(1), "bonus"),
    )


def test_r9_teambonus_three_teams_level_at_the_top_get_a_third_each() -> None:
    # One bonus is shared, so three level teams take a third of it each, exactly.
    teams = {"ann": "red", "bob": "blue", "cal": "green"}
    entries = [net_total(72, name) for name in teams]
    source = [duel_award(name, 1) for name in teams]
    assert teambonus_awards(entries, CLOSED_AT, source, teams, a_teambonus()) == (
        Award("ann", "teambonus", Fraction(2, 3), "bonus"),
        Award("bob", "teambonus", Fraction(2, 3), "bonus"),
        Award("cal", "teambonus", Fraction(2, 3), "bonus"),
    )


def test_r9_teambonus_ignores_players_without_a_season_team() -> None:
    # Eve won the round outright, but she is on no team, so she neither forms one nor scores.
    teams = {"ann": "red", "bob": "blue"}
    entries = [net_total(72, name) for name in ("ann", "bob", "eve")]
    source = [duel_award("ann", 1), duel_award("bob", 0), duel_award("eve", 5)]
    assert teambonus_awards(entries, CLOSED_AT, source, teams, a_teambonus()) == (
        Award("ann", "teambonus", BONUS, "bonus"),
    )


def test_r9_teambonus_with_no_team_among_the_on_time_cards_gives_nothing() -> None:
    entries = [net_total(72, "ann"), net_total(73, "bob")]
    source = [duel_award("ann", 1), duel_award("bob", 0)]
    assert teambonus_awards(entries, CLOSED_AT, source, {}, a_teambonus()) == ()


def test_r9_teambonus_a_member_without_an_on_time_card_gets_nothing() -> None:
    # Bob's team wins, but he handed in no card, so there is nothing to reward him for.
    teams = {"ann": "red", "bob": "red", "cal": "blue"}
    entries = [net_total(72, "ann"), net_total(73, "cal")]
    source = [duel_award("ann", 1), duel_award("cal", 0)]
    assert teambonus_awards(entries, CLOSED_AT, source, teams, a_teambonus()) == (
        Award("ann", "teambonus", BONUS, "bonus"),
    )


def test_r9_teambonus_leaves_awards_from_late_cards_out_of_the_sum() -> None:
    # Dee's late 5 would take blue past red, and earn her a share of a bonus she is not in.
    teams = {"ann": "red", "cal": "blue", "dee": "blue"}
    entries = [net_total(72, "ann"), net_total(73, "cal"), net_total(65, "dee", submitted_at=LATE)]
    source = [duel_award("ann", 1), duel_award("cal", 0), duel_award("dee", 5)]
    assert teambonus_awards(entries, CLOSED_AT, source, teams, a_teambonus()) == (
        Award("ann", "teambonus", BONUS, "bonus"),
    )


def test_r9_teambonus_a_team_with_no_on_time_card_does_not_enter_the_ranking() -> None:
    # Red scored nothing, but blue never played. A sum of nothing is not a sum of zero,
    # so blue does not tie at the top and halve the bonus of the team that turned up.
    teams = {"ann": "red", "cal": "blue"}
    entries = [net_total(72, "ann"), net_total(65, "cal", submitted_at=LATE)]
    source = [duel_award("ann", 0), duel_award("cal", 0)]
    assert teambonus_awards(entries, CLOSED_AT, source, teams, a_teambonus()) == (
        Award("ann", "teambonus", BONUS, "bonus"),
    )


def test_r9_teambonus_two_teams_that_played_and_earned_nothing_share_the_bonus() -> None:
    # This function ranks the teams that played, not the teams holding an award. Ann
    # played and holds none, so seeding sums from round_awards fails here and nowhere else.
    teams = {"ann": "red", "cal": "blue"}
    entries = [net_total(72, "ann"), net_total(73, "cal")]
    source = [duel_award("cal", 0)]
    assert teambonus_awards(entries, CLOSED_AT, source, teams, a_teambonus()) == (
        Award("ann", "teambonus", Fraction(1), "bonus"),
        Award("cal", "teambonus", Fraction(1), "bonus"),
    )


def test_r9_teambonus_sums_only_the_source_contest() -> None:
    # Blue won the field contest of the same round, which this teambonus does not read.
    teams = {"ann": "red", "cal": "blue"}
    entries = [net_total(72, "ann"), net_total(73, "cal")]
    source = [duel_award("ann", 1), duel_award("cal", 0)]
    round_awards = [*source, Award("cal", "field", Fraction(5), "position")]
    assert teambonus_awards(entries, CLOSED_AT, round_awards, teams, a_teambonus()) == (
        Award("ann", "teambonus", BONUS, "bonus"),
    )


def test_r9_teambonus_applies_the_multiplier_to_the_bonus() -> None:
    teams = {"ann": "red", "cal": "blue"}
    entries = [net_total(72, "ann"), net_total(73, "cal")]
    source = [duel_award("ann", 1), duel_award("cal", 0)]
    awards = teambonus_awards(entries, CLOSED_AT, source, teams, a_teambonus(multiplier=3))
    assert awards == (Award("ann", "teambonus", Fraction(6), "bonus"),)
