from dataclasses import replace

from fixtures.season import SEASON as S9B
from fixtures.team_season import t3_open
from league.domain.bay import bay_round
from league.domain.facts import BaySetting

INTERLEAVED = (
    BaySetting("Weather", "Wind", "Off"),
    BaySetting("Game", "Pins", "Medium"),
    BaySetting("Course", "Green stimp", "9"),
    BaySetting("Weather", "Rain", "None"),
    BaySetting("Game", "Putting", "Auto, Fixed"),
    BaySetting("Display", "Units", "Metric"),
)


def test_section_7_the_bay_reads_the_round_its_format_and_its_tee() -> None:
    bay = bay_round(t3_open(), 3)
    assert bay is not None
    assert (bay.number, bay.format, bay.course, bay.tee_name) == (
        3,
        "scramble",
        "Trinity Forest Golf Club",
        "Blue",
    )


def test_section_7_game_lines_and_other_menus_keep_the_order_written() -> None:
    """Weather, Course, Display is neither sorted nor its reverse, and a set would lose it."""
    bay = bay_round(replace(t3_open(), bay_settings=INTERLEAVED), 1)
    assert bay is not None
    assert [(line.setting, line.value) for line in bay.game] == [
        ("Pins", "Medium"),
        ("Putting", "Auto, Fixed"),
    ]
    assert [(menu.name, [line.setting for line in menu.lines]) for menu in bay.menus] == [
        ("Weather", ["Wind", "Rain"]),
        ("Course", ["Green stimp"]),
        ("Display", ["Units"]),
    ]


def test_section_7_a_season_without_bay_settings_has_no_lines() -> None:
    bay = bay_round(replace(t3_open(), bay_settings=()), 1)
    assert bay is not None
    assert (bay.game, bay.menus) == ((), ())


def test_r15_an_own_ball_round_is_not_shared_ball() -> None:
    bay = bay_round(t3_open(), 1)
    assert bay is not None
    assert not bay.shared_ball


def test_r15_a_shared_ball_round_without_a_team_card_is_shared_ball() -> None:
    facts = t3_open()
    round_3 = replace(facts.rounds[2], team_cards={})
    bay = bay_round(replace(facts, rounds=(*facts.rounds[:2], round_3, *facts.rounds[3:])), 3)
    assert bay is not None
    assert bay.shared_ball


def test_section_7_a_closed_round_has_no_bay() -> None:
    assert bay_round(t3_open(), 2) is None


def test_section_7_an_unknown_round_has_no_bay() -> None:
    assert bay_round(t3_open(), 6) is None


def test_section_7_an_individual_seasons_open_round_has_no_bay_until_s21() -> None:
    assert S9B.rounds[3].closed_at is None
    assert bay_round(S9B, 4) is None
