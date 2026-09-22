# FanTraxWinner

A console app for Fantrax matchup summaries, fantasy-week dates, NBA game counts,
both team rosters, and the top 25 available players by Fantrax ADP.

## Run

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Edit `config.py` to change `LEAGUE_ID`, `MY_TEAM_ID`, `NBA_SEASON`,
`MANUAL_START_DATE`, or `MANUAL_END_DATE`. Their existing names and values are
preserved. Each manual date independently overrides its Fantrax scoring-period
date when it is not `None`.

Dates must be quoted: `"2026-01-05"`. Writing `2026-01-05` evaluates subtraction
and produces a number. Invalid manual dates now fail before any network calls.
For historical testing, set `NBA_SEASON = "2025-26"` and use, for example,
`MANUAL_START_DATE = "2026-01-05"` and `MANUAL_END_DATE = "2026-01-11"`.

The current NBA endpoint reads played-game logs. Entirely future date ranges
now skip that request with an explanation. Historical NBA requests use a
5-second connection timeout and a 10-second read timeout, with a clear failure
message if the service cannot be reached. These are fixes added after the
behavior-preserving refactor described below.

`nba_api==1.11.4` records the version already used in the local environment;
the refactor adds no new data source or schedule calculation.

## Structure

```text
main.py
app.py
config.py
clients/
    __init__.py
    fantrax_client.py
    nba_client.py
services/
    __init__.py
    matchup_service.py
    roster_service.py
    player_service.py
    schedule_service.py
formatters/
    __init__.py
    console_formatter.py
```

- `main.py`: creates `FantraxApp` and calls `run()`.
- `app.py`: coordinates requests, parsing, and reports in their original order.
  Existing helper names remain accessible on `FantraxApp` through delegates.
- `config.py`: the existing league/team IDs, NBA season, and manual date overrides.
- `clients/fantrax_client.py`: the four original Fantrax GET requests, preserving
  endpoints, parameters, 30-second timeouts, and `raise_for_status()`.
- `clients/nba_client.py`: the existing `LeagueGameLog` request and team row counts,
  including empty-data and missing-column fallbacks. No printing.
- `services/matchup_service.py`: matchup detection, home/away perspective, and
  formatted category values.
- `services/roster_service.py`: roster-shape fallbacks, player IDs/statuses, roster
  details, and the existing ADP sort.
- `services/player_service.py`: ADP extraction/lookup, names, positions, league
  player lookup, free agents, and their existing sorting/fallback logic.
- `services/schedule_service.py`: scoring-period dates and manual overrides.
- `formatters/console_formatter.py`: all console output, table widths, headings,
  loading messages, and raw ADP debug sample.

Clients can be supplied to `FantraxApp` through its constructor. Importing
`main` does not perform requests. No model classes are needed because the
existing dictionary/list data structures are preserved.

## Preserved behavior

The refactor retains the provider-default matchup period, all parsing fallbacks,
ADP ordering and tie behavior, top-25 limit, manual-date behavior, and the exact
NBA `LeagueGameLog` query. It does not substitute another schedule endpoint or
alter how rows are counted. Console output and error handling are unchanged.

One-time refactor checks compared the original and modular applications across
27 scenarios: home/away/missing matchups, manual and provider dates, partial
overrides, NBA empty/missing-column responses, ADP response variants, and API
failures. Console output, request arguments, and errors matched. All 14 moved
parsing helper bodies were also structurally compared. No new test files were
added.

The older `src/fantrax.py` client and existing `tests/` remain untouched. They
predate this reporting workflow; the app does not use that client's different
retry/credential behavior. In particular, `tests/test_main.py` targets an older
list-printing version of main and is not a verification suite for this refactor.
