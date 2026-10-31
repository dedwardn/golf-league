"""compute_season: the one pipeline from a season's facts to what every screen shows.

It calls the rule modules in order and holds no rule of its own. Each contest nets the round's
cards at its own allowance (R7), so entries are built per contest and never kept per round:
two contests of one round at different allowances need different net cards.
"""

from collections.abc import Mapping

from league.domain.configs import AllplayConfig, DuelConfig, FieldConfig
from league.domain.contests import (
    allplay_awards,
    duel_awards,
    field_awards,
    is_on_time,
    manual_awards,
    teambonus_awards,
)
from league.domain.facts import Card, RoundFacts, SeasonFacts, Tee
from league.domain.index import index_by_card_tenths
from league.domain.results import (
    Award,
    ContestEntries,
    NetEntry,
    RoundAwards,
    RoundView,
    SeasonView,
    SegmentView,
)
from league.domain.standings import round_winners, standings
from league.domain.strokes import FULL_ALLOWANCE, net_card, playing_handicap
from league.domain.team_rounds import team_rounds


def _index_by_card(facts: SeasonFacts) -> dict[str, dict[str, int]]:
    """Player id to card id to the index that card was played off (R6), late cards included.

    Keyed by player first, so a card id that two players share can never cross between them.
    """
    played: dict[str, list[tuple[Card, Tee]]] = {}
    for round_ in facts.rounds:
        for player_id, card in round_.cards.items():
            played.setdefault(player_id, []).append((card, round_.tee))
    return {
        player_id: index_by_card_tenths(
            facts.seed_index_tenths[player_id],
            player_id in facts.provisional,
            cards,
            facts.index_rule,
        )
        for player_id, cards in played.items()
    }


def _entries(
    round_: RoundFacts, allowance: int, indexes: Mapping[str, Mapping[str, int]]
) -> tuple[NetEntry, ...]:
    """The round's cards netted at that allowance, each off its own index, in player id order.

    Player id order rather than the mapping's, so two equal seasons give equal views.
    """
    return tuple(
        NetEntry(
            card.card_id,
            player_id,
            card.submitted_at,
            net_card(
                card,
                round_.tee,
                playing_handicap(indexes[player_id][card.card_id], round_.tee, allowance),
            ),
        )
        for player_id, card in sorted(round_.cards.items())
    )


def _on_time(
    round_: RoundFacts, allowance: int, indexes: Mapping[str, Mapping[str, int]]
) -> list[NetEntry]:
    """Those entries filtered against that round's own close."""
    return [
        entry
        for entry in _entries(round_, allowance, indexes)
        if is_on_time(entry, round_.closed_at)
    ]


def _references(
    round_: RoundFacts,
    config: DuelConfig,
    facts: SeasonFacts,
    indexes: Mapping[str, Mapping[str, int]],
) -> list[NetEntry]:
    """The on-time cards a duel's virtual sides are drawn from, at its own allowance (R7).

    SeasonFacts has already refused a named round that is missing or on another tee.
    """
    numbers = config.reference_rounds or (round_.number,)
    by_number = {played.number: played for played in facts.rounds}
    return [
        entry
        for number in numbers
        for entry in _on_time(by_number[number], config.allowance, indexes)
    ]


def _card_contest_awards(
    round_: RoundFacts,
    config: DuelConfig | FieldConfig | AllplayConfig,
    facts: SeasonFacts,
    indexes: Mapping[str, Mapping[str, int]],
) -> tuple[Award, ...]:
    """One card-reading contest's awards, from the round's cards netted at its allowance."""
    entries = _entries(round_, config.allowance, indexes)
    contest = ContestEntries(round_.tee, round_.closed_at, entries)
    if config.kind == "duel":
        references = _references(round_, config, facts, indexes)
        return duel_awards(contest, references, round_.pairings[config.key], config)
    if config.kind == "field":
        return field_awards(contest, config)
    return allplay_awards(contest, config)


def _round_awards(
    round_: RoundFacts, facts: SeasonFacts, indexes: Mapping[str, Mapping[str, int]]
) -> RoundAwards:
    """Every contest's awards in config order, then the manual ones (R9).

    A teambonus runs after the contests that read cards and is handed only its source's
    awards, so a manual award that shares the source's key never reaches a team's sum.
    """
    by_key: dict[str, tuple[Award, ...]] = {}
    for config in round_.contests:
        if config.kind != "teambonus":
            by_key[config.key] = _card_contest_awards(round_, config, facts, indexes)
    # A teambonus reads only who has an on-time card, so the allowance of these is immaterial.
    entries = _entries(round_, FULL_ALLOWANCE, indexes)
    for config in round_.contests:
        if config.kind == "teambonus":
            source = by_key[config.source]
            by_key[config.key] = teambonus_awards(
                entries, round_.closed_at, source, facts.teams, config
            )
    awards = tuple(award for config in round_.contests for award in by_key[config.key])
    return RoundAwards(round_.number, awards + manual_awards(round_.manual))


def _winners(round_: RoundFacts, indexes: Mapping[str, Mapping[str, int]]) -> tuple[str, ...]:
    """A closed round's winners at full playing handicap (R10), and none while it is open."""
    if round_.closed_at is None:
        return ()
    return round_winners(_on_time(round_, FULL_ALLOWANCE, indexes))


def _individual_rounds(facts: SeasonFacts) -> tuple[RoundView, ...]:
    """An individual season's rounds, each card played off the index R6 gave it."""
    indexes = _index_by_card(facts)
    return tuple(
        RoundView(_round_awards(round_, facts, indexes), _winners(round_, indexes))
        for round_ in facts.rounds
    )


def compute_season(facts: SeasonFacts) -> SeasonView:
    """Every round's awards and winners, the season table and each segment's, from facts alone.

    Tables count closed rounds only (R10), so an open round's awards are in its view and in
    no table. In a team season the teams are the competitors. Raises KeyError where a card it
    reads needs a seed index the facts lack, or for a duel whose key has no pairings, and
    ValueError only as the rule functions raise it.
    """
    if facts.mode == "team":
        rounds = team_rounds(facts)
        competitors = tuple(sorted(set(facts.teams.values())))
    else:
        rounds = _individual_rounds(facts)
        competitors = tuple(facts.seed_index_tenths)
    closed = [
        view.awards
        for view, round_ in zip(rounds, facts.rounds, strict=True)
        if round_.closed_at is not None
    ]
    rule = facts.standings_rule
    segments = tuple(
        SegmentView(segment.name, standings(closed, competitors, rule, segment))
        for segment in rule.segments
    )
    return SeasonView(rounds, standings(closed, competitors, rule), segments)
