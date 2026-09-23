from nba_api.stats.endpoints import scheduleleaguev2


NBA_SEASON = "2026-27"

# Change this to 1, 2, 3, etc.
NBA_WEEK = 1


def get_games_by_team(week_number: int) -> dict[str, int]:

    schedule = scheduleleaguev2.ScheduleLeagueV2(
        season=NBA_SEASON
    )

    games_df = schedule.get_data_frames()[0]

    # Only games belonging to the selected NBA week
    week_games = games_df[
        games_df["weekNumber"] == week_number
    ]

    games_by_team = {}

    for _, game in week_games.iterrows():

        home_team = game["homeTeam_teamTricode"]
        away_team = game["awayTeam_teamTricode"]

        games_by_team[home_team] = (
            games_by_team.get(home_team, 0) + 1
        )

        games_by_team[away_team] = (
            games_by_team.get(away_team, 0) + 1
        )

    return games_by_team


def print_week(week_number: int):

    games_by_team = get_games_by_team(week_number)

    print()
    print("=" * 40)
    print(f"NBA WEEK {week_number} GAME COUNTS")
    print("=" * 40)

    print(f"{'TEAM':<10}{'GAMES':>10}")
    print("-" * 40)

    for team in sorted(games_by_team):
        print(
            f"{team:<10}"
            f"{games_by_team[team]:>10}"
        )

    print("-" * 40)

    total_games = sum(games_by_team.values()) // 2

    print(f"Teams: {len(games_by_team)}")
    print(f"Total NBA Games: {total_games}")

    print("=" * 40)


if __name__ == "__main__":
    print_week(NBA_WEEK)