from services.matchup_service import iter_category_scores
from services.roster_service import extract_roster_players, get_roster_rows
from services.player_service import get_available_player_details


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


def print_adp_sample(adp_players):
    """Print the existing raw ADP debug sample."""
    print('\nRAW ADP SAMPLE:')
    if adp_players:
        print(adp_players[0])
    else:
        print('No ADP players were extracted.')
