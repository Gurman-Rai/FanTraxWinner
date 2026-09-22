from services.player_service import (get_league_player_info, get_player_name,
                                     get_player_positions, get_player_adp)

def find_team_roster(rosters_data, team_id):
    """Find a fantasy team's roster."""
    if not isinstance(rosters_data, dict):
        return None
    possible_keys = ['teams', 'rosters', 'teamRosters']
    for key in possible_keys:
        container = rosters_data.get(key)
        if isinstance(container, list):
            for team in container:
                if not isinstance(team, dict):
                    continue
                current_team_id = team.get('teamId') or team.get('id')
                if str(current_team_id) == str(team_id):
                    return team
        elif isinstance(container, dict):
            if str(team_id) in container:
                return container[str(team_id)]
            if team_id in container:
                return container[team_id]
            for key_id, team in container.items():
                if not isinstance(team, dict):
                    continue
                current_team_id = team.get('teamId') or team.get('id') or key_id
                if str(current_team_id) == str(team_id):
                    return team
    if str(team_id) in rosters_data:
        return rosters_data[str(team_id)]
    return None


def extract_roster_players(rosters_data, team_id):
    """Return all roster players."""
    team_roster = find_team_roster(rosters_data, team_id)
    if not team_roster:
        return []
    if isinstance(team_roster, list):
        return team_roster
    if not isinstance(team_roster, dict):
        return []
    possible_player_keys = ['players', 'roster', 'rosterItems', 'playerInfo', 'slots']
    for key in possible_player_keys:
        players = team_roster.get(key)
        if isinstance(players, list):
            return players
        if isinstance(players, dict):
            converted_players = []
            for player_id, player_data in players.items():
                if not isinstance(player_data, dict):
                    continue
                player = player_data.copy()
                if 'playerId' not in player:
                    player['playerId'] = player_id
                converted_players.append(player)
            if converted_players:
                return converted_players
    return []


def get_roster_player_id(roster_player):
    """Extract Fantrax player ID."""
    if not isinstance(roster_player, dict):
        return ''
    nested_player = roster_player.get('player', {})
    if not isinstance(nested_player, dict):
        nested_player = {}
    player_id = roster_player.get('playerId') or roster_player.get('id') or nested_player.get('playerId') or nested_player.get('id')
    if player_id is None:
        return ''
    return str(player_id)


def get_roster_status(roster_player):
    """Get ACTIVE / RESERVE."""
    if not isinstance(roster_player, dict):
        return 'N/A'
    status = roster_player.get('status') or roster_player.get('rosterStatus') or roster_player.get('slot') or roster_player.get('lineupStatus')
    if isinstance(status, dict):
        return status.get('name') or status.get('shortName') or status.get('status') or 'N/A'
    return status or 'N/A'


def get_roster_rows(roster_players, league_data, adp_lookup):
    """Resolve roster player details and sort by the existing ADP key."""
    formatted_players = []
    for roster_player in roster_players:
        if not isinstance(roster_player, dict):
            continue
        player_id = get_roster_player_id(roster_player)
        nested_player = roster_player.get('player', {})
        if not isinstance(nested_player, dict):
            nested_player = {}
        league_player = get_league_player_info(league_data, player_id)
        adp_player = adp_lookup.get(str(player_id), {})
        player_name = get_player_name(adp_player)
        if player_name == 'Unknown':
            player_name = get_player_name(league_player)
        if player_name == 'Unknown':
            player_name = get_player_name(nested_player)
        if player_name == 'Unknown':
            player_name = get_player_name(roster_player)
        positions = get_player_positions(adp_player, league_player)
        if positions == 'N/A':
            positions = get_player_positions(nested_player, roster_player)
        status = get_roster_status(roster_player)
        adp = get_player_adp(adp_player)
        if adp == float('inf'):
            adp = get_player_adp(league_player)
        formatted_players.append({'playerId': player_id, 'playerName': player_name, 'positions': positions, 'status': status, 'adp': adp})
    formatted_players.sort(key=lambda player: player['adp'])
    return formatted_players
