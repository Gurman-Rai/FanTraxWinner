import json
import logging
from unittest.mock import Mock

import pytest
import requests

from src.fantrax import FantraxClient, FantraxConfigError, FantraxError


def response(payload=None, status=200):
    result = Mock(status_code=status)
    result.json.return_value = {"example": "data"} if payload is None else payload
    return result


@pytest.fixture
def session():
    result = Mock(spec=requests.Session)
    result.headers = {}
    result.request.return_value = response()
    return result


@pytest.fixture
def client(session):
    return FantraxClient("league-test-123", "secret-test-456", session=session, max_retries=0)


@pytest.mark.parametrize("method,endpoint,params", [
    ("get_league_info", "getLeagueInfo", {"leagueId": "league-test-123"}),
    ("get_team_rosters", "getTeamRosters", {"leagueId": "league-test-123"}),
    ("get_matchup_scores", "getMatchupScores", {"leagueId": "league-test-123"}),
    ("get_standings", "getStandings", {"leagueId": "league-test-123"}),
    ("get_player_ids", "getPlayerIds", {"sport": "NBA"}),
    ("get_player_info", "getAdp", {"sport": "NBA"}),
    ("get_draft_picks", "getDraftPicks", {"leagueId": "league-test-123"}),
    ("get_draft_results", "getDraftResults", {"leagueId": "league-test-123"}),
])
def test_endpoint_contract(client, session, method, endpoint, params):
    assert getattr(client, method)() == {"example": "data"}
    session.request.assert_called_once_with(
        "GET", f"{client.BASE_URL}/{endpoint}", params=params, data=None,
        timeout=(5.0, 30.0), allow_redirects=False,
    )


def test_leagues_secret_is_in_post_body_only(client, session):
    client.get_leagues()
    call = session.request.call_args
    assert call.args[0] == "POST"
    assert call.kwargs["data"] == {"userSecretId": "secret-test-456"}
    assert call.kwargs["params"] is None
    assert "secret-test-456" not in call.args[1]


def test_optional_parameters(client, session):
    client.get_league_info(exclude_player_info=True)
    assert session.request.call_args.kwargs["params"]["excludePlayerInfo"] == "true"
    client.get_team_rosters(period=6)
    assert session.request.call_args.kwargs["params"]["period"] == 6
    client.get_matchup_scores(period=2)
    assert session.request.call_args.kwargs["params"]["period"] == 2


@pytest.mark.parametrize("period", [0, -1, "2", True])
def test_invalid_period_never_sends_request(client, session, period):
    with pytest.raises(FantraxConfigError):
        client.get_team_rosters(period)
    session.request.assert_not_called()


def test_all_information_keeps_periods_separate(client, session):
    result = client.get_all_information(roster_period=6, scoring_period=2,
                                        include_leagues=True, include_extras=True)
    assert {"league_info", "leagues", "team_rosters", "matchup_scores", "standings",
            "player_ids", "player_info", "draft_picks", "draft_results"} <= result.keys()
    calls = {call.args[1].rsplit("/", 1)[-1]: call.kwargs for call in session.request.call_args_list}
    assert calls["getTeamRosters"]["params"]["period"] == 6
    assert calls["getMatchupScores"]["params"]["period"] == 2


@pytest.mark.parametrize("status", [301, 401, 403, 404, 429, 500])
def test_http_failures_do_not_expose_response(client, session, status):
    session.request.return_value = response({"message": "secret-test-456"}, status)
    with pytest.raises(FantraxError, match=f"HTTP {status}") as exc:
        client.get_league_info()
    assert "secret-test-456" not in str(exc.value)
    session.request.return_value.close.assert_called_once()


@pytest.mark.parametrize("payload", [
    {"error": "secret-test-456"}, {"errors": ["bad"]}, {"success": False},
    {"status": "ERROR"}, "error page", 12,
])
def test_rejects_error_envelopes_and_invalid_shapes(client, session, payload):
    session.request.return_value = response(payload)
    with pytest.raises(FantraxError) as exc:
        client.get_league_info()
    assert "secret-test-456" not in str(exc.value)


def test_invalid_json(client, session):
    session.request.return_value.json.side_effect = ValueError("secret-test-456")
    with pytest.raises(FantraxError, match="not valid JSON"):
        client.get_league_info()


@pytest.mark.parametrize("payload", [{}, [], {"error": None, "teams": []}])
def test_empty_responses_are_preserved_for_later_schema_validation(client, session, payload):
    session.request.return_value = response(payload)
    assert client.get_matchup_scores() == payload


def test_transient_failures_retry_and_close_responses(session, monkeypatch):
    sleep = Mock()
    monkeypatch.setattr("src.fantrax.time.sleep", sleep)
    unavailable = response(status=503)
    session.request.side_effect = [requests.Timeout("secret"), unavailable, response()]
    client = FantraxClient("league", session=session, max_retries=2)
    assert client.get_standings() == {"example": "data"}
    assert session.request.call_count == 3
    unavailable.close.assert_called_once()
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]


def test_retry_exhaustion_and_safe_logs(session, monkeypatch, caplog):
    monkeypatch.setattr("src.fantrax.time.sleep", Mock())
    session.request.side_effect = requests.ConnectionError("secret-test-456 league-test-123")
    client = FantraxClient("league-test-123", "secret-test-456", session=session)
    with caplog.at_level(logging.INFO), pytest.raises(FantraxError) as exc:
        client.get_leagues()
    assert session.request.call_count == 3
    for sensitive in ("secret-test-456", "league-test-123"):
        assert sensitive not in str(exc.value) + caplog.text
    assert exc.value.__suppress_context__


def test_client_error_does_not_retry(session, monkeypatch):
    sleep = Mock()
    monkeypatch.setattr("src.fantrax.time.sleep", sleep)
    session.request.return_value = response(status=403)
    with pytest.raises(FantraxError):
        FantraxClient("league", session=session).get_standings()
    session.request.assert_called_once()
    sleep.assert_not_called()


def test_env_file_preserves_existing_environment(tmp_path, monkeypatch, session):
    env = tmp_path / ".env"
    env.write_text("FANTRAX_LEAGUE_ID=file-league\nFANTRAX_USER_SECRET=file-secret\n")
    monkeypatch.setenv("FANTRAX_LEAGUE_ID", "shell-league")
    monkeypatch.delenv("FANTRAX_USER_SECRET", raising=False)
    client = FantraxClient.from_env(env, session=session)
    client.get_league_info()
    assert session.request.call_args.kwargs["params"]["leagueId"] == "shell-league"
    client.get_leagues()
    assert session.request.call_args.kwargs["data"]["userSecretId"] == "file-secret"


def test_default_environment_folder(tmp_path, monkeypatch, session):
    monkeypatch.setattr("src.fantrax.PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("FANTRAX_LEAGUE_ID", raising=False)
    monkeypatch.delenv("FANTRAX_USER_SECRET", raising=False)
    (tmp_path / "environment").mkdir()
    (tmp_path / "environment/.env").write_text("FANTRAX_LEAGUE_ID=folder-league\n")
    (tmp_path / ".env").write_text("FANTRAX_LEAGUE_ID=root-league\n")
    client = FantraxClient.from_env(session=session)
    client.get_league_info()
    assert session.request.call_args.kwargs["params"]["leagueId"] == "folder-league"


def test_missing_config(session, tmp_path):
    with pytest.raises(FantraxConfigError, match="FANTRAX_LEAGUE_ID"):
        FantraxClient("", session=session)
    with pytest.raises(FantraxConfigError, match="does not exist"):
        FantraxClient.from_env(tmp_path / "missing.env", session=session)
    client = FantraxClient("league", session=session)
    with pytest.raises(FantraxConfigError, match="FANTRAX_USER_SECRET"):
        client.get_leagues()
    session.request.assert_not_called()


def test_redaction_is_recursive_and_does_not_modify_payload(client):
    payload = {"userSecretId": "other-secret", "items": [{"url": "value=secret-test-456"}],
               "league": "league-test-123"}
    safe = client.redact(payload)
    assert "other-secret" not in json.dumps(safe)
    assert "secret-test-456" not in json.dumps(safe)
    assert "league-test-123" not in json.dumps(safe)
    assert payload["league"] == "league-test-123"


def test_session_ownership(session, monkeypatch):
    with FantraxClient("league", session=session):
        pass
    session.close.assert_not_called()
    monkeypatch.setattr("src.fantrax.requests.Session", Mock(return_value=session))
    with FantraxClient("league"):
        pass
    session.close.assert_called_once()
