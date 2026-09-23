from nba_api.stats.endpoints import commonallplayers, leaguegamelog, scheduleleaguev2, leaguedashplayerstats
import pandas as pd
import requests

from config import NBA_SEASON
from services.player_service import NBA_STAT_KEYS, normalize_player_name


class NBAClient:
    """Retrieve NBA schedules, player teams, and historical game logs."""

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
        columns = ['homeTeam_teamTricode', 'awayTeam_teamTricode']
        if not {'weekNumber', *columns}.issubset(games.columns):
            raise ValueError('NBA ScheduleLeagueV2 response is missing required schedule columns.')
        week_games = games[games['weekNumber'] == week_number]
        counts = {}
        for column in columns:
            for team in week_games[column].dropna():
                if isinstance(team, str) and team.strip():
                    team = team.strip().upper()
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
        """
        Count NBA games for every team between
        start_date and end_date.

        Expected date format:
        YYYY-MM-DD
        """
        try:
            game_log = leaguegamelog.LeagueGameLog(
                season=NBA_SEASON,
                season_type_all_star='Regular Season',
                date_from_nullable=start_date,
                date_to_nullable=end_date,
                player_or_team_abbreviation='T',
                timeout=(5, 10),
            )
        except requests.RequestException as exc:
            raise requests.RequestException(
                f'NBA game-log request failed ({type(exc).__name__}). '
                'Check your connection and try again; the NBA service may be unavailable. '
                'The request uses a 5-second connection and 10-second read timeout.'
            ) from None
        data_frames = game_log.get_data_frames()
        if not data_frames:
            return {}
        games_df = data_frames[0]
        if games_df.empty:
            return {}
        if 'TEAM_ABBREVIATION' not in games_df.columns:
            return {}
        games_by_team = {}
        for team_abbreviation in games_df['TEAM_ABBREVIATION'].dropna().unique():
            team_games = games_df[games_df['TEAM_ABBREVIATION'] == team_abbreviation]
            games_by_team[str(team_abbreviation)] = len(team_games)
        return games_by_team
