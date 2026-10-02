from nba_api.stats.endpoints import commonallplayers, scheduleleaguev2, leaguedashplayerstats
from nba_api.stats.static import teams
import pandas as pd
import requests

from config import NBA_SEASON
from services.player_service import NBA_STAT_KEYS, normalize_player_name
from services.schedule_service import parse_date


class NBAClient:
    """Retrieve NBA schedules, player teams, and player statistics."""

    def get_player_stats_map(self, season: str, player_names=None) -> dict:
        """Fetch per-game regular-season averages once; optionally retain selected names."""
        self.stats_rows_fetched = 0
        wanted = None if player_names is None else {
            normalize_player_name(name) for name in player_names}
        try:
            stats = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season, season_type_all_star='Regular Season',
                per_mode_detailed='PerGame', timeout=(5, 10))
            frames = stats.get_data_frames()
        except requests.RequestException as exc:
            raise requests.RequestException(
                f'NBA LeagueDashPlayerStats request failed ({type(exc).__name__}). '
                'Check your connection and NBA service availability.') from None
        except (ValueError, KeyError, IndexError) as exc:
            raise ValueError('NBA LeagueDashPlayerStats returned an invalid stats response.') from exc
        if not frames:
            raise ValueError('NBA LeagueDashPlayerStats returned no stats dataset.')
        stats_df = frames[0]
        columns = ['PLAYER_NAME', 'TEAM_ABBREVIATION', *(key.upper() for key in NBA_STAT_KEYS)]
        if not set(columns).issubset(stats_df.columns):
            raise ValueError('NBA LeagueDashPlayerStats response is missing required stats columns.')
        self.stats_rows_fetched = len(stats_df)
        mapping = {}
        for row in stats_df[columns].to_dict('records'):
            name = row['PLAYER_NAME']
            if not isinstance(name, str) or not name.strip():
                continue
            key = normalize_player_name(name)
            if wanted is not None and key not in wanted:
                continue
            mapping[key] = {
                'nba_team': None if pd.isna(row['TEAM_ABBREVIATION']) else row['TEAM_ABBREVIATION'],
                **{stat: None if pd.isna(row[stat.upper()]) else float(row[stat.upper()])
                   for stat in NBA_STAT_KEYS},
            }
        return mapping

    def get_weekly_games_by_team(self, week_number: int) -> dict[str, int]:
        """Count both teams in each scheduled game in the selected NBA week."""
        if type(week_number) is not int or week_number < 1:
            raise ValueError('NBA_WEEK must be a positive integer.')
        games = self._get_schedule_dataframe()
        # Reuse this run's response for DSS remaining-game calculations; no extra request.
        self.schedule_games = games.copy()
        return self._count_schedule_games(games[games['weekNumber'] == week_number])

    def _get_schedule_dataframe(self):
        """Fetch current regular-season schedules, including unplayed games."""
        try:
            schedule = scheduleleaguev2.ScheduleLeagueV2(
                season=NBA_SEASON, timeout=(5, 10))
            frames = schedule.get_data_frames()
        except requests.RequestException as exc:
            raise requests.RequestException(
                f'NBA ScheduleLeagueV2 request failed ({type(exc).__name__}). '
                'Check your connection and NBA service availability.') from None
        except (ValueError, KeyError, IndexError) as exc:
            raise ValueError('NBA ScheduleLeagueV2 returned an invalid schedule response.') from exc
        if not frames:
            raise ValueError('NBA ScheduleLeagueV2 returned no schedule dataset.')
        games = frames[0]
        columns = {'weekNumber', 'gameId', 'gameDate', 'seasonYear',
                   'homeTeam_teamTricode', 'awayTeam_teamTricode'}
        if not columns.issubset(games.columns):
            raise ValueError('NBA ScheduleLeagueV2 response is missing required schedule columns.')
        if games.empty or not games['seasonYear'].eq(NBA_SEASON).all():
            raise ValueError(f'NBA ScheduleLeagueV2 returned no schedule for {NBA_SEASON}.')
        # NBA game IDs beginning 002 identify regular-season games.
        games = games[games['gameId'].astype(str).str.startswith('002')].copy()
        games = games.drop_duplicates(subset='gameId')
        games['weekNumber'] = pd.to_numeric(games['weekNumber'], errors='coerce')
        # gameDate is the league calendar date, not the UTC tip-off timestamp.
        games['gameDate'] = games['gameDate'].map(
            lambda value: pd.to_datetime(value, errors='coerce').date())
        if games['gameDate'].isna().any():
            raise ValueError('NBA ScheduleLeagueV2 returned an invalid gameDate.')
        return games

    @staticmethod
    def _count_schedule_games(games):
        if games.empty:
            raise ValueError('NBA schedule source returned no games for the requested week or date range.')
        valid_teams = {team['abbreviation'] for team in teams.get_teams()}
        counts = {}
        for home, away in games[['homeTeam_teamTricode', 'awayTeam_teamTricode']].itertuples(
                index=False, name=None):
            if home not in valid_teams or away not in valid_teams or home == away:
                raise ValueError('NBA ScheduleLeagueV2 returned an invalid team pairing.')
            for team in (home, away):
                counts[team] = counts.get(team, 0) + 1
        return counts

    def get_player_team_map(self, player_names=None) -> dict[str, str]:
        """Fetch once and retain only requested names, or all when omitted."""
        wanted = None if player_names is None else {
            normalize_player_name(name) for name in player_names}
        if wanted == set():
            return {}
        try:
            players = commonallplayers.CommonAllPlayers(
                season=NBA_SEASON, is_only_current_season=1, timeout=(5, 10))
            frames = players.get_data_frames()
        except requests.RequestException as exc:
            raise requests.RequestException(
                f'NBA CommonAllPlayers request failed ({type(exc).__name__}). '
                'Check your connection and NBA service availability.') from None
        except (ValueError, KeyError, IndexError) as exc:
            raise ValueError('NBA CommonAllPlayers returned an invalid player response.') from exc
        if not frames:
            raise ValueError('NBA CommonAllPlayers returned no player dataset.')
        players_df = frames[0]
        if not {'DISPLAY_FIRST_LAST', 'TEAM_ABBREVIATION'}.issubset(players_df.columns):
            raise ValueError('NBA CommonAllPlayers response is missing required player columns.')
        mapping = {}
        for column in ('DISPLAY_FIRST_LAST', 'DISPLAY_LAST_COMMA_FIRST'):
            if column not in players_df.columns:
                continue
            for name, team in players_df[
                    [column, 'TEAM_ABBREVIATION']].itertuples(index=False, name=None):
                if isinstance(name, str) and name and isinstance(team, str) and team.strip():
                    key = normalize_player_name(name)
                    if wanted is None or key in wanted:
                        mapping.setdefault(key, team.strip().upper())
            if wanted is not None and wanted <= mapping.keys():
                break
        return mapping

    def get_nba_games_by_team(self, start_date, end_date) -> dict[str, int]:
        """Count scheduled games in an inclusive ISO date range, including future games."""
        start = parse_date(start_date, 'Start date')
        end = parse_date(end_date, 'End date')
        if start > end:
            raise ValueError('Start date must be on or before end date.')
        games = self._get_schedule_dataframe()
        return self._count_schedule_games(
            games[(games['gameDate'] >= start) & (games['gameDate'] <= end)])
