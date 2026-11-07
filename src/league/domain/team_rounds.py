"""A team season's rounds, for compute_season.

A team season plays every card off the seed index (R15) and builds team scores per contest,
since a combined team scores differently on stableford and on total (R17).
"""

from collections.abc import Mapping

from league.domain.configs import (
    Basis,
    BestballFormat,
    CombinedFormat,
    FoursomeFormat,
    GreensomeFormat,
    ScrambleFormat,
)
from league.domain.contests import (
    allplay_awards,
    allplay_records,
    field_awards,
    is_on_time,
    manual_awards,
)
from league.domain.facts import Card, RoundFacts, SeasonFacts
from league.domain.results import (
    Award,
    ContestEntries,
    NetCard,
    NetEntry,
    Record,
    RoundAwards,
    RoundView,
    points_text,
)
from league.domain.standings import team_round_winners, winning_round_total
from league.domain.strokes import net_card, playing_handicap
from league.domain.teams import own_ball_score, team_members, team_playing_handicap


def _own_ball(
    round_: RoundFacts,
    config: BestballFormat | CombinedFormat,
    players: tuple[str, ...],
    basis: Basis,
    seeds: Mapping[str, int],
) -> tuple[NetCard | None, tuple[Card, ...]]:
    """An own-ball team's score from its players' cards at the format's allowance, and the cards."""
    tee = round_.tee
    cards = [round_.cards.get(player_id) for player_id in players]
    a, b = (
        None
        if card is None
        else net_card(card, tee, playing_handicap(seeds[player_id], tee, config.allowance))
        for player_id, card in zip(players, cards, strict=True)
    )
    return own_ball_score((a, b), config, basis, tee), tuple(filter(None, cards))


def _shared_ball(
    round_: RoundFacts,
    config: ScrambleFormat | GreensomeFormat | FoursomeFormat,
    team_id: str,
    players: tuple[str, ...],
    seeds: Mapping[str, int],
) -> tuple[NetCard | None, tuple[Card, ...]]:
    """A shared-ball team's team card netted at its team playing handicap, and the card."""
    card = round_.team_cards.get(team_id)
    if card is None:
        return None, ()
    a, b = players
    handicap = team_playing_handicap((seeds[a], seeds[b]), round_.tee, config)
    return net_card(card, round_.tee, handicap), (card,)


def _team_entry(
    round_: RoundFacts,
    team_id: str,
    players: tuple[str, ...],
    basis: Basis,
    seeds: Mapping[str, int],
) -> NetEntry | None:
    """One team's score (R17) as an entry whose competitor is the team, or None.

    It carries its latest card's time, so a contest reads a team with a late card as late.
    """
    # SeasonFacts refuses a round of a team season without a format (R15).
    assert round_.format is not None
    if isinstance(round_.format, BestballFormat | CombinedFormat):
        score, cards = _own_ball(round_, round_.format, players, basis, seeds)
    else:
        score, cards = _shared_ball(round_, round_.format, team_id, players, seeds)
    if score is None:
        return None
    latest = max(cards, key=lambda card: (card.submitted_at, card.card_id))
    return NetEntry(latest.card_id, team_id, latest.submitted_at, score)


def _team_contest(round_: RoundFacts, basis: Basis, facts: SeasonFacts) -> ContestEntries:
    """What one contest of a team round reads: each team's score on its basis, in team id order."""
    entries = tuple(
        entry
        for team_id, players in sorted(team_members(facts.teams).items())
        if (entry := _team_entry(round_, team_id, players, basis, facts.seed_index_tenths))
        is not None
    )
    return ContestEntries(round_.tee, round_.closed_at, entries)


def _scores(round_: RoundFacts, facts: SeasonFacts) -> tuple[NetEntry, ...]:
    """Each team with a score in the round (R17), which needs on-time cards, on the stableford
    basis, which the round result reads.

    The cards a score needs are the same on every basis, so these are also the teams with one.
    """
    entries = _team_contest(round_, "stableford", facts).entries
    return tuple(entry for entry in entries if is_on_time(entry, round_.closed_at))


def _team_view(
    round_: RoundFacts,
    round_awards: RoundAwards,
    scores: tuple[NetEntry, ...],
    records: tuple[Record, ...],
) -> RoundView:
    """A team round's awards and, once it closes, its winners on round totals (R15)."""
    total = None if round_.closed_at is None else winning_round_total(round_awards)
    if total is None:
        return RoundView(round_awards, (), None, scores, records)
    winners = team_round_winners(round_awards)
    return RoundView(round_awards, winners, f"{points_text(total)} points", scores, records)


def team_rounds(facts: SeasonFacts) -> tuple[RoundView, ...]:
    """A team season's rounds: field and allplay over the teams' scores, then manual awards.

    SeasonFacts has refused every other contest kind (R15). Decision 6 gives each round one
    allplay contest, whose records the round result reads.
    """
    views: list[RoundView] = []
    for round_ in facts.rounds:
        awards: list[Award] = []
        records: tuple[Record, ...] = ()
        for config in round_.contests:
            if config.kind == "field":
                awards.extend(field_awards(_team_contest(round_, config.basis, facts), config))
            if config.kind == "allplay":
                contest = _team_contest(round_, config.basis, facts)
                awards.extend(allplay_awards(contest, config))
                records = allplay_records(contest, config.basis)
        all_awards = (*awards, *manual_awards(round_.manual))
        scores = _scores(round_, facts)
        holders = tuple(entry.competitor_id for entry in scores)
        round_awards = RoundAwards(round_.number, all_awards, holders)
        views.append(_team_view(round_, round_awards, scores, records))
    return tuple(views)
