"""compute_season: the one pipeline from a season's facts to what every screen shows.

It calls the rule modules in order and holds no rule of its own. Each contest nets the round's
cards at its own allowance (R7), so entries are built per contest and never kept per round:
two contests of one round at different allowances need different net cards.

A team season plays every card off the seed index (R15) and builds team scores per contest,
since a combined team scores differently on stableford and on total (R17).
"""

from collections.abc import Mapping

from league.domain.configs import (
    AllplayConfig,
    Basis,
    BestballFormat,
    CombinedFormat,
    DuelConfig,
    FieldConfig,
    FoursomeFormat,
    GreensomeFormat,
    ScrambleFormat,
)
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
    NetCard,
    NetEntry,
    RoundAwards,
    RoundView,
    SeasonView,
    SegmentView,
)
from league.domain.standings import round_winners, standings, team_round_winners
from league.domain.strokes import FULL_ALLOWANCE, net_card, playing_handicap
from league.domain.teams import own_ball_score, team_playing_handicap


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


def _team_members(teams: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    """Each team id to its two players in player id order, which SeasonFacts has checked."""
    members: dict[str, tuple[str, ...]] = {}
    for player_id, team_id in sorted(teams.items()):
        members[team_id] = (*members.get(team_id, ()), player_id)
    return members


def _team_contest(round_: RoundFacts, basis: Basis, facts: SeasonFacts) -> ContestEntries:
    """What one contest of a team round reads: each team's score on its basis, in team id order."""
    entries = tuple(
        entry
        for team_id, players in sorted(_team_members(facts.teams).items())
        if (entry := _team_entry(round_, team_id, players, basis, facts.seed_index_tenths))
        is not None
    )
    return ContestEntries(round_.tee, round_.closed_at, entries)


def _team_rounds(facts: SeasonFacts) -> tuple[RoundView, ...]:
    """A team season's rounds: field and allplay over the teams' scores, then manual awards.

    SeasonFacts has refused every other contest kind (R15).
    """
    views: list[RoundView] = []
    for round_ in facts.rounds:
        awards: list[Award] = []
        for config in round_.contests:
            if config.kind == "field":
                awards.extend(field_awards(_team_contest(round_, config.basis, facts), config))
            if config.kind == "allplay":
                awards.extend(allplay_awards(_team_contest(round_, config.basis, facts), config))
        round_awards = RoundAwards(round_.number, (*awards, *manual_awards(round_.manual)))
        winners = () if round_.closed_at is None else team_round_winners(round_awards)
        views.append(RoundView(round_awards, winners))
    return tuple(views)


def compute_season(facts: SeasonFacts) -> SeasonView:
    """Every round's awards and winners, the season table and each segment's, from facts alone.

    Tables count closed rounds only (R10), so an open round's awards are in its view and in
    no table. In a team season the teams are the competitors. Raises KeyError where a card it
    reads needs a seed index the facts lack, or for a duel whose key has no pairings, and
    ValueError only as the rule functions raise it.
    """
    if facts.mode == "team":
        rounds = _team_rounds(facts)
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
