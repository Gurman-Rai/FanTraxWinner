"""Read-only client for the Fantrax REST API v1.8 Beta.

Payloads remain dictionaries/lists until the real league's schema is verified.
No roster changes or other write operations are implemented.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
JSONPayload = dict[str, Any] | list[Any]


class FantraxError(RuntimeError):
    """An API failure whose message is safe to display without credentials."""


class FantraxConfigError(ValueError):
    """Missing or invalid local configuration."""


class FantraxClient:
    """Retrieve league data using one reusable HTTP session.

    Use ``from_env()`` to load credentials from environment/.env or .env.
    The user secret is only sent to getLeagues, in a POST body. League
    endpoints use leagueId as specified in the supplied API contract.
    """

    BASE_URL = "https://www.fantrax.com/fxea/general"
    RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        league_id: str,
        user_secret_id: str | None = None,
        *,
        timeout: tuple[float, float] = (5.0, 30.0),
        max_retries: int = 2,
        session: requests.Session | None = None,
    ) -> None:
        if not isinstance(league_id, str) or not league_id.strip():
            raise FantraxConfigError("Set FANTRAX_LEAGUE_ID before retrieving league data.")
        if user_secret_id is not None and not isinstance(user_secret_id, str):
            raise FantraxConfigError("FANTRAX_USER_SECRET must be a string.")
        if type(max_retries) is not int or not 0 <= max_retries <= 5:
            raise FantraxConfigError("max_retries must be an integer between 0 and 5.")
        if len(timeout) != 2 or any(value <= 0 for value in timeout):
            raise FantraxConfigError("Connect and read timeouts must be positive.")
        self._league_id = league_id.strip()
        self._user_secret_id = (user_secret_id or "").strip()
        self._timeout = timeout
        self._max_retries = max_retries
        self._owns_session = session is None
        self._session = session if session is not None else requests.Session()
        if self._owns_session:
            self._session.headers.update({"Accept": "application/json"})

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, **kwargs: Any) -> FantraxClient:
        """Load one env file, preserving variables already set by the shell/CI.

        Default search order: project/environment/.env, then project/.env.
        A supplied path must exist. No credentials are required on disk if
        FANTRAX_LEAGUE_ID is already set in the process environment.
        """
        if env_file is not None:
            path = Path(env_file)
            if not path.is_file():
                raise FantraxConfigError("The specified environment file does not exist.")
        else:
            path = next(
                (p for p in (PROJECT_ROOT / "environment/.env", PROJECT_ROOT / ".env")
                 if p.is_file()),
                None,
            )
        if path is not None:
            load_dotenv(path, override=False, interpolate=False, encoding="utf-8-sig")
        return cls(
            league_id=os.environ.get("FANTRAX_LEAGUE_ID", ""),
            user_secret_id=os.environ.get("FANTRAX_USER_SECRET"),
            **kwargs,
        )

    def __enter__(self) -> FantraxClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close this client's session; injected sessions remain caller-owned."""
        if self._owns_session:
            self._session.close()

    def get_leagues(self) -> JSONPayload:
        """Retrieve leagues and team ownership information for the configured user."""
        if not self._user_secret_id:
            raise FantraxConfigError("Set FANTRAX_USER_SECRET to call get_leagues().")
        return self._request(
            "getLeagues", method="POST", data={"userSecretId": self._user_secret_id}
        )

    def get_league_info(self, *, exclude_player_info: bool = False) -> JSONPayload:
        """League settings, teams, periods and player pool (included by default)."""
        params = self._league_params()
        if exclude_player_info:
            params["excludePlayerInfo"] = "true"
        return self._request("getLeagueInfo", params=params)

    def get_team_rosters(self, period: int | None = None) -> JSONPayload:
        """All team rosters; period is a roster/lineup period, not a scoring period."""
        return self._request("getTeamRosters", params=self._league_params(period))

    def get_matchup_scores(self, period: int | None = None) -> JSONPayload:
        """Matchup scores for a scoring period; omitted means provider default."""
        return self._request("getMatchupScores", params=self._league_params(period))

    def get_standings(self) -> JSONPayload:
        return self._request("getStandings", params=self._league_params())

    def get_player_ids(self, sport: str = "NBA") -> JSONPayload:
        return self._request("getPlayerIds", params={"sport": self._sport(sport)})

    def get_player_info(self, sport: str = "NBA") -> JSONPayload:
        """Basic player info / ADP; this is not a current-stat projection source."""
        return self._request("getAdp", params={"sport": self._sport(sport)})

    def get_draft_picks(self) -> JSONPayload:
        return self._request("getDraftPicks", params=self._league_params())

    def get_draft_results(self) -> JSONPayload:
        return self._request("getDraftResults", params=self._league_params())

    def get_all_information(
        self,
        *,
        roster_period: int | None = None,
        scoring_period: int | None = None,
        include_leagues: bool = False,
        include_extras: bool = False,
    ) -> dict[str, Any]:
        """Fetch the core data bundle, failing if any requested endpoint fails.

        Optional extras are ADP, draft picks and draft results. League discovery
        is optional because leagueId already identifies the selected league.
        This is a series of requests, not an atomic provider snapshot. Missing
        periods use provider defaults; their meaning must be verified before
        this data feeds a matchup forecast.
        """
        if include_leagues and not self._user_secret_id:
            raise FantraxConfigError("Set FANTRAX_USER_SECRET to include league discovery.")
        result: dict[str, Any] = {
            "fetch_started_at": datetime.now(timezone.utc).isoformat(),
            "requested_roster_period": roster_period,
            "requested_scoring_period": scoring_period,
        }
        if include_leagues:
            result["leagues"] = self.get_leagues()
        result["league_info"] = self.get_league_info()
        result["team_rosters"] = self.get_team_rosters(roster_period)
        result["matchup_scores"] = self.get_matchup_scores(scoring_period)
        result["standings"] = self.get_standings()
        result["player_ids"] = self.get_player_ids()
        if include_extras:
            result["player_info"] = self.get_player_info()
            result["draft_picks"] = self.get_draft_picks()
            result["draft_results"] = self.get_draft_results()
        result["fetch_completed_at"] = datetime.now(timezone.utc).isoformat()
        return result

    def redact(self, value: Any) -> Any:
        """Make a copy safe from known credential values before saving diagnostics.

        League payloads may still contain personal/team information. Keep
        diagnostic files local and review them before sharing.
        """
        if isinstance(value, dict):
            return {
                self.redact(key): (
                    "[REDACTED]"
                    if str(key).lower().replace("_", "") in {
                        "usersecretid", "usersecret", "fantraxusersecret", "token",
                        "password", "authorization", "cookie",
                    }
                    else self.redact(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, str):
            for credential in (self._user_secret_id, self._league_id):
                if credential:
                    value = value.replace(credential, "[REDACTED]")
        return value

    @staticmethod
    def _sport(sport: str) -> str:
        if not isinstance(sport, str) or not sport.strip():
            raise FantraxConfigError("sport must be a nonempty string.")
        return sport.strip().upper()

    def _league_params(self, period: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"leagueId": self._league_id}
        if period is not None:
            if type(period) is not int or period < 1:
                raise FantraxConfigError("period must be a positive integer or None.")
            params["period"] = period
        return params

    def _request(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> JSONPayload:
        for attempt in range(self._max_retries + 1):
            logger.info("Fantrax request endpoint=%s attempt=%d", endpoint, attempt + 1)
            try:
                response = self._session.request(
                    method,
                    f"{self.BASE_URL}/{endpoint}",
                    params=params,
                    data=data,
                    timeout=self._timeout,
                    allow_redirects=False,
                )
            except (requests.Timeout, requests.ConnectionError):
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise FantraxError(
                    f"{endpoint}: connection failed or timed out after {attempt + 1} attempts."
                ) from None
            except requests.RequestException:
                raise FantraxError(f"{endpoint}: request failed.") from None

            try:
                if response.status_code in self.RETRY_STATUSES and attempt < self._max_retries:
                    # Bounded backoff; no unbounded Retry-After wait in daily jobs.
                    retry = True
                else:
                    retry = False
                    if not 200 <= response.status_code < 300:
                        raise FantraxError(
                            f"{endpoint}: HTTP {response.status_code}. "
                            "Check Fantrax availability and league access."
                        )
                    try:
                        payload = response.json()
                    except ValueError:
                        raise FantraxError(f"{endpoint}: response was not valid JSON.") from None
                    if not isinstance(payload, (dict, list)):
                        raise FantraxError(f"{endpoint}: expected a JSON object or array.")
                    if isinstance(payload, dict) and (
                        payload.get("error")
                        or payload.get("errors")
                        or payload.get("success") is False
                        or str(payload.get("status", "")).lower() in {"error", "failed", "failure"}
                    ):
                        # Do not echo arbitrary server messages: they can contain secrets.
                        raise FantraxError(f"{endpoint}: Fantrax returned an API error.")
                    logger.info("Fantrax response endpoint=%s status=ok", endpoint)
                    return payload
            finally:
                response.close()
            if retry:
                time.sleep(2 ** attempt)
        raise AssertionError("Retry loop must return or raise.")
