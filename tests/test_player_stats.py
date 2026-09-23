from copy import deepcopy
from unittest.mock import Mock

import pandas as pd
import pytest
import requests

from clients import nba_client
from formatters import console_formatter as console
from services.player_service import NBA_STAT_KEYS, map_players_to_stats


def test_stats_request_normalization_filter_and_nulls(monkeypatch):
    rows = [
        {'PLAYER_NAME': 'Nikola Vu\u010devi\u0107', 'TEAM_ABBREVIATION': 'OLD',
         **{key.upper(): 1.2 for key in NBA_STAT_KEYS}, 'FG_PCT': .553, 'STL': 0, 'BLK': float('nan')},
        {'PLAYER_NAME': 'Other Player', 'TEAM_ABBREVIATION': 'BOS',
         **{key.upper(): 2 for key in NBA_STAT_KEYS}},
    ]
    endpoint = Mock()
    endpoint.return_value.get_data_frames.return_value = [pd.DataFrame(rows)]
    monkeypatch.setattr(nba_client.leaguedashplayerstats, 'LeagueDashPlayerStats', endpoint)
    client = nba_client.NBAClient()
    mapping = client.get_player_stats_map('2025-26', ['Vucevic, Nikola'])
    endpoint.assert_called_once_with(season='2025-26', season_type_all_star='Regular Season',
                                     per_mode_detailed='PerGame', timeout=(5, 10))
    assert client.stats_rows_fetched == 2
    assert set(mapping) == {'nikola vucevic'}
    assert mapping['nikola vucevic']['fg_pct'] == .553
    assert mapping['nikola vucevic']['stl'] == 0
    assert mapping['nikola vucevic']['blk'] is None


def test_enrichment_preserves_current_team_and_missing_is_not_zero(capsys):
    players = [{'playerName': 'Claxton, Nicolas', 'nba_team': 'CHI', 'games_this_week': 4,
                'playerId': 'p1', 'adp': 12, 'status': 'RESERVE'},
               {'playerName': 'Rookie', 'nba_team': 'BOS', 'games_this_week': 3}]
    original = deepcopy(players)
    mapping = {'nic claxton': {'nba_team': 'BKN', 'pts': 12.3, 'fg_pct': .65, 'tov': 0}}
    enriched = map_players_to_stats(players, mapping)
    assert players == original
    assert enriched[0]['nba_team'] == 'CHI'
    assert enriched[0]['pts'] == 12.3 and enriched[0]['fg_pct'] == .65
    assert all(enriched[1][key] is None for key in NBA_STAT_KEYS)
    console.print_player_stats('Test', enriched, '2025-26')
    console.print_stats_summary(1, [enriched, []], [])
    output = capsys.readouterr().out
    assert '0.650' in output and 'N/A' in output and '12.3' in output
    assert 'NBA stats not found for player: Rookie' in output


def test_empty_and_malformed_stats(monkeypatch):
    endpoint = Mock()
    monkeypatch.setattr(nba_client.leaguedashplayerstats, 'LeagueDashPlayerStats', endpoint)
    client = nba_client.NBAClient()
    columns = ['PLAYER_NAME', 'TEAM_ABBREVIATION', *(key.upper() for key in NBA_STAT_KEYS)]
    endpoint.return_value.get_data_frames.return_value = [pd.DataFrame(columns=columns)]
    assert client.get_player_stats_map('2026-27') == {}
    assert client.stats_rows_fetched == 0
    endpoint.return_value.get_data_frames.return_value = [pd.DataFrame([{'PLAYER_NAME': 'Bad'}])]
    with pytest.raises(ValueError, match='LeagueDashPlayerStats.*missing required'):
        client.get_player_stats_map('2025-26')
    endpoint.side_effect = requests.Timeout('timeout')
    with pytest.raises(requests.RequestException, match='LeagueDashPlayerStats request failed'):
        client.get_player_stats_map('2025-26')


def test_summary_counts_unnamed_missing_players_without_repeated_warnings(capsys):
    rows = map_players_to_stats([{'playerName': 'Unknown'}, {'playerName': 'Unknown'}], {})
    console.print_stats_summary(0, [], rows)
    output = capsys.readouterr().out
    assert output.count('Warning:') == 1
    assert 'stats unavailable for 2 players' in output
    assert 'Players without stats: 2' in output


def test_available_stats_output_preserves_limit(capsys):
    from services.player_service import get_available_player_rows
    from services.roster_service import map_players_to_weekly_games
    available = [{'playerId': str(i), 'leagueInfo': {'status': 'FA'},
                  'adpInfo': {'name': f'Player {i}', 'ADP': i}} for i in range(30)]
    original = deepcopy(available)
    rows = get_available_player_rows(available)
    rows = map_players_to_weekly_games(rows, {}, {})
    rows = map_players_to_stats(rows, {})
    console.print_player_stats('Waivers', rows[:25], '2025-26')
    output = capsys.readouterr().out
    assert 'Player 24' in output and 'Player 25' not in output
    assert len(rows) == 30 and available == original
