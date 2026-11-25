from fixtures.season import SEASON as S9B
from fixtures.team_season import SEASON as T3
from fixtures.team_season import t3_open
from league.domain.round_cards import RoundCard, round_cards


def rows(cards: tuple[RoundCard, ...]) -> list[tuple[str, str | None, int | None]]:
    """Each row as its holder, its card's id and its gross."""
    return [
        (row.holder, None if row.card is None else row.card.card_id, row.gross) for row in cards
    ]


def test_r15_own_ball_round_lists_every_player_in_team_order() -> None:
    """team_members reads red first in T3, so team id order has to be chosen."""
    assert rows(round_cards(t3_open(), 1)) == [
        ("cam", "r1-cam", 76),
        ("dee", "r1-dee", 80),
        ("gus", "r1-gus", 72),
        ("hal", None, None),
        ("eve", "r1-eve", 77),
        ("fay", "r1-fay", 78),
        ("ann", "r1-ann", 76),
        ("bob", "r1-bob", 78),
    ]


def test_r15_shared_ball_round_lists_every_team_with_its_team_card() -> None:
    assert rows(round_cards(t3_open(), 3)) == [
        ("blue", None, None),
        ("gold", "r3-gold", 76),
        ("green", "r3-green", 77),
        ("red", "r3-red", 72),
    ]


def test_r13_a_closed_round_lists_its_late_card_as_any_counted_card() -> None:
    """green's team card for round 4 came in after the close."""
    cards = round_cards(T3, 4)
    assert rows(cards) == [
        ("blue", "r4-blue", 78),
        ("gold", "r4-gold", 80),
        ("green", "r4-green", 72),
        ("red", "r4-red", 72),
    ]
    assert cards[2].card == T3.rounds[3].team_cards["green"]


def test_r15_round_cards_of_a_round_not_in_the_facts_list_no_row() -> None:
    """A draft is not in the facts, so this is a draft's case too."""
    assert round_cards(T3, 99) == ()


def test_r15_round_cards_in_an_individual_season_list_no_row() -> None:
    """An individual season's card list is S21's."""
    assert round_cards(S9B, 1) == ()
