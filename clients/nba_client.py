from nba_api.stats.endpoints import leaguegamelog
import requests

from config import NBA_SEASON


class NBAClient:
    """Retrieve and count the same LeagueGameLog rows as before."""

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
