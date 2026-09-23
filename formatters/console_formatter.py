from services.matchup_service import iter_category_scores
from services.roster_service import extract_roster_players, get_roster_rows
from services.player_service import NBA_STAT_KEYS, get_available_player_details


def print_progress(message):
    """Show the active step immediately, even when output is buffered."""
    print(message, flush=True)


def print_week_dates(current_period, start_date, end_date):
    """Print the current fantasy week dates."""
    print('\n')
    print('=' * 65)
    print('FANTASY WEEK DATES')
    print('=' * 65)
    print(f'Scoring Period: {current_period}')
    print(f'Start Date:     {start_date}')
    print(f'End Date:       {end_date}')
    print('=' * 65)


def print_schedule_loading():
    """Print the existing NBA request message."""
    print('\nPulling NBA played-game records...', flush=True)


def print_future_game_logs():
    """Explain why a future range does not need a played-game lookup."""
    print('\nNBA lookup skipped: this date range is in the future. '
          'LeagueGameLog contains played games, not upcoming fixtures.', flush=True)


def print_nba_games(nba_games_by_team):
    """Print the NBA game counts in the original order."""
    print('\n')
    print('=' * 65)
    print('NBA GAMES DURING FANTASY WEEK')
    print('=' * 65)
    if not nba_games_by_team:
        print('No NBA games returned for this date range.')
    else:
        for team, games in sorted(nba_games_by_team.items()):
            print(f'{team:<5}{games}')
    print('=' * 65)


def print_missing_matchup():
    """Print the existing missing-matchup message."""
    print("Could not find Gurmanrai's matchup.")


def print_matchup_summary(my_matchup, my_team, opponent, my_side, opponent_side, current_period):
    """Print teams, records, games played and category scores."""
    print('\n')
    print('=' * 65)
    print('FANTRAX MATCHUP SUMMARY')
    print('=' * 65)
    print(f'\nPeriod: {current_period}')
    print('\nTeams')
    print('-' * 65)
    print(f"My Team:   {my_team['teamName']} ({my_team['teamId']})")
    print(f"Opponent:  {opponent['teamName']} ({opponent['teamId']})")
    print('\nCurrent Category Record')
    print('-' * 65)
    print(f"{my_team['teamName']}: {int(my_team.get('categoryWins', 0))}-{int(my_team.get('categoryLosses', 0))}-{int(my_team.get('categoryTies', 0))}")
    print(f"{opponent['teamName']}: {int(opponent.get('categoryWins', 0))}-{int(opponent.get('categoryLosses', 0))}-{int(opponent.get('categoryTies', 0))}")
    print('\nGames Played')
    print('-' * 65)
    print(f"{my_team['teamName']}: {my_team.get('gamesPlayed', 0)}")
    print(f"{opponent['teamName']}: {opponent.get('gamesPlayed', 0)}")
    print('\nCategory Scores')
    print('-' * 65)
    print(f"{'CAT':<10}{my_team['teamName']:<25}{opponent['teamName']:<25}")
    print('-' * 65)
    for category_name, my_value, opponent_value in iter_category_scores(my_matchup, my_side, opponent_side):
        print(f'{category_name:<10}{str(my_value):<25}{str(opponent_value):<25}')
    print('\n')
    print('=' * 65)
    print('SUMMARY')
    print('=' * 65)
    print(f"{my_team['teamName']} vs {opponent['teamName']}")
    print(f'Scoring Period: {current_period}')
    print('=' * 65)


def print_team_roster(team_name, team_id, rosters_data, league_data, adp_lookup):
    """Print one roster using the existing player fallbacks and sort."""
    roster_players = extract_roster_players(rosters_data, team_id)
    print('\n')
    print('=' * 95)
    print(f'{team_name.upper()} ROSTER')
    print('=' * 95)
    print(f"{'#':<4}{'PLAYER':<32}{'POSITION':<22}{'STATUS':<15}{'ADP':<10}{'FANTRAX ID':<18}")
    print('-' * 95)
    if not roster_players:
        print(f'No roster players found for {team_name}.')
        print('-' * 95)
        return
    formatted_players = get_roster_rows(roster_players, league_data, adp_lookup)
    for index, player in enumerate(formatted_players, start=1):
        adp = player['adp']
        if adp == float('inf'):
            adp_display = 'N/A'
        else:
            adp_display = f'{adp:.1f}'
        print(f"{index:<4}{player['playerName']:<32}{player['positions']:<22}{str(player['status']):<15}{adp_display:<10}{player['playerId']:<18}")
    print('-' * 95)


def print_weekly_matchup(season, week_number, my_name, opponent_name,
                         my_players, opponent_players, games_by_team, player_team_map):
    """Show scheduled player-games and visible name-match failures."""
    print('\n' + '=' * 65)
    print(f'FANTASY MATCHUP - NBA WEEK {week_number} ({season})')
    print('=' * 65)
    if not games_by_team:
        print('Warning: no NBA schedule games returned for the selected season/week.')
    if not player_team_map:
        print('Warning: no NBA players mapped to teams for the selected season.')
    unmatched = []
    for name, players in ((my_name, my_players), (opponent_name, opponent_players)):
        print(f'\n{name}')
        print('-' * 65)
        print(f"{'PLAYER':<32}{'NBA TEAM':<15}{'GAMES':>6}")
        print('-' * 65)
        if not players:
            print(f'No roster players found for {name}.')
        for player in players:
            print(f"{player['playerName']:<32}{player['nba_team'] or 'UNKNOWN':<15}"
                  f"{player['games_this_week']:>6}")
            if player['nba_team'] is None:
                unmatched.append(player['playerName'])
        print(f"\nTotal Player Games: {sum(p['games_this_week'] for p in players)}")
    for name in unmatched:
        print(f'Warning: NBA team not found for player: {name}')
    # Keep the diagnostic summary together so it is easy to remove later.
    print(f'\nNBA teams with schedule data: {len(games_by_team)}')
    print(f'NBA normalized player names mapped to teams: {len(player_team_map)}')
    print(f'My roster players: {len(my_players)}')
    print(f'Opponent roster players: {len(opponent_players)}')
    print(f'Unmatched players: {len(unmatched)}')


def print_available_players(available_players):
    """Print the same top 25 free agents."""
    print('\n')
    print('=' * 88)
    print('TOP 25 AVAILABLE PLAYERS BY FANTRAX ADP')
    print('=' * 88)
    print(f"{'#':<4}{'PLAYER':<32}{'POSITION':<22}{'ADP':<12}{'FANTRAX ID':<18}")
    print('-' * 88)
    for index, player in enumerate(available_players[:25], start=1):
        player_id, player_name, positions, adp = get_available_player_details(player)
        if adp == float('inf'):
            adp_display = 'N/A'
        else:
            adp_display = f'{adp:.1f}'
        print(f'{index:<4}{player_name:<32}{positions:<22}{adp_display:<12}{player_id:<18}')
    print('-' * 88)


def print_player_stats(title, players, season):
    """Display unscaled season averages alongside current teams and weekly games."""
    print('\n' + '=' * 115)
    print(f'{title} - {season} REGULAR SEASON AVERAGES (PER GAME)')
    print('-' * 115)
    labels = ('PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG%', 'FT%', 'TO')
    print(f"{'PLAYER':<32}{'TEAM':<8}{'GAMES':>6}" + ''.join(f'{label:>7}' for label in labels))
    print('-' * 115)
    for player in players:
        values = []
        for key in NBA_STAT_KEYS:
            value = player.get(key)
            values.append('N/A' if value is None else
                          f'{value:.3f}' if key in ('fg_pct', 'ft_pct') else f'{value:.1f}')
        print(f"{player['playerName']:<32}{player['nba_team'] or 'UNKNOWN':<8}"
              f"{player['games_this_week']:>6}" + ''.join(f'{value:>7}' for value in values))
    if not players:
        print('No players found.')


def print_stats_summary(rows_fetched, rosters, available_players):
    """Keep all missing-stat warnings and temporary diagnostics together."""
    players = [player for group in [*rosters, available_players] for player in group]
    missing = [player for player in players if all(player[key] is None for key in NBA_STAT_KEYS)]
    unnamed = 0
    for player in missing:
        if player['playerName'] == 'Unknown':
            unnamed += 1
            continue
        print(f"Warning: NBA stats not found for player: {player['playerName']}")
    if unnamed:
        print(f'Warning: NBA stats unavailable for {unnamed} players whose Fantrax name '
              'could not be resolved (Unknown). Rows retained with N/A stats.')
    print(f'\nNBA stats rows fetched: {rows_fetched}')
    print(f'My roster players: {len(rosters[0]) if rosters else 0}')
    print(f'Opponent roster players: {len(rosters[1]) if rosters else 0}')
    print(f'Waiver players processed: {len(available_players)}')
    print(f'Players with stats: {len(players) - len(missing)}')
    print(f'Players without stats: {len(missing)}')


def print_adp_sample(adp_players):
    """Print the existing raw ADP debug sample."""
    print('\nRAW ADP SAMPLE:')
    if adp_players:
        print(adp_players[0])
    else:
        print('No ADP players were extracted.')
