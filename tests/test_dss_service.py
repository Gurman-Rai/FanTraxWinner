from copy import deepcopy
from datetime import date

import pytest

from services import dss_service as dss
from formatters.dss_formatter import print_dss_report
from run_dss_sanity import fake_data


def test_player_projection_and_games_precedence():
    _, mine, _, _ = fake_data()
    result = dss.project_player_remaining({**mine[0], 'games_this_week': 9})
    assert result['projected_pts'] == 50
    assert result['projected_blk'] == 1
    assert result['projected_tov'] == 4
    player = dict(mine[0])
    del player['games_remaining']
    assert dss.project_player_remaining({**player, 'games_this_week': 3})['projected_pts'] == 75
    assert dss.project_player_remaining({**player, 'games_remaining': 0})['projected_pts'] == 0


def test_aggregation_final_and_actual_score():
    score, mine, opponent, _ = fake_data()
    projected = dss.calculate_team_remaining_projection(mine)
    assert projected == dict(pts=60, reb=14, ast=14, stl=2.5, blk=1.2, fg3m=7, tov=5)
    final = dss.calculate_projected_final(score, projected, dss.calculate_team_remaining_projection(opponent))
    assert final['pts']['me'] == 460
    assert final['pts']['opp'] == 390
    assert final['tov']['gap'] == 2  # 52 opponent turnovers minus our 50
    assert dss.calculate_category_record(final) == dict(wins=5, losses=2, ties=0)


@pytest.mark.parametrize('gap,expected', [
    (0.10, 'SAFE_AHEAD'), (0.099, 'CLOSE_AHEAD'), (0, 'CLOSE_AHEAD'),
    (-0.05, 'CLOSE_BEHIND'), (-0.051, 'FAR_BEHIND'),
])
def test_category_classification_boundaries(gap, expected):
    assert dss.classify_category(gap) == expected


def test_exact_ties_and_zero_denominator():
    zero = dict.fromkeys(dss.DSS_CATEGORIES, 0)
    score = {key: dict(me=0, opp=0) for key in dss.DSS_CATEGORIES}
    final = dss.calculate_projected_final(score, zero, zero)
    assert dss.calculate_category_record(final) == dict(wins=0, losses=0, ties=7)
    assert final['pts']['relative_gap'] == 0


def test_sanity_ranking_simulation_and_no_mutation():
    inputs = fake_data()
    original = deepcopy(inputs)
    report = dss.build_dss_report(*inputs)
    assert inputs == original
    best, other = report['moves']
    assert best['add_player']['playerName'] == 'Rebound Block Waiver'
    assert best['drop_player']['playerName'] == 'My Streamer'
    assert best['impact_score'] > other['impact_score']
    assert best['net_production']['reb'] == 26
    assert best['effects']['reb']['before_gap'] == -12
    assert best['effects']['reb']['after_gap'] == 14
    assert best['net_production']['tov'] == 2
    assert best['effects']['tov']['gap_change'] == -2
    assert best['after_record'] == dict(wins=6, losses=0, ties=1)
    assert best['transitions']['blk'] == ('FAR_BEHIND', 'SAFE_AHEAD')
    assert report == dss.build_dss_report(*inputs)


@pytest.mark.parametrize('missing', [None, float('nan'), float('inf'), 'N/A', -1])
def test_missing_stats_excluded_not_replaced_by_zero(missing):
    score, mine, opponent, waivers = fake_data()
    waivers[0]['reb'] = missing
    report = dss.build_dss_report(score, mine, opponent, waivers)
    assert len(report['moves']) == 1
    assert report['moves'][0]['add_player']['playerName'] == 'Scoring Guard Waiver'
    assert report['summary']['Players skipped for missing stats'] == 1
    projected = dss.project_player_remaining(waivers[0])
    assert projected['projected_reb'] is None
    assert not projected['dss_eligible']


def test_partial_roster_is_reported_and_not_droppable():
    score, mine, opponent, waivers = fake_data()
    mine[1]['ast'] = None
    report = dss.build_dss_report(score, mine, opponent, waivers)
    assert report['partial_projection']
    assert report['summary']['Drop candidates'] == 0
    assert report['moves'] == []
    assert report['outlook']['pts']['remaining_me'] == 50


def test_protection_limits_mapping_and_zero_games(monkeypatch):
    score, mine, opponent, waivers = fake_data()
    mine[1]['adp'] = 50
    assert not dss.build_dss_report(score, mine, opponent, waivers)['moves']
    mine[1]['adp'] = 51
    mine[1]['games_remaining'] = 0
    waivers[0]['nba_team'] = None
    waivers[1]['games_remaining'] = 0
    report = dss.build_dss_report(score, mine, opponent, waivers)
    assert report['summary']['Drop candidates'] == 1
    assert report['summary']['Waiver candidates'] == 0
    _, _, _, waivers = fake_data()
    monkeypatch.setattr(dss, 'WAIVER_CANDIDATE_COUNT', 1)
    report = dss.build_dss_report(score, mine, opponent, waivers)
    assert report['summary']['Waiver pool inspected'] == 1
    assert report['moves'][0]['add_player']['playerName'] == 'Scoring Guard Waiver'


def test_damaging_winning_category_is_penalized():
    score, mine, opponent, waivers = fake_data()
    move = dss.build_dss_report(score, mine, opponent, waivers)['moves'][1]
    assert move['effects']['tov']['gap_change'] < 0
    assert move['effects']['tov']['transition_adjustment'] < 0


@pytest.mark.parametrize('my_side', ['home', 'away'])
def test_normalize_actual_scores_raw_first_and_aliases(my_side):
    other = 'away' if my_side == 'home' else 'home'
    matchup = {'home': {'gamesPlayed': 5}, 'away': {'gamesPlayed': 5}, 'categories': [
        {'shortName': label, my_side: {'value': 12, 'formattedValue': '999'},
         other: {'formattedValue': '1,234'}}
        for label in ['PTS', 'REB', 'AST', 'ST', 'BLK', '3PTM', 'TO']]}
    score = dss.normalize_current_score(matchup, my_side, other)
    assert score == {key: dict(me=12, opp=1234) for key in dss.DSS_CATEGORIES}
    matchup['categories'][0][my_side] = {}
    with pytest.raises(ValueError, match='unavailable'):
        dss.normalize_current_score(matchup, my_side, other)
    matchup[my_side]['gamesPlayed'] = 0
    assert dss.normalize_current_score(matchup, my_side, other)['pts']['me'] == 0


def test_missing_score_never_silently_projects_from_zero():
    score, mine, opponent, waivers = fake_data()
    del score['pts']
    with pytest.raises(ValueError, match='Current PTS'):
        dss.build_dss_report(score, mine, opponent, waivers)
    with pytest.raises(ValueError, match='missing categories'):
        dss.normalize_current_score({'categories': []}, 'home', 'away')


def test_console_report(capsys):
    print_dss_report(dss.build_dss_report(*fake_data()))
    output = capsys.readouterr().out
    for expected in ['DSS INPUT SUMMARY', 'LIVE MATCHUP OUTLOOK', 'TOP STREAMING MOVES',
                     'MOVE #1 DETAILS', 'MATCHUP IMPACT SCORE', 'Rebound Block Waiver',
                     'MAKE MOVE:', 'ADD PLAYER USABLE GAMES', 'NET GAMES:',
                     'calendar-date based', '5-2-0 -> 6-0-1', 'STATUS CHANGES',
                     'Category record improves: YES']:
        assert expected in output


def streaming_scenario():
    score = {key: {'me': mine, 'opp': opponent} for key, mine, opponent in [
        ('pts', 440, 380), ('reb', 122, 128), ('ast', 90, 91),
        ('stl', 25, 23), ('blk', 16, 17), ('fg3m', 55, 44), ('tov', 45, 48)]}
    mine = [dict(playerName='One Game Guard', nba_team='BBB',
                 remaining_game_dates=['2026-10-25'], pts=12, reb=3, ast=4,
                 stl=0.5, blk=0.1, fg3m=2, tov=1.5, adp=180)]
    opponent = []
    waivers = [
        dict(playerName='Three Game Big', nba_team='DDD',
             remaining_game_dates=['2026-10-23', '2026-10-24', '2026-10-25'],
             pts=10, reb=9, ast=1, stl=0.8, blk=1.8, fg3m=0, tov=1, adp=160),
        dict(playerName='Sunday Scorer', nba_team='EEE',
             remaining_game_dates=['2026-10-25'], pts=24, reb=2, ast=5,
             stl=0.5, blk=0, fg3m=4, tov=3, adp=140),
    ]
    return score, mine, opponent, waivers


def test_streaming_optimizes_actual_move_date_and_preserves_inputs(capsys):
    inputs = streaming_scenario()
    original = deepcopy(inputs)
    score, mine, opponent, waivers = inputs
    report = dss.build_dss_report(
        score, mine, opponent, waivers, as_of=date(2026, 10, 22),
        week_end='2026-10-25T23:59:59.0-0400')
    best = report['moves'][0]
    assert best['add_player']['playerName'] == 'Three Game Big'
    assert best['drop_player']['playerName'] == 'One Game Guard'
    assert best['move_date'] == '2026-10-23'
    assert best['add_usable_games'] == 3
    assert best['drop_lost_games'] == 1
    assert best['net_games'] == 2
    assert best['add_usable_game_dates'] == ['2026-10-23', '2026-10-24', '2026-10-25']
    assert best['drop_lost_game_dates'] == ['2026-10-25']
    assert best['effects']['reb']['gap_change'] > 0
    assert best['effects']['blk']['gap_change'] > 0
    print_dss_report(report)
    output = capsys.readouterr().out
    assert 'Three Game Big' in output
    assert '2026-10-23' in output
    assert 'ADD PLAYER USABLE GAMES (3): 2026-10-23, 2026-10-24, 2026-10-25' in output
    assert 'DROP PLAYER LOST GAMES (1): 2026-10-25' in output
    assert inputs == original


def test_later_add_date_reduces_games_and_does_not_remove_prior_drop_games():
    _, mine, _, waivers = streaming_scenario()
    drop = {**mine[0], 'remaining_game_dates': ['2026-10-22', '2026-10-25']}
    add = waivers[0]
    assert dss.get_usable_game_dates(add, '2026-10-24') == ['2026-10-24', '2026-10-25']
    baseline = dss.calculate_team_remaining_projection([drop])
    zero = dict.fromkeys(dss.DSS_CATEGORIES, 0.0)
    earlier = dss.simulate_move(
        streaming_scenario()[0], baseline, zero, add, drop, '2026-10-23')
    later = dss.simulate_move(
        streaming_scenario()[0], baseline, zero, add, drop, '2026-10-24')
    assert earlier['add_usable_games'] == 3
    assert later['add_usable_games'] == 2
    assert earlier['drop_lost_game_dates'] == ['2026-10-25']
    assert later['drop_lost_game_dates'] == ['2026-10-25']
    assert later['impact_score'] <= earlier['impact_score']
