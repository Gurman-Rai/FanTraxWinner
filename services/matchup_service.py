"""Matchup detection and category parsing."""

def get_category_value(category_side):
    """Safely return category value."""
    if not category_side:
        return 'N/A'
    if 'formattedValue' in category_side:
        return category_side['formattedValue']
    if 'value' in category_side:
        return category_side['value']
    return 'N/A'


def find_my_matchup(matchups_data, my_team_id):
    """Find matchup containing my team."""
    for matchup in matchups_data.get('matchups', []):
        home_team = matchup.get('home', {})
        away_team = matchup.get('away', {})
        if home_team.get('teamId') == my_team_id or away_team.get('teamId') == my_team_id:
            return matchup
    return None


def get_matchup_sides(my_matchup, my_team_id):
    """Identify the same home/away perspective for the configured team."""
    home_team = my_matchup['home']
    away_team = my_matchup['away']
    if home_team['teamId'] == my_team_id:
        my_team = home_team
        opponent = away_team
        my_side = 'home'
        opponent_side = 'away'
    else:
        my_team = away_team
        opponent = home_team
        my_side = 'away'
        opponent_side = 'home'
    return (my_team, opponent, my_side, opponent_side)


def iter_category_scores(my_matchup, my_side, opponent_side):
    """Yield category values with the original formatted-value fallback."""
    for category in my_matchup.get('categories', []):
        category_name = category.get('shortName', category.get('name', 'Unknown'))
        my_category_data = category.get(my_side, {})
        opponent_category_data = category.get(opponent_side, {})
        my_value = get_category_value(my_category_data)
        opponent_value = get_category_value(opponent_category_data)
        yield (category_name, my_value, opponent_value)
