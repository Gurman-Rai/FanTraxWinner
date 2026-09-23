# FanTraxWinner

A console app for Fantrax matchup summaries, fantasy-week dates, NBA game counts,
both team rosters, and the top 25 available players by Fantrax ADP.

## Run

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Edit `config.py` to change `LEAGUE_ID`, `MY_TEAM_ID`, `NBA_SEASON`, `NBA_WEEK`,
`MANUAL_START_DATE`, or `MANUAL_END_DATE`. The weekly player report defaults to
`NBA_SEASON = "2026-27"` and `NBA_WEEK = 1`. Each manual date independently
overrides the displayed Fantrax scoring-period date when it is not `None`.
Manual dates do not select the NBA week.

Dates must be quoted: `"2026-01-05"`. Writing `2026-01-05` evaluates subtraction
and produces a number. Invalid manual dates now fail before any network calls.
For historical testing, set `NBA_SEASON = "2025-26"` and use, for example,
`MANUAL_START_DATE = "2026-01-05"` and `MANUAL_END_DATE = "2026-01-11"`.

Each run fetches `ScheduleLeagueV2` once and counts home and away teams in
dataframe 0 where `weekNumber == NBA_WEEK`. It fetches `CommonAllPlayers` once
for the configured season and reuses its player/team map for both rosters.
The app supplies only names from your roster, your opponent's roster, and the
existing Fantrax available-player pool (`FA`). Other fantasy teams' players
are excluded from the map. The NBA endpoint still returns the full dataset;
this limits stored mappings, not network traffic. No per-player requests are made.
Requests use a 5-second connection timeout and a 10-second read timeout.
The existing date-based `get_nba_games_by_team(start_date, end_date)` helper
remains available, but the normal run now uses scheduled games instead.

`nba_api==1.11.4` remains unchanged; this feature adds no dependencies.

Both NBA and Fantrax names use `normalize_player_name()` in
`services/player_service.py`: convert last-first names, remove diacritics,
lowercase, and collapse whitespace. The only manual alias is
`nicolas claxton` -> `nic claxton`. NBA-provided name aliases use the same
normalization. There is no fuzzy matching or suffix normalization. Missing teams display
`UNKNOWN`, zero games, and a warning. Totals include all roster statuses and
represent possible player-games, without injury or lineup adjustments.

Verify offline with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_weekly_games.py tests/test_fantrax.py
```

For live verification, run `main.py` and check both weekly roster tables,
totals, schedule-team count, normalized name-map count, and unmatched
warnings. Empty schedule/player datasets produce warnings instead of implying
that every zero is confirmed. No data is persisted between runs.

Live Week 1 verification after normalization returned 581 normalized name keys.
Both rosters contained 15 players; totals were 41 and 39, with zero unmatched
players. Porzingis, Vucevic, and Claxton all mapped using API-provided teams.
Live data may change.

## Structure

### Season averages

`NBA_STATS_SEASON = "2025-26"` selects the regular-season per-game averages,
independently of `NBA_SEASON` and `NBA_WEEK`. Each normal run calls
`NBAClient.get_player_stats_map(season, player_names)` once. It uses
`LeagueDashPlayerStats` with `per_mode_detailed="PerGame"`, retaining only the
relevant normalized names. `stats_rows_fetched` records the full response row
count for the debug summary; no dataset is cached between runs.

`player_service.map_players_to_stats(players, player_stats_map)` copies rows
and attaches `pts`, `reb`, `ast`, `stl`, `blk`, `fg3m`, `fg_pct`, `ft_pct`, and
`tov`. The same map and helper serve both rosters and every available player.
Historical stats teams never replace current teams. Missing averages are
`None` / `N/A`, while actual zero averages stay zero. Percentages are displayed
as decimals to three places; no averages are multiplied by weekly games.

Both roster stats tables and the top 25 available players are displayed,
preserving ADP order. Missing named players receive individual warnings;
unnamed entries are counted together. All available rows are enriched even
when outside the displayed top 25. The available pool retains its existing
Fantrax `FA` filter; separate waiver-status detection has not been added.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_weekly_games.py tests/test_player_stats.py tests/test_fantrax.py
.\.venv\Scripts\python.exe main.py
```

Live verification matched all nine supplied averages for Shai Gilgeous-Alexander,
Trae Young, Jalen Duren, Stephen Curry, and Jayson Tatum. The API returned 582
stats rows; 123 of the 1,645 relevant Fantrax rows matched. The 1,522 missing rows
included 1,499 entries whose names the existing Fantrax/ADP lookup cannot resolve.
The remaining 23 named failures include rookies and name differences; no extra
aliases or guesses were introduced. See the local verification output in
`data/season-stats-verification.txt` for all warnings and tables.

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
- `clients/nba_client.py`: weekly schedule counts and current player/team mapping,
  plus the preserved historical `LeagueGameLog` method. No printing.
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

## Earlier refactor history

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

The older `src/fantrax.py` client and pre-existing tests remain untouched. They
predate this reporting workflow; the app does not use that client's different
retry/credential behavior. In particular, `tests/test_main.py` targets an older
list-printing version of main and is not a verification suite for this refactor.
