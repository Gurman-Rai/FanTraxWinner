import requests


class FantraxClient:
    """The reporting app's original Fantrax HTTP requests."""

    def __init__(self, league_id: str):
        self.league_id = league_id

    def get_league_info(self):
        """Retrieve league info using the existing request."""
        league_info_url = 'https://www.fantrax.com/fxea/general/getLeagueInfo'
        league_info_params = {'leagueId': self.league_id, 'excludePlayerInfo': 'false'}
        league_info_response = requests.get(league_info_url, params=league_info_params, timeout=30)
        league_info_response.raise_for_status()
        league_info = league_info_response.json()
        return league_info

    def get_team_rosters(self):
        """Retrieve rosters using the existing request."""
        rosters_url = 'https://www.fantrax.com/fxea/general/getTeamRosters'
        rosters_params = {'leagueId': self.league_id}
        rosters_response = requests.get(rosters_url, params=rosters_params, timeout=30)
        rosters_response.raise_for_status()
        rosters = rosters_response.json()
        return rosters

    def get_matchup_scores(self):
        """Retrieve matchups using the existing request."""
        matchups_url = 'https://www.fantrax.com/fxea/general/getMatchupScores'
        matchups_params = {'leagueId': self.league_id}
        matchups_response = requests.get(matchups_url, params=matchups_params, timeout=30)
        matchups_response.raise_for_status()
        matchups = matchups_response.json()
        return matchups

    def get_adp(self):
        """Retrieve adp data using the existing request."""
        adp_url = 'https://www.fantrax.com/fxea/general/getAdp'
        adp_params = {
            'sport': 'NBA',
            'showAllPositions': 'true',
            'start': 0,
            'limit': 1000,
            'order': 'ADP',
        }
        adp_response = requests.get(adp_url, params=adp_params, timeout=30)
        adp_response.raise_for_status()
        adp_data = adp_response.json()
        return adp_data
