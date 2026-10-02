"""Opt-in live diagnostic: python tests/test_nba_schedule_sources.py.

No network calls occur during pytest collection. Exit 0 means at least one
source passed validation; exit 1 means production integration is not justified.
"""

from collections import Counter
from datetime import date
import importlib
import importlib.metadata
import pkgutil

import pandas as pd
import requests
from nba_api.stats import endpoints
from nba_api.stats.static import teams

NBA_SEASON = "2026-27"
START_DATE = "2026-10-20"
END_DATE = "2026-10-25"
NBA_WEEK = 1
TIMEOUT = (5, 10)
CDN_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nba.com/",
}
TEAM_CODES = {team['abbreviation'] for team in teams.get_teams()}


def calendar_date(value):
    # gameDate is a league calendar date. Preserve it rather than shifting to UTC.
    stamp = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(stamp) else stamp.date()


def in_window(frame):
    dates = frame['gameDate'].map(calendar_date)
    return frame[dates.map(lambda d: d is not None and
                          date.fromisoformat(START_DATE) <= d <= date.fromisoformat(END_DATE))]


def validate(label, frame):
    print(f"\n[{label}]", flush=True)
    print(f"Rows: {len(frame)}")
    if frame.empty:
        print("Status: FAIL\nReason: returned 0 games in the requested selection")
        return False
    required = {'gameId', 'gameDate', 'gameStatus',
                'homeTeam_teamTricode', 'awayTeam_teamTricode'}
    if not required <= set(frame.columns):
        raise ValueError(f"Missing columns: {sorted(required - set(frame.columns))}")
    display = [c for c in ['gameDate', 'weekNumber', 'gameId', 'gameStatus',
                           'gameStatusText', 'awayTeam_teamTricode',
                           'homeTeam_teamTricode'] if c in frame]
    print(frame[display].to_string(index=False))
    ids = frame['gameId'].astype(str)
    if ids.duplicated().any():
        raise ValueError("Duplicate game IDs would inflate team counts")
    if not ids.str.startswith('002').all():
        raise ValueError("Selection includes non-regular-season game IDs")
    if len(in_window(frame)) != len(frame):
        raise ValueError("Selection includes dates outside the requested window")
    counts = Counter()
    for row in frame.to_dict('records'):
        home, away = row['homeTeam_teamTricode'], row['awayTeam_teamTricode']
        if home not in TEAM_CODES or away not in TEAM_CODES or home == away:
            raise ValueError(f"Invalid NBA team pairing: {away!r} at {home!r}")
        counts.update((home, away))
    future = frame.apply(lambda r: calendar_date(r['gameDate']) > date.today()
                        and str(r['gameStatus']) == '1', axis=1)
    print("TEAM      GAMES")
    for team, count in sorted(counts.items()):
        print(f"{team:<10}{count}")
    assert sum(counts.values()) == 2 * len(frame)
    print(f"Future games found: {'YES' if future.any() else 'NO'}")
    print(f"Status: {'PASS' if future.any() else 'FAIL - no future scheduled games'}", flush=True)
    return bool(future.any())


def failure(label, exc):
    print(f"\n[{label}]\nStatus: FAIL\nReason: {type(exc).__name__}: {exc}", flush=True)


def schedule_probe(module_name, class_name):
    print(f"\nRequesting {class_name}...", flush=True)
    try:
        cls = getattr(importlib.import_module(f'nba_api.stats.endpoints.{module_name}'), class_name)
        frame = cls(season=NBA_SEASON, timeout=TIMEOUT).get_data_frames()[0]
        print(f"Total rows returned: {len(frame)}")
        print(f"Required field sample:\n{frame.reindex(columns=['gameDate', 'weekNumber', 'gameStatus', 'gameStatusText', 'homeTeam_teamTricode', 'awayTeam_teamTricode']).head(3).to_string(index=False)}")
        if 'seasonYear' in frame:
            print(f"Returned seasons: {frame['seasonYear'].unique().tolist()}")
            if not frame['seasonYear'].eq(NBA_SEASON).all():
                raise ValueError('Response contains a different season')
    except Exception as exc:
        failure(f'{class_name} - weekNumber AND date range', exc)
        return []
    passed = []
    selections = {
        'weekNumber': lambda: frame[pd.to_numeric(frame['weekNumber'], errors='coerce') == NBA_WEEK],
        'date range': lambda: in_window(frame),
    }
    ids = {}
    for kind, select in selections.items():
        label = f'{class_name} - {kind}'
        try:
            selected = select()
            ids[kind] = set(selected['gameId'])
            if validate(label, selected):
                passed.append(label)
        except Exception as exc:
            failure(label, exc)
    if len(ids) == 2:
        print(f"Week/date game IDs match: {ids['weekNumber'] == ids['date range']}")
    return passed


def cdn_probe():
    label = 'NBA CDN'
    print(f"\nRequesting {label}...", flush=True)
    try:
        response = requests.get(CDN_URL, timeout=TIMEOUT)
        print(f"Normal request HTTP {response.status_code}")
        if response.status_code == 403:
            response = requests.get(CDN_URL, headers=HEADERS, timeout=TIMEOUT)
            print(f"Browser-style headers HTTP {response.status_code}")
        response.raise_for_status()
        schedule = response.json()['leagueSchedule']
        print(f"Returned season: {schedule.get('seasonYear')}")
        rows = []
        for day in schedule['gameDates']:
            for game in day['games']:
                rows.append({**game, 'gameDate': day['gameDate'],
                             'homeTeam_teamTricode': game['homeTeam']['teamTricode'],
                             'awayTeam_teamTricode': game['awayTeam']['teamTricode']})
        frame = pd.DataFrame(rows)
        print(f"Total rows returned: {len(frame)}")
        if schedule.get('seasonYear') != NBA_SEASON:
            raise ValueError(f"Wrong season: {schedule.get('seasonYear')!r}")
        return [label] if validate(label, in_window(frame)) else []
    except Exception as exc:
        failure(label, exc)
        return []


def scoreboard_probe(module_name, class_name):
    cls = getattr(importlib.import_module(f'nba_api.stats.endpoints.{module_name}'), class_name)
    rows, errors = [], []
    for day in pd.date_range(START_DATE, END_DATE):
        iso = day.date().isoformat()
        print(f"Requesting {class_name} {iso}...", flush=True)
        try:
            endpoint = cls(game_date=iso, timeout=TIMEOUT)
            # Inspect structured raw headers; team IDs are resolved by nba_api's static table.
            headers = endpoint.game_header.get_data_frame()
            print(f"{iso}: {len(headers)} rows; columns: {list(headers.columns)}")
            if class_name == 'ScoreboardV2':
                codes = {t['id']: t['abbreviation'] for t in teams.get_teams()}
                for game in headers.to_dict('records'):
                    if calendar_date(game['GAME_DATE_EST']) != day.date():
                        raise ValueError(f"Requested {iso}, received {game['GAME_DATE_EST']}")
                    rows.append({'gameId': game['GAME_ID'], 'gameDate': game['GAME_DATE_EST'],
                                 'gameStatus': game['GAME_STATUS_ID'],
                                 'gameStatusText': game['GAME_STATUS_TEXT'],
                                 'homeTeam_teamTricode': codes.get(game['HOME_TEAM_ID']),
                                 'awayTeam_teamTricode': codes.get(game['VISITOR_TEAM_ID'])})
            else:
                raw = endpoint.get_dict()['scoreboard']
                if calendar_date(raw['gameDate']) != day.date():
                    raise ValueError(f"Requested {iso}, received {raw['gameDate']}")
                for game in raw['games']:
                    rows.append({**game, 'gameDate': raw['gameDate'],
                                 'homeTeam_teamTricode': game['homeTeam']['teamTricode'],
                                 'awayTeam_teamTricode': game['awayTeam']['teamTricode']})
        except Exception as exc:
            failure(f'{class_name} {iso}', exc)
            errors.append(iso)
    if errors:
        print(f'{class_name}: FAIL - incomplete window; failed dates: {errors}')
        return []
    try:
        return [class_name] if validate(class_name, pd.DataFrame(rows)) else []
    except Exception as exc:
        failure(class_name, exc)
        return []


def historical_probe(module_name, class_name, **kwargs):
    print(f"\nRequesting {class_name}...", flush=True)
    try:
        cls = getattr(importlib.import_module(f'nba_api.stats.endpoints.{module_name}'), class_name)
        frame = cls(date_from_nullable=START_DATE, date_to_nullable=END_DATE,
                    timeout=TIMEOUT, **kwargs).get_data_frames()[0]
        print(f"[{class_name}]\nRows: {len(frame)}")
        print(frame.head().to_string(index=False))
        print("Status: FAIL FOR FUTURE SCHEDULES\nReason: " +
              ("returned 0 future rows" if frame.empty else
               "statistical records are not proof of unplayed scheduled games; inspect above"))
    except Exception as exc:
        failure(class_name, exc)
        print("Historical-only behavior cannot be empirically confirmed when the request fails.")


def main():
    print('=' * 72)
    print(f'NBA SCHEDULE SOURCE TEST\nSeason: {NBA_SEASON}\n'
          f'Window: {START_DATE} to {END_DATE}\nToday: {date.today()}\n'
          f'nba_api: {importlib.metadata.version("nba_api")}')
    installed = {m.name for m in pkgutil.iter_modules(endpoints.__path__)}
    print('Installed candidates:', sorted(n for n in installed if
          any(s in n for s in ('schedule', 'scoreboard', 'leaguegame'))))
    passed = schedule_probe('scheduleleaguev2', 'ScheduleLeagueV2')
    passed += cdn_probe()
    for module, cls in [('scheduleleaguev2int', 'ScheduleLeagueV2Int'),
                        ('scoreboardv2', 'ScoreboardV2'), ('scoreboardv3', 'ScoreboardV3')]:
        if module in installed:
            passed += (schedule_probe(module, cls) if 'schedule' in module
                       else scoreboard_probe(module, cls))
    historical_probe('leaguegamelog', 'LeagueGameLog', season=NBA_SEASON,
                     season_type_all_star='Regular Season')
    historical_probe('leaguegamefinder', 'LeagueGameFinder', season_nullable=NBA_SEASON,
                     season_type_nullable='Regular Season')
    print('\nLive scoreboard excluded: its fixed todaysScoreboard URL cannot select future dates.')
    print(f'\nValidated future sources: {passed or "NONE"}', flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
