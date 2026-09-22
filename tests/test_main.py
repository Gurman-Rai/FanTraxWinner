from unittest.mock import MagicMock

import pytest

import main
from src.fantrax import FantraxError


@pytest.fixture
def payloads():
    return (
        {"teamInfo": {"t1": {"name": "Team One"}, "t2": {"name": "Team Two"}}},
        {"rosters": {
            "t1": {"rosterItems": [
                {"id": "p1", "position": "PG", "status": "ACTIVE"},
                {"id": "p2", "position": "C", "status": "RESERVE"},
                {"id": "missing", "position": "PF", "status": "MINORS"}]},
            "t2": {"rosterItems": []}}},
        {"p1": {"name": "Player One", "team": "BOS"},
         "p2": {"name": "Player Two", "team": "TOR"}},
    )


def test_lists_join_players_and_preserve_all_statuses(payloads):
    teams, owners, rosters = main.build_league_lists(*payloads)
    assert len(teams) == len(owners) == len(rosters) == 2
    assert teams[0] == {"team_id": "t1", "team_name": "Team One"}
    assert owners[0]["owner_names"] == []
    assert owners[0]["source"] == "not provided by Fantrax"
    assert [p["name"] for p in rosters[0]["players"]] == [
        "Player One", "Player Two", "Unknown player (missing)"]
    assert [p["status"] for p in rosters[0]["players"]] == ["ACTIVE", "RESERVE", "MINORS"]
    assert rosters[1]["players"] == []


def test_known_coowners(payloads):
    _, owners, _ = main.build_league_lists(*payloads, owner_names_by_team={"t1": ["A", "B"]})
    assert owners[0]["owner_names"] == ["A", "B"]


def test_missing_roster_is_not_an_empty_roster(payloads):
    del payloads[1]["rosters"]["t2"]
    with pytest.raises(FantraxError, match="Missing roster"):
        main.build_league_lists(*payloads)


def test_fetch_and_console_output(payloads, monkeypatch, capsys):
    client = MagicMock()
    client.__enter__.return_value = client
    client.get_league_info.return_value = payloads[0]
    client.get_team_rosters.return_value = payloads[1]
    client.get_player_ids.return_value = payloads[2]
    monkeypatch.setattr(main, "FantraxClient", MagicMock(return_value=client))
    assert main.main() == 0
    output = capsys.readouterr().out
    assert all(label in output for label in ("TEAMS", "OWNERS", "PLAYERS BY TEAM", "Player One"))
    client.get_team_rosters.assert_called_once_with(period=None)


def test_api_failure(monkeypatch, capsys):
    monkeypatch.setattr(main, "FantraxClient", MagicMock(side_effect=FantraxError("failed")))
    assert main.main() == 1
    assert "Could not retrieve" in capsys.readouterr().out
