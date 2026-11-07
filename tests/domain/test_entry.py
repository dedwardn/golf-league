from dataclasses import replace
from datetime import datetime

import pytest

from fixtures.season import SEASON as S9B
from fixtures.team_season import PARS, t3_open
from fixtures.team_season import SEASON as T3
from league.domain.entry import CardEntry, CardIn, card_entry

NOW = datetime(2026, 3, 2, 20, 0)
# The design's card: out 41, in 40.
DESIGN = (4, 5, 3, 5, 6, 5, 5, 4, 4, 5, 3, 4, 5, 4, 6, 5, 3, 5)


def test_section_7_entry_reads_the_round_its_tee_and_par() -> None:
    entry = card_entry(t3_open(), 1, "hal", NOW, ())
    assert isinstance(entry, CardEntry)
    assert (entry.number, entry.course, entry.tee_name, entry.pars, entry.par_total) == (
        1,
        "Trinity Forest Golf Club",
        "White",
        PARS,
        72,
    )
    assert entry.scores == ()


def test_section_7_check_the_card_adds_out_in_and_total() -> None:
    entry = card_entry(t3_open(), 1, "hal", NOW, DESIGN)
    assert isinstance(entry, CardEntry)
    assert (entry.scores, entry.out_total, entry.in_total, entry.total) == (DESIGN, 41, 40, 81)


def with_holes(changes: dict[int, int | None]) -> tuple[int | None, ...]:
    """The design's card with the given holes changed, None for one empty or not a number."""
    return tuple(changes.get(hole, score) for hole, score in enumerate(DESIGN, start=1))


def test_r13_holes_empty_or_outside_one_to_nineteen_are_in_error() -> None:
    entry = card_entry(t3_open(), 1, "hal", NOW, with_holes({3: None, 7: 0, 12: 20, 1: 1, 18: 19}))
    assert isinstance(entry, CardEntry)
    assert entry.error_holes == (3, 7, 12)


@pytest.mark.parametrize(
    ("changes", "text"),
    [
        pytest.param({5: None}, "Looks like an error on hole 5.", id="one"),
        pytest.param({5: 20, 12: None}, "Looks like an error on holes 5 and 12.", id="two"),
        pytest.param(
            {5: 0, 9: None, 12: 20}, "Looks like an error on holes 5, 9 and 12.", id="three"
        ),
    ],
)
def test_section_7_the_warn_line_names_the_holes_in_error(
    changes: dict[int, int | None], text: str
) -> None:
    entry = card_entry(t3_open(), 1, "hal", NOW, with_holes(changes))
    assert isinstance(entry, CardEntry)
    assert entry.error_text == text


def test_section_7_a_card_is_ready_once_typed_with_no_hole_in_error() -> None:
    ready = [
        entry.ready
        for scores in ((), DESIGN, with_holes({5: None}))
        if isinstance(entry := card_entry(t3_open(), 1, "hal", NOW, scores), CardEntry)
    ]
    assert ready == [False, True, False]


def test_r15_a_shared_ball_round_takes_the_teams_card() -> None:
    """Round 3 is not the first open round, so an entry for the wrong round shows here."""
    entry = card_entry(t3_open(), 3, "cam", NOW, ())
    assert isinstance(entry, CardEntry)
    assert (entry.number, entry.tee_name) == (3, "Blue")


def test_r15_the_card_is_in_once_the_viewers_own_is() -> None:
    assert "gus" in t3_open().rounds[0].cards
    assert card_entry(t3_open(), 1, "gus", NOW, ()) == CardIn()


def test_r15_the_card_is_in_once_the_teams_team_card_is() -> None:
    """ann has no card of her own in a shared-ball round, so only red's team card says so."""
    round_3 = t3_open().rounds[2]
    assert ("ann" not in round_3.cards, "red" in round_3.team_cards) == (True, True)
    assert card_entry(t3_open(), 3, "ann", NOW, ()) == CardIn()


def test_r15_a_partners_card_alone_leaves_the_viewers_to_hand_in() -> None:
    round_1 = t3_open().rounds[0]
    assert ("gus" in round_1.cards, "hal" in round_1.cards) == (True, False)
    assert isinstance(card_entry(t3_open(), 1, "hal", NOW, ()), CardEntry)


def test_r15_the_card_is_in_on_a_closed_round_too() -> None:
    assert t3_open().rounds[1].closed_at is not None
    assert card_entry(t3_open(), 2, "hal", NOW, ()) == CardIn()


def test_r13_no_entry_for_a_closed_or_unknown_round() -> None:
    assert "hal" not in T3.rounds[0].cards
    assert card_entry(T3, 1, "hal", NOW, ()) is None
    assert card_entry(t3_open(), 6, "hal", NOW, ()) is None


def test_r13_no_entry_for_a_viewer_outside_the_season() -> None:
    assert card_entry(t3_open(), 1, "ivy", NOW, ()) is None


def test_section_7_no_entry_in_an_individual_season_until_s21() -> None:
    *played, round_4 = S9B.rounds
    cards = {player_id: card for player_id, card in round_4.cards.items() if player_id != "ann"}
    facts = replace(S9B, rounds=(*played, replace(round_4, cards=cards)))
    assert "ann" in facts.seed_index_tenths
    assert "ann" not in facts.rounds[3].cards
    assert card_entry(facts, 4, "ann", NOW, ()) is None
    assert "ann" in S9B.rounds[3].cards
    assert card_entry(S9B, 4, "ann", NOW, ()) is None
