# FanTraxWinner implementation plan

Status: plan accepted; Phase 1 Fantrax client implemented with mocked tests.
Live league validation remains required before proceeding to normalization.

## Outcome and scope

At approximately 08:00 America/Toronto each day, read the current Fantrax matchup, project remaining eligible production, simulate category outcomes, evaluate legal single add/drop moves, and send a concise Telegram report. Recommendations maximize matchup win probability and preserve manually protected dynasty players. Transactions remain manual.

V1 is one Python 3.12 application with no database, server, dashboard, or LLM. Multi-day transaction search, automated injury news, dynasty valuation, trades, and historical storage follow a validated V1. Build modules as their milestones arrive rather than creating empty classes up front.

## Assumptions and early gates

1. **Fantrax contract is unverified.** Use the supplied REST v1.8 Beta endpoints, but validate authentication, response shapes, permissions, pagination, and period semantics against the actual league. Public research did not establish a complete authoritative schema. Do not invent JSON field paths.
2. **Scoring periods and roster periods differ.** Resolve each from league metadata; do not assume the same numeric ID or a Monday-to-Sunday week. Handle playoffs, extended weeks, byes, and offseason explicitly.
3. **Current percentages are insufficient.** Require exact current FGM/FGA and FTM/FTA. Rounded FG% cannot recover these. If matchup data omits them, investigate an authoritative stats endpoint or historical counted lineup/game records. Block full matchup probabilities until resolved.
4. **Unrostered does not mean immediately addable.** Waiver processing, bids, dropped-player restrictions, player-pool eligibility, and transaction limits matter. Unknown availability must be labeled conditional, never an executable recommendation.
5. **Scheduled games do not all count.** Bench/IR slots, positions, locks, game caps, and transaction effective times must constrain production. Basic legality belongs before actionable recommendations, even though multi-day optimization is deferred.
6. **Matchup victory is league-specific.** Verify category ties, precision, zero attempts, minimum attempts, and playoff tiebreakers. Winning five categories is not always identical to winning more categories than the opponent when categories tie.
7. **Injuries need a minimal V1 policy.** Use available reliable status and manual exclusions/availability overrides. Detailed news monitoring can wait; known inactive players must not automatically receive full production.
8. **Free data reliability needs evidence.** Run source smoke tests locally and on GitHub Actions before accepting the provider. A successful local request is insufficient.

## Architecture

```text
FantraxClient -> league/matchup/roster snapshot
NBADataClient + PlayerMapper -> validated player histories and schedule
ScheduleService + lineup rules -> eligible remaining player-games
ProjectionEngine -> deterministic forecast and predictive distributions
MatchupSimulator -> baseline probabilities
WaiverOptimizer -> legal alternatives and probability changes
ReportGenerator -> structured JSON + concise text
TelegramNotifier -> phone notification
```

`FantasyOptimizerApp` orchestrates this pipeline. Provider adapters own HTTP and parsing; numerical modules receive validated models and never call APIs. Keep raw responses separate from normalized objects. Pass dependencies and random generators explicitly so tests need no network.

Proposed layout:

```text
main.py
pyproject.toml
requirements.txt
config.example.yaml
src/fantrax_winner/
  app.py, config.py, models.py
  fantrax.py, nba_data.py, mapping.py
  schedule.py, lineup.py, projections.py
  simulator.py, optimizer.py, reporter.py, telegram.py
tests/fixtures/
docs/fantrax_contract.md
.github/workflows/daily.yml
```

Use requests, Pydantic, NumPy, PyYAML, nba_api, pytest, and tzdata for Windows timezone support. Add pandas only where useful for NBA data processing; SciPy only if required. Pin tested dependencies during implementation.

## Data-source recommendation

Use NBA.com data through the community-maintained `nba_api` adapter as the initial free provider candidate. Its [PlayerGameLogs interface](https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoints/playergamelogs.md) exposes game-level player statistics suitable for computing all three averaging windows locally. Retrieve batches rather than one request per player.

Use the NBA season schedule through ScheduleLeagueV2 or the NBA CDN season schedule, subject to a live schema/freshness check. Provider acceptance requires stable NBA player/team/game IDs, current team membership, complete required statistics, upcoming games, and corrected/postponed game handling. Do not use a today's-scoreboard feed as the entire remaining-week schedule.

This is a recommendation to test, not a reliability guarantee: the adapter's [release history](https://github.com/swar/nba_api/releases) documents upstream endpoint and header changes. Test repeated requests from GitHub-hosted runners; set bounded timeouts, retry transient failures, and cache within each run. If access fails, retain the adapter boundary and evaluate a replacement before continuing. Never silently substitute stale fixtures for live data. A dated local import may support development but does not satisfy unattended operation.

## Internal models

| Model | Essential fields and invariants |
| --- | --- |
| LeagueRules | League ID, scoring categories, direction, tie/precision policy, roster slots, locks, limits, waiver rules; unknown rules explicit |
| CategoryDefinition | Provider ID, canonical stat, count/ratio kind, numerator/denominator, higher/lower wins |
| ScoringPeriod | Provider ID, start/end boundaries and timezone; separate roster-period references |
| Player | Fantrax ID, optional NBA ID, name, current NBA team ID, eligible positions, availability, mapping provenance |
| Team / RosterEntry | Fantasy team ID/name; player ID, active/bench/IR status, position, effective period, drop eligibility |
| PlayerStats | FGM, FGA, FTM, FTA, PTS, REB, AST, STL, BLK, FG3M, TOV; also FG3A for shooting simulation; makes <= attempts |
| PlayerGameLog | Player/game/team IDs, date/time, minutes, box-score vector, participation status |
| ScheduledGame | Stable game ID, teams, UTC tipoff, league-local date, status, source timestamp |
| Matchup | Period, both teams, exact counted current totals, Fantrax W/L/T, snapshot timestamp, status |
| PlayerProjection | Per-game mean vector, eligible games, availability assumptions, expected totals, history/sample sizes |
| CategoryProbability | Win/tie/loss probabilities, expected final totals, classification |
| SimulationResult | Category probabilities, matchup W/T/L, modal final category record, seed/run count, uncertainty |
| WaiverRecommendation | Add/drop IDs, effective time, legality/conditions, before/after probabilities, delta, useful games |
| AnalysisReport | Baseline, ranked alternatives, coverage/freshness, exclusions, assumptions, source timestamps |

Validate required fields at adapter boundaries. Missing is distinct from zero. Preserve identifiers as strings and UTC-aware timestamps. Ratios are derived values, never additive stats.

## Fantrax client contract

Transport interface, with response parsing defined only after real payload inspection:

```python
get_leagues()  # userSecretId only where required
get_league_info(league_id, *, exclude_player_info=False)
get_team_rosters(league_id, *, roster_period=None)
get_matchup_scores(league_id, *, scoring_period=None)
get_standings(league_id)
get_player_ids(*, sport="NBA")
```

These map to the supplied `/fxea/general/getLeagues`, `getLeagueInfo`, `getTeamRosters`, `getMatchupScores`, `getStandings`, and `getPlayerIds` endpoints. Draft/ADP endpoints are deferred. Confirm whether omitted periods select current periods; do not rely on this undocumented behavior.

A normalization/service layer provides `get_my_team(team_id)`, `get_current_matchup(team_id, as_of)`, and `get_available_players(snapshot)`. Configure `FANTRAX_TEAM_ID` once; never infer ownership from a fuzzy team name. Validate that the ID belongs to the selected league.

Use a reusable session, bounded retries for transient errors, explicit timeouts, HTTP status checks, JSON/schema checks, and API error-envelope checks. Distinguish unavailable API, malformed data, unsupported settings, and valid no-matchup states. Never log credential-bearing URLs, headers, or raw exception request objects. Save sanitized fixture samples, not unrestricted raw payloads in CI logs.

## Identity and waiver mapping

Mapping priority: verified shared external ID, explicit reviewed override, then unique normalized full-name candidate. Normalize accents, punctuation, spacing, and suffixes for lookup only; preserve original names. Team membership is corroborating evidence, not a permanent identity key, because players trade. Ambiguity stays unresolved; no automatic fuzzy collision resolution.

Persist reviewed mappings in a small versioned file keyed by Fantrax ID, including NBA ID and provenance. Target at least 95% automatic mapping, but require complete coverage for contributing roster players before full probabilities. Exclude unmapped waiver candidates with a visible coverage count. Revalidate conflicting or stale mappings.

Potential candidates = complete league-eligible player pool minus the union of every roster's player IDs, including bench, IR, reserves, and minors where applicable. Verify completeness/pagination first. Then resolve free-agent/waiver status, earliest acquisition time, roster legality, and remaining adds. If the API lacks these details, use explicit dated configuration or show conditional analysis until verified.

Protected players resolve to stable Fantrax IDs. Names may be a configuration convenience, but an unresolved or ambiguous protected name is a configuration error. A protected player can never enter the drop set. Restrict initial drops to a user-approved expendable list for added dynasty control.

## Schedule and lineup treatment

Filter games by actual scoring-period boundaries and snapshot cutoff, excluding already counted games. Do not count in-progress games again; V1 can return an unsupported live-state notice on manual runs until partial-game support exists. Recheck postponements, team changes, and transaction activation times.

Produce both scheduled games and usable active-lineup games. Honor actual league slot eligibility with a deterministic feasible assignment; use the same lineup policy for baseline and alternatives. Keep locked historical contributions unchanged. For future opponent decisions, state the assumed feasible lineup policy. If future daily lineups are unavailable, label forecasts as conditional on that policy. Weekly locked leagues require different eligibility handling.

## Projection methodology

Start with configurable weights: 0.50 last 14 calendar days, 0.30 season, 0.20 last five played games. Compute averages of counting stats, including shooting makes and attempts. Exclude DNP rows from per-played-game averages; model nonparticipation separately. Explain that these windows overlap and intentionally emphasize recent performance.

For missing windows, renormalize available weights; shrink very small recent samples toward the season estimate. No history means an explicit fallback requiring review or exclusion, never fabricated zeros. Offseason/early-season use of prior-year data must be explicitly configured and labeled.

Expected remaining production is the sum over eligible games of per-game mean times participation probability. Current exact totals plus remaining means give the deterministic forecast. FG% and FT% use summed makes divided by summed attempts. Follow league zero-attempt/minimum-attempt rules.

## Monte Carlo methodology

Use approximately 10,000 trials and a configurable seed. A transparent initial predictive model is a weighted bootstrap of complete historical player box-score rows: choose a history window with the projection weights, then sample a played-game row uniformly within that window. Its expected stat vector matches the corresponding weighted averages. Apply any small-sample shrinkage by adjusting the same mixture used for the deterministic projection.

Sample participation separately for each eligible future game. Whole-row sampling preserves observed relationships among points, threes, shooting makes/attempts, and other stats; it avoids impossible independently sampled shooting totals. It assumes future played-game production resembles weighted history and does not model all shared pace, teammate, or role-change effects. Report these limitations; probabilities are model estimates, not calibrated certainty.

For each trial, sum sampled production onto immutable current totals, compute ratios, apply category direction/tie rules, then determine matchup W/T/L using verified league rules. Report probability of 5+ category wins separately if useful. Derive overall matchup probability from joint trials, never multiply marginal category probabilities. Report a modal final category record separately from the deterministic expected-stat result.

Reuse random draws by player ID, game ID, and trial across all alternatives so unchanged players/opponents have identical simulated output. At 10,000 independent trials, a probability near 50% has about 0.5 percentage-point Monte Carlo standard error; this does not measure model error. Use paired trial differences to estimate uncertainty in move impact.

## Optimizer objective

1. Generate only legal single additions into a genuine open slot or legal add/drop pairs; exclude protected and non-droppable players.
2. Apply each move at its earliest valid effective time, recompute usable games/lineups, and preserve already earned production.
3. Simulate against the same opponent scenario and calculate `delta = P(win after) - P(win baseline)`.
4. Rank by delta; use category improvements and useful game volume as explanatory secondary metrics. Dynasty protection and legality are hard constraints.
5. Return up to three alternatives, clearly identified as alternatives, not a combined plan.

Use 3 percentage points as a configurable initial recommendation threshold. For a leading move close to the threshold or another move, increase simulations and check paired uncertainty before making a strong recommendation. If no evaluated legal move clears it, report: "No waiver move provides a meaningful improvement today. Hold your roster." If coverage is incomplete, qualify the conclusion as applying to evaluated candidates.

Use configurable category labels with initial boundaries of 30%, 45%, 55%, and 70%. These explain swing categories; do not impose arbitrary category weights on top of the matchup-win objective. Strong categories still matter if a move jeopardizes them. Do not discard specialists solely because of weak overall fantasy rankings.

## Reporting, operations, and configuration

The Telegram report includes data timestamp, opponent/period, projected category record, matchup W/T/L, swing categories, best qualifying add/drop, useful games, and largest category probability changes. Save structured output locally for traceability. Include conditional availability and lineup assumptions when relevant.

Use environment variables or ignored local `.env` for FANTRAX_USER_SECRET, FANTRAX_LEAGUE_ID, FANTRAX_TEAM_ID, TELEGRAM_BOT_TOKEN, and TELEGRAM_CHAT_ID. Use YAML for weights, simulations, threshold, protection IDs, timezone, and explicit rule overrides. Validate config before fetching data.

Log structured run status from the first milestone: timestamp, phase, period/opponent, coverage, counts, simulation metadata, baseline/top move, and notification status. API failure yields a concise failure alert and nonzero exit, never a fake hold recommendation. A genuine bye/offseason yields a normal no-matchup report. Telegram failure also fails the workflow visibly. Use plain text, bounded retries, and safe message splitting; redact bot-token URLs.

## DST-safe scheduling

GitHub now supports an IANA timezone alongside cron, per its [March 2026 announcement](https://github.blog/changelog/2026-03-19-github-actions-late-march-2026-updates/). Use:

```yaml
on:
  schedule:
    - cron: '0 8 * * *'
      timezone: America/Toronto
  workflow_dispatch:
```

This replaces the specification's proposed dual-UTC workaround. Keep timezone-aware dates in the application and support manual runs at any time. Do not reject a delayed scheduled job solely because it starts after 08:00. [GitHub documents](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) that scheduled jobs can be delayed or dropped under load, so exact delivery time is not guaranteed.

Workflow: checkout, Python setup, dependency cache/install, configuration validation, analysis, notification, and visible failure. Use read-only repository permissions, a runtime limit, and a concurrency group to avoid overlapping analyses. Check account Actions allowance before rollout; set bounded runtime rather than assuming unlimited free execution. No workflow or remote setup is created in this planning stage.

## Independently testable milestones

| Step | Deliverable | Acceptance gate |
| --- | --- | --- |
| 1. Fantrax connection | Minimal package/config/logging, client, diagnostic command, contract notes | Mock timeout/auth/malformed/API-error tests; real league info, rosters, matchup payload inspected; credentials absent from logs |
| 2. Normalize matchup | Models, team and opponent/period resolution, exact totals and scoring rules | Sanitized fixtures match Fantrax UI; handle bye/offseason; percentage denominators and period semantics resolved |
| 3. Candidate pool | Complete roster union and unrostered player detection | Correct bench/IR exclusion; player-pool completeness established; free-agent versus waiver distinction documented |
| 4. NBA provider and mapping | Logs, current teams, schedule, reviewed IDs | Local and Actions smoke tests pass; contributing roster coverage complete; unresolved candidates listed |
| 5. Remaining production eligibility | Schedule/lineup service and basic transaction rules | Boundary, postponed, already-started, traded-team, slot collision, lock and effective-time tests |
| 6. Projections | Window weights and deterministic final totals | Manually reconcile five players; test missing history, weighted totals, aggregate FG%/FT%, and no remaining games |
| 7. Simulation | Reproducible category and matchup W/T/L | Known favourite/underdog/exact tie, lower-is-better TO, zero attempts, shooting invariants, convergent mean, probability sums |
| 8. Single-move optimization | Protected drops, legal alternatives, ranked deltas | Synthetic specialist improves intended matchup; protected players never dropped; no-op delta zero; unchanged draws shared; threshold/ranking tests |
| 9. Telegram | Structured report and phone message | Mock delivery/failure tests; one real end-to-end local report; incomplete data produces no recommendation |
| 10. Scheduled operation | Daily workflow and manual execution | Manual Actions run succeeds; summer/winter timezone checks; secrets redacted; failure visible |
| 11. Observation week | Daily manual review and tuning notes | Reconcile data, eligibility, and recommendation usefulness for a week; do not infer statistical calibration from seven outcomes |

Do not proceed past milestone 1 on mocks alone. If the season has no active matchup, validate historical periods when accessible and retain the current-matchup gate until real evidence exists. Mathematical tests remain offline and seeded; live smoke tests are opt-in.

## Decisions needed before Phase 1

Agree on this plan first, as requested in the specification. Then implement only milestone 1. Real connection validation will require league/team identifiers and the Fantrax secret configured locally; do not paste secrets into chat. Discover league rules from the API before asking for manual details it cannot provide. Later milestones require protected/expendable player choices and Telegram setup.
