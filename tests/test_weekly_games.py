from unittest.mock import Mock

import pandas as pd
import pytest
import requests

import app
from clients import nba_client
from services.roster_service import map_players_to_weekly_games


def mock_endpoint(monkeypatch, module, name, rows):
    endpoint = Mock()
    endpoint.return_value.get_data_frames.return_value = [pd.DataFrame(rows)]
    monkeypatch.setattr(module, name, endpoint)
    return endpoint


def test_schedule_counts_both_sides_only_selected_week(monkeypatch):
    endpoint = mock_endpoint(monkeypatch, nba_client.scheduleleaguev2, 'ScheduleLeagueV2', [
        {'weekNumber': 1, 'homeTeam_teamTricode': 'PHI', 'awayTeam_teamTricode': 'BOS'},
        {'weekNumber': 1, 'homeTeam_teamTricode': 'DEN', 'awayTeam_teamTricode': 'PHI'},
        {'weekNumber': 2, 'homeTeam_teamTricode': 'DEN', 'awayTeam_teamTricode': 'BOS'},
    ])
    assert nba_client.NBAClient().get_weekly_games_by_team(1) == {'PHI': 2, 'BOS': 1, 'DEN': 1}
    endpoint.assert_called_once_with(season=nba_client.NBA_SEASON, timeout=(5, 10))
    assert nba_client.NBAClient().get_weekly_games_by_team(99) == {}


def test_player_map_skips_missing_teams(monkeypatch):
    endpoint = mock_endpoint(monkeypatch, nba_client.commonallplayers, 'CommonAllPlayers', [
        {'DISPLAY_FIRST_LAST': name, 'TEAM_ABBREVIATION': team}
        for name, team in [('Tyrese Maxey', 'PHI'), ('Empty', ''), ('Null', None),
                           ('Whitespace', ' '), ('NaN', float('nan'))]
    ])
    assert nba_client.NBAClient().get_player_team_map() == {'tyrese maxey': 'PHI'}
    endpoint.assert_called_once_with(
        season=nba_client.NBA_SEASON, is_only_current_season=1, timeout=(5, 10))


def test_player_map_only_retains_requested_players(monkeypatch):
    endpoint = mock_endpoint(monkeypatch, nba_client.commonallplayers, 'CommonAllPlayers', [
        {'DISPLAY_FIRST_LAST': 'Stephen Curry', 'TEAM_ABBREVIATION': 'GSW'},
        {'DISPLAY_FIRST_LAST': 'Nic Claxton', 'TEAM_ABBREVIATION': 'CHI'},
        {'DISPLAY_FIRST_LAST': 'Other Player', 'TEAM_ABBREVIATION': 'BOS'},
    ])
    result = nba_client.NBAClient().get_player_team_map(
        ['Curry, Stephen', 'Claxton, Nicolas', 'Missing Player'])
    assert result == {'stephen curry': 'GSW', 'nic claxton': 'CHI'}
    endpoint.assert_called_once()


def test_empty_player_selection_skips_request(monkeypatch):
    endpoint = mock_endpoint(monkeypatch, nba_client.commonallplayers, 'CommonAllPlayers', [])
    assert nba_client.NBAClient().get_player_team_map([]) == {}
    endpoint.assert_not_called()


def test_nba_name_formats_share_one_key(monkeypatch):
    mock_endpoint(monkeypatch, nba_client.commonallplayers, 'CommonAllPlayers', [{
        'DISPLAY_FIRST_LAST': 'Stephen Curry', 'DISPLAY_LAST_COMMA_FIRST': 'Curry, Stephen',
        'TEAM_ABBREVIATION': 'GSW',
    }])
    mapping = nba_client.NBAClient().get_player_team_map()
    assert mapping == {'stephen curry': 'GSW'}
    rows = map_players_to_weekly_games(
        [{'playerName': '  CURRY,  Stephen '}], mapping, {'GSW': 3})
    assert rows[0]['nba_team'] == 'GSW'
    assert rows[0]['games_this_week'] == 3


@pytest.mark.parametrize('nba_name,fantrax_name,key', [
    ('Kristaps Porzi\u0146\u0123is', 'Porzingis, Kristaps', 'kristaps porzingis'),
    ('Nikola Vu\u010devi\u0107', 'Vucevic, Nikola', 'nikola vucevic'),
    ('Nic Claxton', 'Claxton, Nicolas', 'nic claxton'),
])
def test_normalized_nba_to_roster_matching(monkeypatch, nba_name, fantrax_name, key):
    mock_endpoint(monkeypatch, nba_client.commonallplayers, 'CommonAllPlayers', [{
        'DISPLAY_FIRST_LAST': nba_name, 'TEAM_ABBREVIATION': 'BOS',
    }])
    mapping = nba_client.NBAClient().get_player_team_map()
    assert mapping == {key: 'BOS'}
    players = [{'playerName': fantrax_name, 'playerId': 'p1', 'status': 'RESERVE', 'adp': 12}]
    rows = map_players_to_weekly_games(players, mapping, {'BOS': 4})
    assert rows == [{**players[0], 'nba_team': 'BOS', 'games_this_week': 4}]
    assert 'nba_team' not in players[0]


@pytest.mark.parametrize('method,module,name,args', [
    ('get_weekly_games_by_team', nba_client.scheduleleaguev2, 'ScheduleLeagueV2', (1,)),
    ('get_player_team_map', nba_client.commonallplayers, 'CommonAllPlayers', ()),
])
def test_api_failures_and_malformed_data(monkeypatch, method, module, name, args):
    endpoint = mock_endpoint(monkeypatch, module, name, [{'unexpected': 1}])
    with pytest.raises(ValueError, match=name):
        getattr(nba_client.NBAClient(), method)(*args)
    endpoint.side_effect = requests.Timeout('timeout')
    with pytest.raises(requests.RequestException, match=name):
        getattr(nba_client.NBAClient(), method)(*args)


def test_mapping_preserves_rows_and_distinguishes_unknown_from_zero():
    players = [{'playerName': 'Tyrese Maxey', 'status': 'RESERVE'},
               {'playerName': 'Unknown Name'}, {'playerName': 'Nikola Jokic'}]
    result = map_players_to_weekly_games(
        players, {'tyrese maxey': 'PHI', 'nikola jokic': 'DEN'}, {'PHI': 4})
    assert [(p['nba_team'], p['games_this_week']) for p in result] == [
        ('PHI', 4), (None, 0), ('DEN', 0)]
    assert result[0]['status'] == 'RESERVE'
    assert all('nba_team' not in p for p in players)


@pytest.mark.parametrize('my_side', ['home', 'away'])
def test_run_reuses_datasets_for_both_rosters(monkeypatch, capsys, my_side):
    fantrax = Mock()
    fantrax.get_league_info.return_value = {'playerInfo': {
        'fa1': {'name': 'Available Player', 'status': 'FA'},
        'other': {'name': 'Other Roster Player', 'status': 'T'},
    }}
    fantrax.get_adp.return_value = []
    fantrax.get_team_rosters.return_value = {'rosters': {
        'mine': {'players': [{'name': 'Tyrese Maxey'}, {'name': 'Missing Name'}]},
        'theirs': {'players': [{'player': {'name': 'Nikola Jokic'}}]},
    }}
    other_side = 'away' if my_side == 'home' else 'home'
    fantrax.get_matchup_scores.return_value = {'period': 7, 'matchups': [{
        my_side: {'teamId': 'mine', 'teamName': 'My Team'},
        other_side: {'teamId': 'theirs', 'teamName': 'Opponent'},
        'categories': [{'shortName': 'PTS', 'home': {'value': 20}, 'away': {'value': 10}}],
    }]}
    nba = Mock()
    nba.get_weekly_games_by_team.return_value = {'PHI': 4, 'DEN': 3}
    nba.get_player_team_map.return_value = {'tyrese maxey': 'PHI', 'nikola jokic': 'DEN'}
    nba.get_player_stats_map.return_value = {
        'tyrese maxey': {'pts': 20.1}, 'nikola jokic': {'pts': 25.2},
        'available player': {'pts': 10.3},
    }
    nba.stats_rows_fetched = 3
    monkeypatch.setattr(app.schedule_service, 'MANUAL_START_DATE', None)
    monkeypatch.setattr(app.schedule_service, 'MANUAL_END_DATE', None)
    app.FantraxApp(my_team_id='mine', fantrax_client=fantrax, nba_client=nba).run()
    output = capsys.readouterr().out
    assert 'Total Player Games: 4' in output
    assert 'Total Player Games: 3' in output
    assert 'UNKNOWN' in output
    assert 'NBA team not found for player: Missing Name' in output
    assert 'Unmatched players: 1' in output
    assert 'Category Scores' in output and 'PTS' in output
    assert 'TOP 25 AVAILABLE PLAYERS BY FANTRAX ADP' in output
    nba.get_weekly_games_by_team.assert_called_once_with(app.NBA_WEEK)
    nba.get_player_team_map.assert_called_once_with(
        {'Tyrese Maxey', 'Missing Name', 'Nikola Jokic', 'Available Player'})
    nba.get_player_stats_map.assert_called_once_with(
        app.NBA_STATS_SEASON, {'Tyrese Maxey', 'Missing Name', 'Nikola Jokic', 'Available Player'})
    assert '20.1' in output and '25.2' in output and '10.3' in output
    assert 'Players with stats: 3' in output
    assert 'Players without stats: 1' in output
    assert 'NBA stats not found for player: Missing Name' in output
    nba.get_nba_games_by_team.assert_not_called()
