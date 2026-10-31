from dataclasses import replace
from datetime import timedelta
from fractions import Fraction

from conftest import dropped, kept, with_round

from fixtures.season import DEE_LATE, ROUND_2, ROUND_3, ROUND_4, SEASON
from league.domain.configs import DuelConfig
from league.domain.facts import Pairing, SeasonFacts
from league.domain.results import Award, Gap, RoundAwards, SegmentView, StandingsRow
from league.domain.season import compute_season


def round_4_awards(season: SeasonFacts) -> tuple[Award, ...]:
    return compute_season(season).rounds[3].awards.awards


def field_points(season: SeasonFacts) -> dict[str, Fraction]:
    """Each player's points from round 4's field contest."""
    return {
        award.competitor_id: award.points
        for award in round_4_awards(season)
        if award.key == "field"
    }


ROUND_1_AWARDS = (
    Award("ann", "field", Fraction(2), "position"),
    Award("bob", "field", Fraction(2), "position"),
    Award("cam", "field", Fraction(10), "position"),
    Award("dee", "field", Fraction(2), "position"),
    Award("eve", "field", Fraction(2), "position"),
    Award("fay", "field", Fraction(2), "position"),
    Award("eve", "longest-drive", Fraction(2), "manual"),
)
ROUND_2_AWARDS = (
    Award("ann", "duel", Fraction(3), "win"),
    Award("fay", "duel", Fraction(0), "loss"),
    Award("bob", "duel", Fraction(3), "win"),
    Award("eve", "duel", Fraction(0), "loss"),
    Award("cam", "duel", Fraction(3), "win"),
    Award("dee", "duel", Fraction(3), "win"),
)
ROUND_3_AWARDS = (
    Award("ann", "allplay", Fraction(3, 5), "record"),
    Award("bob", "allplay", Fraction(9, 5), "record"),
    Award("cam", "allplay", Fraction(3, 5), "record"),
    Award("dee", "allplay", Fraction(9, 5), "record"),
    Award("eve", "allplay", Fraction(3, 5), "record"),
    Award("fay", "allplay", Fraction(3, 5), "record"),
)
BESTBALL = (
    Award("ann", "bb", Fraction(4), "win"),
    Award("bob", "bb", Fraction(4), "win"),
    Award("dee", "bb", Fraction(0), "loss"),
    Award("eve", "bb", Fraction(0), "loss"),
    Award("cam", "bb", Fraction(4), "win"),
    Award("fay", "bb", Fraction(4), "win"),
)
# R9: east takes 12 from the best ball and west 4. dee's manual 20 under the key bb would
# make west 24 if a teambonus summed manual awards.
BONUS = (
    Award("ann", "bonus", Fraction(3), "bonus"),
    Award("bob", "bonus", Fraction(3), "bonus"),
    Award("cam", "bonus", Fraction(3), "bonus"),
)
# R7: at 100 fay leads on 70 and wins her best ball; at 75 ann does. Entries reused from
# the duel would give fay 12 and four players 5 each.
FIELD_AT_75 = (
    Award("ann", "field", Fraction(12), "position"),
    Award("bob", "field", Fraction(8), "position"),
    Award("cam", "field", Fraction(5), "position"),
    Award("dee", "field", Fraction(1), "position"),
    Award("eve", "field", Fraction(1), "position"),
    Award("fay", "field", Fraction(5), "position"),
)
ROUND_4_MANUAL = (Award("dee", "bb", Fraction(20), "manual"),)
EVERYONE = ("ann", "bob", "cam", "dee", "eve", "fay")


def test_r9_the_golden_season_awards_every_round() -> None:
    assert [view.awards for view in compute_season(SEASON).rounds] == [
        RoundAwards(1, ROUND_1_AWARDS, EVERYONE),
        RoundAwards(2, ROUND_2_AWARDS, EVERYONE),
        RoundAwards(3, ROUND_3_AWARDS, EVERYONE),
        RoundAwards(4, BESTBALL + BONUS + FIELD_AT_75 + ROUND_4_MANUAL, EVERYONE),
    ]


def test_r10_the_golden_season_standings() -> None:
    # Best 2 of rounds 1 to 3. eve's longest drive is added on top of her best two.
    # Round 4 is open, so nobody's card in it counts.
    assert compute_season(SEASON).standings == (
        StandingsRow(1, "cam", Fraction(13), 3, (kept(10), kept(3), dropped(Fraction(3, 5))), None),
        StandingsRow(
            2,
            "ann",
            Fraction(5),
            3,
            (kept(2), kept(3), dropped(Fraction(3, 5))),
            Gap(Fraction(8), 1),
        ),
        StandingsRow(
            2,
            "bob",
            Fraction(5),
            3,
            (kept(2), kept(3), dropped(Fraction(9, 5))),
            Gap(Fraction(8), 1),
        ),
        StandingsRow(
            2,
            "dee",
            Fraction(5),
            3,
            (kept(2), kept(3), dropped(Fraction(9, 5))),
            Gap(Fraction(8), 1),
        ),
        StandingsRow(
            5,
            "eve",
            Fraction(23, 5),
            3,
            (kept(2), dropped(0), kept(Fraction(3, 5))),
            Gap(Fraction(2, 5), 2),
        ),
        StandingsRow(
            6,
            "fay",
            Fraction(13, 5),
            3,
            (kept(2), dropped(0), kept(Fraction(3, 5))),
            Gap(Fraction(2), 5),
        ),
    )


def test_r10_the_golden_season_segment_table() -> None:
    assert compute_season(SEASON).segments == (
        SegmentView(
            "first-half",
            (
                StandingsRow(1, "cam", Fraction(13), 2, (kept(10), kept(3)), None),
                StandingsRow(2, "ann", Fraction(5), 2, (kept(2), kept(3)), Gap(Fraction(8), 1)),
                StandingsRow(2, "bob", Fraction(5), 2, (kept(2), kept(3)), Gap(Fraction(8), 1)),
                StandingsRow(2, "dee", Fraction(5), 2, (kept(2), kept(3)), Gap(Fraction(8), 1)),
                StandingsRow(5, "eve", Fraction(4), 2, (kept(2), kept(0)), Gap(Fraction(1), 2)),
                StandingsRow(6, "fay", Fraction(2), 2, (kept(2), kept(0)), Gap(Fraction(2), 5)),
            ),
            None,
        ),
    )


def test_r10_the_golden_season_round_winners() -> None:
    assert [view.winners for view in compute_season(SEASON).rounds] == [
        ("cam",),
        ("eve",),
        ("bob", "dee"),
        (),
    ]


def test_r10_the_golden_season_winning_totals() -> None:
    totals = [view.winning_total for view in compute_season(SEASON).rounds]
    assert totals == ["70 net", "71 net", "71 net", None]


def test_r10_each_table_says_the_best_n_it_counts_with() -> None:
    view = compute_season(SEASON)
    assert view.best_n == 2
    assert [table.best_n for table in view.segments] == [None]


def test_r10_a_late_card_counts_on_a_row_without_a_round_total() -> None:
    # Allplay scores no late card (R9), so fay's round 3 is a counted card with no award.
    assert ROUND_3.closed_at is not None
    late = replace(ROUND_3.cards["fay"], submitted_at=ROUND_3.closed_at + timedelta(hours=1))
    season = with_round(SEASON, replace(ROUND_3, cards={**ROUND_3.cards, "fay": late}))
    fay = next(row for row in compute_season(season).standings if row.competitor_id == "fay")
    assert fay.counted_cards == 3
    assert len(fay.round_totals) == 2


def test_r10_a_late_card_does_not_win_its_round() -> None:
    # dee's late 71 is level with eve's. Closed after it, the round is theirs to share.
    counted = with_round(SEASON, replace(ROUND_2, closed_at=DEE_LATE))
    assert compute_season(SEASON).rounds[1].winners == ("eve",)
    assert compute_season(counted).rounds[1].winners == ("dee", "eve")


def test_r10_an_open_round_scores_in_no_table() -> None:
    view = compute_season(SEASON)
    without_round_4 = compute_season(replace(SEASON, rounds=SEASON.rounds[:3]))
    assert view.rounds[3].awards.awards
    assert view.standings == without_round_4.standings
    assert view.segments == without_round_4.segments


def test_r6_a_late_card_moves_its_players_index_for_their_next_card() -> None:
    # The late card takes dee from 12.0 to 11.5, and round 3 to 11.3: off 8 at 75, net 76,
    # level fifth with eve. Without it she reaches round 4 on 11.5, off 9, and is fifth alone.
    without = with_round(
        SEASON,
        replace(ROUND_2, cards={p: card for p, card in ROUND_2.cards.items() if p != "dee"}),
    )
    replayed = field_points(SEASON)
    on_time_only = field_points(without)
    assert (replayed["dee"], replayed["eve"]) == (Fraction(1), Fraction(1))
    assert (on_time_only["dee"], on_time_only["eve"]) == (Fraction(2), Fraction(0))


def test_r9_a_teambonus_runs_after_the_contest_its_source_names() -> None:
    bb, bonus, field = ROUND_4.contests
    bonus_first = with_round(SEASON, replace(ROUND_4, contests=(bonus, bb, field)))
    assert round_4_awards(bonus_first) == BONUS + BESTBALL + FIELD_AT_75 + ROUND_4_MANUAL


def a_reference_duel(key: str, allowance: int) -> DuelConfig:
    """A single duel on total whose virtual side is the best one card of round 2."""
    return DuelConfig(
        key,
        "total",
        points_win=Fraction(3),
        points_draw=Fraction(1),
        points_loss=Fraction(0),
        side="single",
        virtual_n=1,
        allowance=allowance,
        reference_rounds=(2,),
    )


def test_r7_a_named_reference_round_gives_its_on_time_cards_at_this_contests_allowance() -> None:
    # At 100 eve's 72 meets the best on-time round-2 card but her own, a 72, and draws. dee's
    # late 71, or round 3's own 71s, would beat her. At 75 round 2 nets ann 72, bob 73, cam
    # 74, eve 75, fay 76, so ann's 72 meets bob's 73 and wins. Netted at 100 the pool's best
    # is eve's 71; round 3's own cards at 75 give bob's 72.
    alone = (Pairing(("ann",)),)
    duels = replace(
        ROUND_3,
        contests=(a_reference_duel("d100", 100), a_reference_duel("d75", 75)),
        pairings={"d100": alone, "d75": alone},
    )
    awards = compute_season(with_round(SEASON, duels)).rounds[2].awards.awards
    by_player_and_key = {(award.competitor_id, award.key): award for award in awards}
    assert by_player_and_key["eve", "d100"] == Award("eve", "d100", Fraction(1), "draw")
    assert by_player_and_key["ann", "d75"] == Award("ann", "d75", Fraction(3), "win")


def test_r5_a_provisional_player_moves_at_the_early_rate() -> None:
    # At 70 percent dee's late 83 takes her from 12.0 to 11.3, so she plays round 3 off 11
    # and nets 72, and bob wins it alone.
    provisional = replace(SEASON, provisional=frozenset({"dee"}))
    assert compute_season(provisional).rounds[2].winners == ("bob",)
