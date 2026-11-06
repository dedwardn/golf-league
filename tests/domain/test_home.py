from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from fixtures.team_season import t3_open
from league.domain.configs import (
    BestballFormat,
    CombinedFormat,
    FormatConfig,
    FoursomeFormat,
    GreensomeFormat,
    ScrambleFormat,
)
from league.domain.facts import RoundHeading, SeasonFacts
from league.domain.home import HomePlayer, HomeRound, HomeTeam, home_rounds, time_left
from league.domain.season import compute_season

NOW = datetime(2026, 3, 2, 20, 0)
CLOSES = NOW + timedelta(days=4, hours=1)


def home(facts: SeasonFacts, viewer_id: str, *numbers: int) -> tuple[HomeRound, ...]:
    """The viewer's home over those rounds, read as a service hands them in."""
    headings = tuple(RoundHeading(number, CLOSES) for number in numbers)
    return home_rounds(facts, compute_season(facts), headings, viewer_id, NOW)


def on_format(config: FormatConfig) -> SeasonFacts:
    """R16's example: gus and hal at indexes 10.0 and 20.0, in a round of that format."""
    round_1 = replace(t3_open().rounds[0], format=config)
    seeds = {**T3.seed_index_tenths, "gus": 100, "hal": 200}
    return replace(T3, rounds=(round_1, *T3.rounds[1:]), seed_index_tenths=seeds)


@pytest.mark.parametrize(
    ("left", "expected"),
    [
        (timedelta(days=4, hours=1), "4 days left"),
        (timedelta(days=4, hours=23, minutes=59), "4 days left"),
        (timedelta(days=1), "1 day left"),
        (timedelta(hours=23), "23 hours left"),
        (timedelta(hours=1, minutes=59), "1 hour left"),
        (timedelta(hours=1), "1 hour left"),
        (timedelta(minutes=59), "Under an hour left"),
        (timedelta(0), "Closing soon"),
        (timedelta(days=-2), "Closing soon"),
    ],
)
def test_section_7_time_left(left: timedelta, expected: str) -> None:
    assert time_left(NOW + left, NOW) == expected


@pytest.mark.parametrize(
    ("config", "viewer", "partner"),
    [(BestballFormat(), 9, 17), (CombinedFormat(), 10, 20)],
)
def test_r16_home_gives_each_players_playing_handicap(
    config: FormatConfig, viewer: int, partner: int
) -> None:
    team = home(on_format(config), "gus", 1)[0].team
    assert team is not None
    assert [player.playing_handicap for player in team.players] == [viewer, partner]
    assert team.team_playing_handicap is None


@pytest.mark.parametrize(
    ("config", "expected"),
    [(ScrambleFormat(), 7), (GreensomeFormat(), 14), (FoursomeFormat(), 15)],
)
def test_r16_home_gives_the_team_playing_handicap(config: FormatConfig, expected: int) -> None:
    team = home(on_format(config), "hal", 1)[0].team
    assert team is not None
    assert team.team_playing_handicap == expected
    assert team.players == ()


def test_section_7_home_shows_the_viewer_first_with_each_card_status() -> None:
    hal = home(t3_open(), "hal", 1)[0].team
    gus = home(t3_open(), "gus", 1)[0].team
    assert hal == HomeTeam(
        "bestball", (HomePlayer("hal", 15, False), HomePlayer("gus", 7, True)), None
    )
    assert gus == HomeTeam(
        "bestball", (HomePlayer("gus", 7, True), HomePlayer("hal", 15, False)), None
    )


def test_section_7_home_team_card_status() -> None:
    assert home(t3_open(), "cam", 3)[0].card_in is False
    assert home(t3_open(), "gus", 3)[0].card_in is True


def test_section_7_home_an_own_ball_card_is_the_viewers_own() -> None:
    assert home(t3_open(), "hal", 1)[0].card_in is False
    assert home(t3_open(), "gus", 1)[0].card_in is True


def test_section_7_home_reads_each_heading_against_its_own_round() -> None:
    """Round 2 between them is closed, with 4 teams scored and the combined format."""
    first, third = home(t3_open(), "cam", 1, 3)
    assert (first.number, first.closes_at) == (1, CLOSES)
    assert (first.course, first.tee_name) == ("Trinity Forest Golf Club", "White")
    assert (third.course, third.tee_name) == ("Trinity Forest Golf Club", "Blue")
    assert first.time_left == "4 days left"
    assert third.card_holders == 3
    assert third.team is not None
    assert third.team.format == "scramble"


def test_r17_home_counts_a_team_with_both_cards_only() -> None:
    """Round 1 has 7 cards from 4 teams, and gold lacks hal's."""
    assert home(t3_open(), "ann", 1)[0].card_holders == 3


def test_section_7_home_counts_a_players_counted_cards_in_an_individual_season() -> None:
    assert home(S9B, "ann", 4)[0].card_holders == 6


def test_section_7_home_in_an_individual_season_has_no_team_block() -> None:
    """ann has a season team, which only a teambonus reads."""
    assert home(S9B, "ann", 4)[0].team is None


@pytest.mark.parametrize(("facts", "number"), [(S9B, 4), (t3_open(), 1)])
def test_section_7_home_for_a_viewer_outside_the_season(facts: SeasonFacts, number: int) -> None:
    round_ = home(facts, "nobody", number)[0]
    assert round_.team is None
    assert round_.card_in is False
