"""Deterministic seven-category matchup calculations. No I/O or API calls."""

from datetime import date, datetime
from math import isfinite

DSS_CATEGORIES = ('pts', 'reb', 'ast', 'stl', 'blk', 'fg3m', 'tov')
CATEGORY_LABELS = dict(zip(DSS_CATEGORIES, ('PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'TO')))
SAFE_AHEAD_THRESHOLD = 0.10
CLOSE_THRESHOLD = 0.05
CATEGORY_NEED_WEIGHTS = {
    'SAFE_AHEAD': 0.25, 'CLOSE_AHEAD': 2.0, 'CLOSE_BEHIND': 3.0, 'FAR_BEHIND': 0.75,
}
TRANSITION_BONUSES = {
    ('FAR_BEHIND', 'CLOSE_BEHIND'): 1.0,
    ('FAR_BEHIND', 'CLOSE_AHEAD'): 3.0,
    ('FAR_BEHIND', 'SAFE_AHEAD'): 4.0,
    ('CLOSE_BEHIND', 'CLOSE_AHEAD'): 3.0,
    ('CLOSE_BEHIND', 'SAFE_AHEAD'): 4.0,
    ('CLOSE_AHEAD', 'SAFE_AHEAD'): 1.5,
}
TRANSITION_PENALTIES = {
    ('SAFE_AHEAD', 'CLOSE_AHEAD'): -1.0,
    ('CLOSE_AHEAD', 'CLOSE_BEHIND'): -3.0,
    ('CLOSE_AHEAD', 'FAR_BEHIND'): -4.0,
    ('SAFE_AHEAD', 'CLOSE_BEHIND'): -4.0,
    ('SAFE_AHEAD', 'FAR_BEHIND'): -5.0,
}
WAIVER_CANDIDATE_COUNT = 25
DROP_CANDIDATE_COUNT = 5
PROTECTED_ADP_THRESHOLD = 50
TOP_MOVE_COUNT = 10
TOP_MOVE_DETAIL_COUNT = 3
SAME_DAY_MOVES_COUNT = True


def number(value):
    """Return a finite numeric value, preserving missing/invalid values as None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value.replace(',', '') if isinstance(value, str) else value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def normalize_current_score(matchup, my_side, opponent_side):
    """Prefer raw totals. Empty categories mean zero only with explicit zero games played."""
    aliases = {'PTS': 'pts', 'REB': 'reb', 'AST': 'ast', 'ST': 'stl', 'STL': 'stl',
               'BLK': 'blk', '3PTM': 'fg3m', '3PM': 'fg3m', 'FG3M': 'fg3m',
               'TO': 'tov', 'TOV': 'tov'}
    score = {}
    for category in matchup.get('categories', []):
        key = aliases.get(str(category.get('shortName', '')).upper())
        if key is None:
            continue
        values = {}
        for output_side, input_side in [('me', my_side), ('opp', opponent_side)]:
            raw = category.get(input_side) or {}
            value = number(raw.get('value'))
            if value is None:
                value = number(raw.get('formattedValue'))
            if value is None and not raw and number(matchup[input_side].get('gamesPlayed')) == 0:
                value = 0.0
            if value is None or value < 0:
                raise ValueError(f'Current {CATEGORY_LABELS[key]} score is unavailable for {output_side}.')
            values[output_side] = value
        score[key] = values
    missing = set(DSS_CATEGORIES) - score.keys()
    if missing:
        raise ValueError('Current matchup is missing categories: ' + ', '.join(sorted(missing)))
    return score


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(value).date()


def project_player_remaining(player, as_of=None, week_end=None):
    """Copy a player, retaining missing stats and explaining projection eligibility."""
    today = as_of if as_of is not None else date.today()
    if player.get('remaining_game_dates') is not None:
        dates = sorted(_as_date(value).isoformat() for value in player['remaining_game_dates']
                       if _as_date(value) >= today and
                       (week_end is None or _as_date(value) <= _as_date(week_end)))
        games = len(dates)
    else:
        dates = None
        games = number(player.get('games_remaining', player.get('games_this_week', 0)))
    stats = {key: number(player.get(key)) for key in DSS_CATEGORIES}
    missing = [key for key, value in stats.items() if value is None or value < 0]
    reasons = []
    if missing:
        reasons.append('missing/invalid stats: ' + ', '.join(missing))
    if not player.get('nba_team') or player.get('nba_team') == 'UNKNOWN':
        reasons.append('missing NBA mapping')
    if games is None or games < 0 or not float(games).is_integer():
        reasons.append('invalid remaining games')
    valid = not reasons
    return {**player, 'games_remaining': games, 'remaining_game_dates': dates,
            'projection_valid': valid,
            'dss_eligible': valid and games > 0,
            'missing_stats': missing, 'exclusion_reasons': reasons,
            **{f'projected_{key}': stats[key] * games if valid else None for key in DSS_CATEGORIES}}


def calculate_team_remaining_projection(players):
    """Sum complete projections only; build_dss_report also reports omitted players."""
    totals = dict.fromkeys(DSS_CATEGORIES, 0.0)
    for player in players:
        projected = project_player_remaining(player)
        if projected['projection_valid']:
            for key in DSS_CATEGORIES:
                totals[key] += projected[f'projected_{key}']
    return totals


def classify_category(relative_gap):
    if relative_gap >= SAFE_AHEAD_THRESHOLD:
        return 'SAFE_AHEAD'
    if relative_gap >= 0:
        return 'CLOSE_AHEAD'
    if relative_gap >= -CLOSE_THRESHOLD:
        return 'CLOSE_BEHIND'
    return 'FAR_BEHIND'


def calculate_projected_final(current_score, my_remaining_projection, opponent_remaining_projection):
    result = {}
    for key in DSS_CATEGORIES:
        current_me = number(current_score.get(key, {}).get('me'))
        current_opp = number(current_score.get(key, {}).get('opp'))
        if current_me is None or current_opp is None or min(current_me, current_opp) < 0:
            raise ValueError(f'Current {CATEGORY_LABELS[key]} score is unavailable.')
        me = current_me + my_remaining_projection[key]
        opp = current_opp + opponent_remaining_projection[key]
        gap = opp - me if key == 'tov' else me - opp
        relative_gap = gap / max(abs(opp), 1)
        result[key] = {'current_me': current_me, 'current_opp': current_opp,
                       'remaining_me': my_remaining_projection[key],
                       'remaining_opp': opponent_remaining_projection[key],
                       'me': me, 'opp': opp, 'gap': gap, 'relative_gap': relative_gap,
                       'status': classify_category(relative_gap)}
    return result


def calculate_category_record(outlook):
    gaps = [outlook[key]['gap'] for key in DSS_CATEGORIES]
    return {'wins': sum(g > 0 for g in gaps), 'losses': sum(g < 0 for g in gaps),
            'ties': sum(g == 0 for g in gaps)}


def get_usable_game_dates(player, move_date):
    """Return eligible calendar dates, assuming a move is effective on its move date."""
    move = _as_date(move_date)
    dates = player.get('remaining_game_dates')
    if dates is None:
        return []
    return sorted(_as_date(value).isoformat() for value in dates
                  if (_as_date(value) >= move if SAME_DAY_MOVES_COUNT else
                      _as_date(value) > move))


def simulate_move(current_score, my_projection, opponent_projection, add_player, drop_player,
                  move_date=None):
    add = project_player_remaining(add_player)
    drop = project_player_remaining(drop_player)
    if not add['dss_eligible'] or not drop['projection_valid']:
        raise ValueError('Cannot simulate a move with missing player data or no add games remaining.')
    move = _as_date(move_date) if move_date is not None else date.today()
    add_dates = get_usable_game_dates(add, move)
    drop_dates = get_usable_game_dates(drop, move)
    add_games = (int(add['games_remaining']) if add['remaining_game_dates'] is None
                 else len(add_dates))
    drop_games = (int(drop['games_remaining']) if drop['remaining_game_dates'] is None
                  else len(drop_dates))
    net = {key: add[key] * add_games - drop[key] * drop_games
           for key in DSS_CATEGORIES}
    after_projection = {key: my_projection[key] + net[key] for key in DSS_CATEGORIES}
    before = calculate_projected_final(current_score, my_projection, opponent_projection)
    after = calculate_projected_final(current_score, after_projection, opponent_projection)
    effects, transitions = {}, {}
    score = 0.0
    for key in DSS_CATEGORIES:
        change = after[key]['gap'] - before[key]['gap']
        transition = (before[key]['status'], after[key]['status'])
        weighted = change / max(abs(before[key]['opp']), 1) * CATEGORY_NEED_WEIGHTS[transition[0]]
        bonus = TRANSITION_BONUSES.get(transition, 0) + TRANSITION_PENALTIES.get(transition, 0)
        # An exact tie shares CLOSE_AHEAD status, but is not a projected win.
        if before[key]['gap'] > 0 and after[key]['gap'] == 0:
            bonus -= 1.0
        score += weighted + bonus
        effects[key] = {'before_gap': before[key]['gap'], 'after_gap': after[key]['gap'],
                        'gap_change': change, 'weighted_improvement': weighted,
                        'transition_adjustment': bonus}
        if transition[0] != transition[1]:
            transitions[key] = transition
    return {'add_player': add, 'drop_player': drop, 'move_date': move.isoformat(),
            'add_usable_game_dates': add_dates, 'drop_lost_game_dates': drop_dates,
            'add_usable_games': add_games, 'drop_lost_games': drop_games,
            'net_games': add_games - drop_games, 'net_production': net,
            'effects': effects, 'transitions': transitions, 'after_outlook': after,
            'before_gaps': {key: row['gap'] for key, row in before.items()},
            'after_gaps': {key: row['gap'] for key, row in after.items()},
            'status_changes': transitions,
            'before_record': calculate_category_record(before),
            'after_record': calculate_category_record(after), 'impact_score': score}


def identity(player):
    return str(player.get('playerId') or player.get('playerName', '')).casefold()


def adp_key(player):
    return number(player.get('adp')) if number(player.get('adp')) is not None else float('inf')


def candidate_move_dates(add_player, drop_player, as_of=None, week_end=None):
    """Generate dates where either candidate's usable game set can change."""
    today = as_of if as_of is not None else date.today()
    end = _as_date(week_end) if week_end is not None else None
    dates = set()
    for player in (add_player, drop_player):
        player_dates = player.get('remaining_game_dates')
        if player_dates is not None:
            dates.update(_as_date(value) for value in player_dates
                         if _as_date(value) >= today and
                         (end is None or _as_date(value) <= end))
    if any(today in {_as_date(value) for value in player['remaining_game_dates']}
           for player in (add_player, drop_player)
           if player.get('remaining_game_dates') is not None):
        dates.add(today)
    if not dates and all(player.get('remaining_game_dates') is None
                         for player in (add_player, drop_player)):
        dates.add(today)
    return sorted(dates)


def rank_moves(current_score, my_projection, opponent_projection, waivers, drops,
               as_of=None, week_end=None):
    moves = []
    for add in waivers:
        for drop in drops:
            if identity(add) == identity(drop):
                continue
            date_moves = [simulate_move(current_score, my_projection, opponent_projection,
                                        add, drop, move_date)
                          for move_date in candidate_move_dates(add, drop, as_of, week_end)]
            if date_moves:
                moves.append(sorted(date_moves, key=lambda move: (
                    -move['impact_score'], move['move_date']))[0])
    return sorted(moves, key=lambda m: (-m['impact_score'], m['move_date'],
                                        identity(m['add_player']),
                                        identity(m['drop_player'])))


def build_dss_report(current_score, my_players, opponent_players, waiver_players,
                     as_of=None, week_end=None):
    """Evaluate the first 25 ADP-ordered waivers against five unprotected low-value drops."""
    mine = [project_player_remaining(p, as_of, week_end) for p in my_players]
    opponent = [project_player_remaining(p, as_of, week_end) for p in opponent_players]
    # Limit the inspected pool first, so unavailable top-25 players are visible in the summary.
    waiver_pool = [project_player_remaining(p, as_of, week_end)
                   for p in sorted(waiver_players, key=adp_key)
                   [:WAIVER_CANDIDATE_COUNT]]
    roster_ids = {identity(p) for p in [*mine, *opponent]}
    waivers = []
    for player in waiver_pool:
        if player['dss_eligible'] and identity(player) not in roster_ids:
            waivers.append(player)
            roster_ids.add(identity(player))
    my_projection = calculate_team_remaining_projection(mine)
    opp_projection = calculate_team_remaining_projection(opponent)
    outlook = calculate_projected_final(current_score, my_projection, opp_projection)

    def remaining_value(player):
        return sum(((-1 if key == 'tov' else 1) * player[f'projected_{key}'] /
                    max(abs(outlook[key]['opp']), 1)) for key in DSS_CATEGORIES)

    drops = sorted((p for p in mine if p['projection_valid'] and
                    adp_key(p) > PROTECTED_ADP_THRESHOLD),
                   key=lambda p: (remaining_value(p), identity(p)))[:DROP_CANDIDATE_COUNT]
    skipped = [{'group': group, 'playerName': p.get('playerName', 'Unknown'),
                'reasons': p['exclusion_reasons'] or ['no remaining games']}
               for group, players in [('my roster', mine), ('opponent', opponent), ('waiver', waiver_pool)]
               for p in players if not p['projection_valid'] or (group == 'waiver' and not p['dss_eligible'])]
    priorities = sorted(DSS_CATEGORIES,
                        key=lambda k: (-CATEGORY_NEED_WEIGHTS[outlook[k]['status']],
                                       abs(outlook[k]['relative_gap']), DSS_CATEGORIES.index(k)))
    moves = rank_moves(current_score, my_projection, opp_projection, waivers, drops,
                       as_of, week_end)
    return {'outlook': outlook, 'record': calculate_category_record(outlook),
            'priorities': priorities, 'moves': moves, 'skipped': skipped,
            'partial_projection': any(not p['projection_valid'] for p in [*mine, *opponent]),
            'summary': {'My roster players': len(mine), 'Opponent players': len(opponent),
                        'Waiver pool inspected': len(waiver_pool), 'Waiver candidates': len(waivers),
                        'Drop candidates': len(drops), 'Add/drop combinations evaluated': len(moves),
                        'Players skipped for missing stats': sum(bool(p['missing_stats'])
                                                                 for p in [*mine, *opponent, *waiver_pool])}}
