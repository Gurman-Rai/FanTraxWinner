# =========================
# CONFIG
# =========================

LEAGUE_ID = "0vypzr6smssls5m0"
MY_TEAM_ID = "g5y12rlqmsxeqlfb"

NBA_SEASON = "2026-27"
NBA_STATS_SEASON = "2025-26"  # Per-game averages; independent of the schedule season.
NBA_WEEK = 1  # NBA schedule weekNumber, independent of the Fantrax scoring period.


# =========================
# DATE TESTING
# =========================

# Leave as None to use Fantrax scoring-period dates.
# Change these manually when testing.

# Dates must be quoted strings, not subtraction expressions.
MANUAL_START_DATE = "2026-01-05"
MANUAL_END_DATE = "2026-01-11"

# For historical testing, also set NBA_SEASON = "2025-26":
# MANUAL_START_DATE = "2026-01-05"
# MANUAL_END_DATE = "2026-01-11"

# Set both dates to None to use the Fantrax scoring period.
