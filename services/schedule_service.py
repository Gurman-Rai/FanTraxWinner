from datetime import date, datetime

from config import MANUAL_START_DATE, MANUAL_END_DATE


def parse_date(value, label):
    """Read an ISO date or Fantrax timestamp without accepting numeric dates."""
    if not isinstance(value, str):
        raise ValueError(f'{label} must be a quoted date, such as "2026-01-05".')
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        raise ValueError(f'{label} must use YYYY-MM-DD or a valid ISO timestamp.') from None


def validate_manual_dates():
    """Catch invalid overrides before making any API requests."""
    start = parse_date(MANUAL_START_DATE, 'MANUAL_START_DATE') if MANUAL_START_DATE is not None else None
    end = parse_date(MANUAL_END_DATE, 'MANUAL_END_DATE') if MANUAL_END_DATE is not None else None
    if start is not None and end is not None and start > end:
        raise ValueError('MANUAL_START_DATE must be on or before MANUAL_END_DATE.')

def get_scoring_period_dates(league_info, period_number):
    """Get Fantrax scoring-period start and end dates."""
    scoring_periods = league_info.get('scoringPeriods', [])
    for period in scoring_periods:
        if str(period.get('number')) == str(period_number):
            start_date = period.get('startDate')
            end_date = period.get('endDate')
            return (start_date, end_date)
    return (None, None)


def get_week_dates(league_info, current_period):
    """Apply the existing manual date overrides independently."""
    fantrax_start_date, fantrax_end_date = get_scoring_period_dates(league_info, current_period)
    start_date = MANUAL_START_DATE if MANUAL_START_DATE is not None else fantrax_start_date
    end_date = MANUAL_END_DATE if MANUAL_END_DATE is not None else fantrax_end_date
    if parse_date(start_date, 'Start date') > parse_date(end_date, 'End date'):
        raise ValueError('Start date must be on or before end date.')
    return (start_date, end_date)


def get_remaining_games_by_team(games, start_date, end_date, as_of=None):
    """Count unstarted games from an existing schedule, at calendar-day precision.

    Uses actual Fantrax period dates, not manual display overrides. In-progress
    games are omitted; intraday scoring-period boundaries are not modeled in V1.
    """
    period_start = parse_date(start_date, 'DSS period start')
    start = max(period_start, as_of if as_of is not None else date.today())
    dates = get_remaining_game_dates_by_team(games, start, end_date)
    return {team: len(game_dates) for team, game_dates in dates.items()}


def get_remaining_game_dates_by_team(games, start_date, end_date):
    """Return unstarted regular-season calendar dates per team, without duplicate games."""
    start = parse_date(start_date, 'DSS period start') if isinstance(start_date, str) else start_date
    end = parse_date(end_date, 'DSS period end')
    if start > end:
        raise ValueError('DSS period start must be on or before its end.')
    required = {'gameDate', 'gameId', 'gameStatus', 'homeTeam_teamTricode', 'awayTeam_teamTricode'}
    if games is None or not required.issubset(games.columns):
        raise ValueError('DSS requires the fetched schedule with game status information.')
    dates_by_team = {}
    for game in games.drop_duplicates(subset='gameId').to_dict('records'):
        game_date = game['gameDate']
        if isinstance(game_date, str):
            game_date = parse_date(game_date, 'NBA game date')
        if (start <= game_date <= end and
                str(game['gameStatus']) == '1' and str(game['gameId']).startswith('002')):
            for column in ('homeTeam_teamTricode', 'awayTeam_teamTricode'):
                team = game[column]
                dates_by_team.setdefault(team, []).append(game_date.isoformat())
    return {team: sorted(game_dates) for team, game_dates in dates_by_team.items()}
