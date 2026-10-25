from fractions import Fraction

from league.domain.facts import Pairing
from league.domain.pairing import high_low_pairings, random_pairings, swiss_pairings
from league.domain.results import StandingsRow


def rows(*points: tuple[str, int]) -> tuple[StandingsRow, ...]:
    """A table in points order, a position each, as standings() returns it."""
    return tuple(
        StandingsRow(place, player_id, Fraction(value))
        for place, (player_id, value) in enumerate(points, start=1)
    )


def ranked_rows(*player_ids: str) -> tuple[StandingsRow, ...]:
    """A table with no ties, best first, where points fall by one down the order."""
    return rows(
        *((player_id, len(player_ids) - place) for place, player_id in enumerate(player_ids))
    )


def level_indexes(*player_ids: str) -> dict[str, int]:
    """Equal indexes, for the tables where the standings order alone decides."""
    return {player_id: 0 for player_id in player_ids}


def test_r11_round_one_is_ordered_by_index() -> None:
    # Round 1: everyone shares first place on 0 points, so only the index orders them.
    standings = tuple(StandingsRow(1, player_id, Fraction(0)) for player_id in "abcdef")
    index_tenths = {"a": 200, "b": 100, "c": 150, "d": 50, "e": 300, "f": 250}
    assert swiss_pairings(standings, index_tenths, []) == (
        Pairing(("d",), ("b",)),
        Pairing(("c",), ("a",)),
        Pairing(("f",), ("e",)),
    )


def test_r11_a_shared_position_is_broken_by_index_then_player_id() -> None:
    standings = (
        StandingsRow(1, "ann", Fraction(10)),
        StandingsRow(2, "bob", Fraction(5)),
        StandingsRow(2, "cam", Fraction(5)),
        StandingsRow(2, "dee", Fraction(5)),
    )
    index_tenths = {"ann": 100, "bob": 200, "cam": 150, "dee": 200}
    # cam is lowest on index of the three who share second, then bob and dee by id.
    assert swiss_pairings(standings, index_tenths, []) == (
        Pairing(("ann",), ("cam",)),
        Pairing(("bob",), ("dee",)),
    )


def test_r11_pairs_the_highest_ranked_unmet_player() -> None:
    standings = ranked_rows("ann", "bob", "cam", "dee")
    history = [[Pairing(("ann",), ("bob",)), Pairing(("cam",), ("dee",))]]
    # ann skips bob, whom she has met, for the next player down.
    assert swiss_pairings(standings, level_indexes("ann", "bob", "cam", "dee"), history) == (
        Pairing(("ann",), ("cam",)),
        Pairing(("bob",), ("dee",)),
    )


def test_r11_all_met_takes_the_least_recent_rematch() -> None:
    standings = ranked_rows("ann", "bob", "cam", "dee")
    history = [
        [Pairing(("ann",), ("cam",)), Pairing(("bob",), ("dee",))],
        [Pairing(("ann",), ("dee",)), Pairing(("bob",), ("cam",))],
        [Pairing(("ann",), ("bob",)), Pairing(("cam",), ("dee",))],
    ]
    # ann has met everyone. bob is the highest ranked, but cam was the longest ago.
    assert swiss_pairings(standings, level_indexes("ann", "bob", "cam", "dee"), history) == (
        Pairing(("ann",), ("cam",)),
        Pairing(("bob",), ("dee",)),
    )


def test_r11_a_tie_on_least_recent_goes_to_the_highest_ranked() -> None:
    standings = ranked_rows("ann", "bob", "cam", "dee")
    history = [
        [Pairing(("ann", "dee"), ("bob", "cam"))],
        [Pairing(("ann",), ("dee",)), Pairing(("bob",), ("cam",))],
    ]
    # ann has met everyone, and met bob and cam in the same round as that best ball side,
    # so the tie goes to bob, the higher ranked of the two.
    assert swiss_pairings(standings, level_indexes("ann", "bob", "cam", "dee"), history) == (
        Pairing(("ann",), ("bob",)),
        Pairing(("cam",), ("dee",)),
    )


def test_r11_opposite_best_ball_sides_have_met() -> None:
    standings = ranked_rows("ann", "bob", "cam", "dee")
    history = [[Pairing(("ann", "cam"), ("bob", "dee"))]]
    # ann met both of the other side, so the only player she has not met is her partner.
    assert swiss_pairings(standings, level_indexes("ann", "bob", "cam", "dee"), history) == (
        Pairing(("ann",), ("cam",)),
        Pairing(("bob",), ("dee",)),
    )


def test_r11_the_odd_player_is_the_lowest_ranked_with_the_fewest_single_sided_pairings() -> None:
    standings = ranked_rows("ann", "bob", "cam", "dee", "eve")
    history = [
        [Pairing(("ann",), ("bob",)), Pairing(("cam",), ("dee",)), Pairing(("eve",))],
    ]
    # eve has had one, so it rotates up to dee, and eve is paired like anyone else.
    # Pairing from the top first would have left eve over instead.
    indexes = level_indexes("ann", "bob", "cam", "dee", "eve")
    assert swiss_pairings(standings, indexes, history) == (
        Pairing(("ann",), ("cam",)),
        Pairing(("bob",), ("eve",)),
        Pairing(("dee",)),
    )


def test_r11_once_everyone_has_had_one_the_rotation_starts_again_from_the_bottom() -> None:
    standings = ranked_rows("ann", "bob", "cam", "dee", "eve")
    history = [
        [Pairing(("eve",))],
        [Pairing(("dee",))],
        [Pairing(("cam",))],
        [Pairing(("bob",))],
        [Pairing(("ann",))],
    ]
    indexes = level_indexes("ann", "bob", "cam", "dee", "eve")
    assert swiss_pairings(standings, indexes, history) == (
        Pairing(("ann",), ("bob",)),
        Pairing(("cam",), ("dee",)),
        Pairing(("eve",)),
    )


def test_r11_a_player_absent_from_a_round_has_not_had_a_single_sided_pairing() -> None:
    standings = ranked_rows("ann", "bob", "cam", "dee", "eve")
    # eve was in no pairing, so under R9 she met the virtual side. That is not one of these.
    history = [[Pairing(("ann",), ("bob",)), Pairing(("cam",), ("dee",))]]
    indexes = level_indexes("ann", "bob", "cam", "dee", "eve")
    assert swiss_pairings(standings, indexes, history) == (
        Pairing(("ann",), ("cam",)),
        Pairing(("bob",), ("dee",)),
        Pairing(("eve",)),
    )


def test_r11_high_low_joins_the_highest_with_the_lowest_and_the_middle_plays_alone() -> None:
    standings = ranked_rows("ann", "bob", "cam", "dee", "eve")
    indexes = level_indexes("ann", "bob", "cam", "dee", "eve")
    # ann+eve and bob+dee are both on 6, so the side with the better member leads.
    assert high_low_pairings(standings, indexes) == (
        Pairing(("ann", "eve"), ("bob", "dee")),
        Pairing(("cam",)),
    )


def test_r11_high_low_sides_are_paired_by_combined_points() -> None:
    standings = rows(
        ("ann", 100),
        ("bob", 50),
        ("cam", 49),
        ("dee", 40),
        ("eve", 30),
        ("fay", 29),
        ("gus", 1),
        ("hal", 0),
    )
    indexes = level_indexes("ann", "bob", "cam", "dee", "eve", "fay", "gus", "hal")
    # Combined: ann+hal 100, cam+fay 78, dee+eve 70, bob+gus 51, which is not the order
    # the sides were formed in.
    assert high_low_pairings(standings, indexes) == (
        Pairing(("ann", "hal"), ("cam", "fay")),
        Pairing(("dee", "eve"), ("bob", "gus")),
    )


def test_r11_random_sides_are_reproducible_from_rng_seed() -> None:
    standings = ranked_rows("ann", "bob", "cam", "dee", "eve")
    indexes = level_indexes("ann", "bob", "cam", "dee", "eve")
    # Seed 1 shuffles the ranked order to cam, dee, eve, ann, bob: consecutive pairs, and
    # bob, last of the shuffle, alone. eve+ann on 6 leads cam+dee on 5, and bob on 4 trails.
    assert random_pairings(standings, indexes, 1) == (
        Pairing(("eve", "ann"), ("cam", "dee")),
        Pairing(("bob",)),
    )
    # Seed 2 shuffles to cam, bob, dee, eve, ann, so ann is alone on 5, above dee+eve on 3.
    # The lone player still takes the single-sided pairing, and the two-player sides meet.
    assert random_pairings(standings, indexes, 2) == (
        Pairing(("cam", "bob"), ("dee", "eve")),
        Pairing(("ann",)),
    )


def test_r11_an_odd_number_of_sides_gives_the_one_member_side_the_single_sided_pairing() -> None:
    players = ("ann", "bob", "cam", "dee", "eve", "fay", "gus", "hal", "ivy")
    standings = ranked_rows(*players)
    # Nine players make four joined sides and one alone, five in all, so a side plays alone.
    assert high_low_pairings(standings, level_indexes(*players)) == (
        Pairing(("ann", "ivy"), ("bob", "hal")),
        Pairing(("cam", "gus"), ("dee", "fay")),
        Pairing(("eve",)),
    )


def test_r11_an_odd_number_of_two_player_sides_gives_the_lowest_side_the_single_sided_pairing() -> (
    None
):
    standings = rows(
        ("ann", 100),
        ("bob", 50),
        ("cam", 49),
        ("dee", 40),
        ("eve", 30),
        ("fay", 29),
        ("gus", 20),
        ("hal", 10),
        ("ivy", 5),
        ("jan", 0),
    )
    players = tuple(row.competitor_id for row in standings)
    # Ten players make five two-player sides and no one-member side, so the side lowest on
    # combined points plays alone: bob+ivy on 55, though bob himself is second in the table.
    assert high_low_pairings(standings, level_indexes(*players)) == (
        Pairing(("ann", "jan"), ("dee", "gus")),
        Pairing(("cam", "hal"), ("eve", "fay")),
        Pairing(("bob", "ivy")),
    )
