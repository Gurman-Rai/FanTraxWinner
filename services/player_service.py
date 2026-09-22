"""Player identity, free-agent and ADP parsing helpers."""

def get_free_agents(league_data):
    """Get all players whose Fantrax status is FA."""
    player_info = league_data.get('playerInfo', {})
    free_agents = []
    if isinstance(player_info, dict):
        for key, value in player_info.items():
            if not isinstance(value, dict):
                continue
            player = value.copy()
            if 'playerId' not in player:
                player['playerId'] = key
            if player.get('status') == 'FA':
                free_agents.append(player)
    elif isinstance(player_info, list):
        for player in player_info:
            if isinstance(player, dict) and player.get('status') == 'FA':
                free_agents.append(player)
    return free_agents


def extract_adp_players(adp_response_data):
    """Extract player records from Fantrax ADP response."""
    if isinstance(adp_response_data, list):
        return adp_response_data
    if not isinstance(adp_response_data, dict):
        return []
    possible_keys = ['players', 'playerInfo', 'data', 'results', 'adp']
    for key in possible_keys:
        value = adp_response_data.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            players = []
            for player_id, player_data in value.items():
                if not isinstance(player_data, dict):
                    continue
                player = player_data.copy()
                if 'playerId' not in player:
                    player['playerId'] = player_id
                players.append(player)
            return players
    return []


def build_adp_lookup(adp_players):
    """Build playerId -> ADP info lookup."""
    lookup = {}
    for player in adp_players:
        if not isinstance(player, dict):
            continue
        player_id = player.get('playerId') or player.get('id')
        if player_id is None:
            continue
        lookup[str(player_id)] = player
    return lookup


def get_player_name(player):
    """Get player name."""
    if not isinstance(player, dict):
        return 'Unknown'
    return player.get('name') or player.get('playerName') or player.get('fullName') or player.get('displayName') or 'Unknown'


def get_player_positions(player, league_player=None):
    """Get player position."""
    if not isinstance(player, dict):
        player = {}
    positions = player.get('positions') or player.get('position') or player.get('pos') or player.get('eligiblePos')
    if not positions and league_player:
        positions = league_player.get('positions') or league_player.get('position') or league_player.get('pos') or league_player.get('eligiblePos')
    if isinstance(positions, list):
        converted_positions = []
        for position in positions:
            if isinstance(position, dict):
                value = position.get('name') or position.get('shortName') or position.get('position')
                if value:
                    converted_positions.append(str(value))
            else:
                converted_positions.append(str(position))
        return ', '.join(converted_positions)
    if positions:
        return str(positions)
    return 'N/A'


def get_player_adp(player):
    """Return ADP."""
    if not isinstance(player, dict):
        return float('inf')
    possible_fields = ['adp', 'ADP', 'averageDraftPosition', 'avgDraftPosition']
    for field in possible_fields:
        value = player.get(field)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return float('inf')


def get_league_player_info(league_data, player_id):
    """Retrieve player info from Fantrax league info."""
    player_info = league_data.get('playerInfo', {})
    if isinstance(player_info, dict):
        player = player_info.get(str(player_id))
        if isinstance(player, dict):
            return player
        player = player_info.get(player_id)
        if isinstance(player, dict):
            return player
    elif isinstance(player_info, list):
        for player in player_info:
            if not isinstance(player, dict):
                continue
            current_id = player.get('playerId') or player.get('id')
            if str(current_id) == str(player_id):
                return player
    return {}


def get_available_players(league_info, adp_lookup):
    """Join free agents to ADP and retain the original sorting."""
    free_agents = get_free_agents(league_info)
    available_players = []
    for free_agent in free_agents:
        player_id = str(free_agent.get('playerId', ''))
        if not player_id:
            continue
        adp_player = adp_lookup.get(player_id, {})
        available_players.append({'playerId': player_id, 'leagueInfo': free_agent, 'adpInfo': adp_player})
    available_players.sort(key=lambda player: get_player_adp(player['adpInfo']))
    return available_players


def get_available_player_details(player):
    """Resolve the original name, position and ADP fallbacks for a free agent."""
    league_player = player['leagueInfo']
    adp_player = player['adpInfo']
    player_id = player['playerId']
    player_name = get_player_name(adp_player)
    if player_name == 'Unknown':
        player_name = get_player_name(league_player)
    positions = get_player_positions(adp_player, league_player)
    adp = get_player_adp(adp_player)
    if adp == float('inf'):
        adp = get_player_adp(league_player)
    return (player_id, player_name, positions, adp)
