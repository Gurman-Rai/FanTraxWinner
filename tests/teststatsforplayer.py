from nba_api.stats.endpoints import leaguedashplayerstats
import pandas as pd


NBA_SEASON = "2025-26"

PLAYERS_TO_TEST = [
    "Shai Gilgeous-Alexander",
    "Trae Young",
    "Jalen Duren",
    "Stephen Curry",
    "Jayson Tatum",
]


def get_player_stats():
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season=NBA_SEASON,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )

    df = stats.get_data_frames()[0]

    return df


def test_players():

    df = get_player_stats()

    wanted_columns = [
        "PLAYER_NAME",
        "TEAM_ABBREVIATION",
        "PTS",
        "REB",
        "AST",
        "STL",
        "BLK",
        "FG3M",
        "FG_PCT",
        "FT_PCT",
        "TOV",
    ]

    available_columns = [
        column
        for column in wanted_columns
        if column in df.columns
    ]

    print()
    print("=" * 100)
    print("NBA PLAYER SEASON AVERAGES")
    print("=" * 100)

    for player_name in PLAYERS_TO_TEST:

        player_row = df[
            df["PLAYER_NAME"] == player_name
        ]

        if player_row.empty:
            print(f"\nNOT FOUND: {player_name}")
            continue

        player = player_row.iloc[0]

        print()
        print("-" * 100)
        print(player_name)
        print("-" * 100)

        for column in available_columns:

            value = player[column]

            print(
                f"{column:<20}"
                f"{value}"
            )


if __name__ == "__main__":
    test_players()