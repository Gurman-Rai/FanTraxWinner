"""Coordinate data retrieval, parsing, and the existing console reports."""

from config import LEAGUE_ID, MY_TEAM_ID, NBA_SEASON, NBA_WEEK, NBA_STATS_SEASON
from datetime import datetime, timezone
from clients.fantrax_client import FantraxClient
from clients.nba_client import NBAClient
from services import matchup_service, player_service, roster_service, schedule_service
from formatters import console_formatter as console


class FantraxApp:
    """Run the existing matchup, schedule, roster, and ADP reports."""

    def __init__(
        self,
        league_id=LEAGUE_ID,
        my_team_id=MY_TEAM_ID,
        fantrax_client: FantraxClient | None = None,
        nba_client: NBAClient | None = None,
    ):
        self.league_id = league_id
        self.my_team_id = my_team_id
        self.fantrax_client = (
            fantrax_client if fantrax_client is not None else FantraxClient(league_id)
        )
        self.nba_client = nba_client if nba_client is not None else NBAClient()

    # Keep the existing helper entry points available without duplicate logic.
    get_category_value = staticmethod(matchup_service.get_category_value)
    find_my_matchup = staticmethod(matchup_service.find_my_matchup)
    get_free_agents = staticmethod(player_service.get_free_agents)
    extract_adp_players = staticmethod(player_service.extract_adp_players)
    build_adp_lookup = staticmethod(player_service.build_adp_lookup)
    get_player_name = staticmethod(player_service.get_player_name)
    get_player_positions = staticmethod(player_service.get_player_positions)
    get_player_adp = staticmethod(player_service.get_player_adp)
    get_league_player_info = staticmethod(player_service.get_league_player_info)
    find_team_roster = staticmethod(roster_service.find_team_roster)
    extract_roster_players = staticmethod(roster_service.extract_roster_players)
    get_roster_player_id = staticmethod(roster_service.get_roster_player_id)
    get_roster_status = staticmethod(roster_service.get_roster_status)
    get_scoring_period_dates = staticmethod(schedule_service.get_scoring_period_dates)
    print_team_roster = staticmethod(console.print_team_roster)

    def get_nba_games_by_team(self, start_date, end_date):
        """Skip future played-game queries and otherwise retrieve game counts."""
        start = schedule_service.parse_date(start_date, 'Start date')
        end = schedule_service.parse_date(end_date, 'End date')
        if start > end:
            raise ValueError('Start date must be on or before end date.')
        if start > datetime.now(timezone.utc).date():
            console.print_future_game_logs()
            return {}
        console.print_schedule_loading()
        return self.nba_client.get_nba_games_by_team(start_date, end_date)

    def run(self) -> None:
        """Fetch the same data and print reports in the same order."""
        schedule_service.validate_manual_dates()
        if type(NBA_WEEK) is not int or NBA_WEEK < 1:
            raise ValueError('NBA_WEEK must be a positive integer.')
        console.print_progress('[1/4] Loading Fantrax league information...')
        league_info = self.fantrax_client.get_league_info()
        console.print_progress('[2/4] Loading Fantrax team rosters...')
        rosters = self.fantrax_client.get_team_rosters()
        console.print_progress('[3/4] Loading Fantrax matchup scores...')
        matchups = self.fantrax_client.get_matchup_scores()
        console.print_progress('[4/4] Loading Fantrax ADP...')
        adp_data = self.fantrax_client.get_adp()
        console.print_progress('Fantrax requests complete. Preparing reports...')

        adp_players = self.extract_adp_players(adp_data)
        adp_lookup = self.build_adp_lookup(adp_players)
        my_matchup = self.find_my_matchup(matchups, self.my_team_id)
        available_players = player_service.get_available_players(league_info, adp_lookup)
        available_rows = player_service.get_available_player_rows(available_players)
        player_names = {player['playerName'] for player in available_rows}
        roster_rows = []
        if my_matchup is not None:
            my_team, opponent, my_side, opponent_side = matchup_service.get_matchup_sides(
                my_matchup, self.my_team_id)
            for team in (my_team, opponent):
                rows = roster_service.get_roster_rows(
                    self.extract_roster_players(rosters, team['teamId']), league_info, adp_lookup)
                roster_rows.append(rows)
                player_names.update(player['playerName'] for player in rows)
        current_period = matchups.get('period')
        # Fantasy dates are informational; NBA counts use only NBA_WEEK.
        start_date, end_date = self.get_scoring_period_dates(league_info, current_period)
        start_date = schedule_service.MANUAL_START_DATE or start_date
        end_date = schedule_service.MANUAL_END_DATE or end_date
        console.print_week_dates(current_period, start_date, end_date)
        console.print_progress(f'Loading NBA {NBA_SEASON} schedule and player teams...')
        nba_games_by_team = self.nba_client.get_weekly_games_by_team(NBA_WEEK)
        player_team_map = self.nba_client.get_player_team_map(player_names)
        console.print_progress(f'Loading NBA {NBA_STATS_SEASON} per-game season averages...')
        player_stats_map = self.nba_client.get_player_stats_map(NBA_STATS_SEASON, player_names)
        # One shared enrichment path for both rosters and the entire available pool.
        enriched_groups = [
            player_service.map_players_to_stats(
                roster_service.map_players_to_weekly_games(players, player_team_map, nba_games_by_team),
                player_stats_map)
            for players in [*roster_rows, available_rows]
        ]
        weekly_rosters, available_rows = enriched_groups[:-1], enriched_groups[-1]

        if my_matchup is None:
            console.print_missing_matchup()
        else:
            console.print_matchup_summary(
                my_matchup, my_team, opponent, my_side, opponent_side, current_period)
            self.print_team_roster(my_team['teamName'], my_team['teamId'],
                                   rosters, league_info, adp_lookup)
            self.print_team_roster(opponent['teamName'], opponent['teamId'],
                                   rosters, league_info, adp_lookup)
            console.print_weekly_matchup(
                NBA_SEASON, NBA_WEEK, my_team['teamName'], opponent['teamName'],
                *weekly_rosters, nba_games_by_team, player_team_map)
            for team, players in zip((my_team, opponent), weekly_rosters):
                console.print_player_stats(team['teamName'], players, NBA_STATS_SEASON)

        console.print_available_players(available_players)
        console.print_player_stats('WAIVER / FREE AGENTS - TOP 25 BY ADP',
                                   available_rows[:25], NBA_STATS_SEASON)
        console.print_stats_summary(self.nba_client.stats_rows_fetched,
                                    weekly_rosters, available_rows)
        console.print_adp_sample(adp_players)
