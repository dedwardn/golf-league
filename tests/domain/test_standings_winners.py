from conftest import net_total

from league.domain.standings import round_winners


def test_r10_the_lowest_net_total_wins_the_round() -> None:
    entries = [net_total(71, "ann"), net_total(70, "bob"), net_total(72, "cal")]
    assert round_winners(entries) == ("bob",)


def test_r10_players_level_on_the_lowest_net_total_share_the_round() -> None:
    # Cal comes before Bob in the entries, so the order is the sort's and not the input's.
    entries = [net_total(70, "cal"), net_total(70, "bob"), net_total(71, "ann")]
    assert round_winners(entries) == ("bob", "cal")


def test_r10_no_on_time_card_means_no_winner() -> None:
    assert round_winners([]) == ()
