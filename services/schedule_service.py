from datetime import datetime

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
