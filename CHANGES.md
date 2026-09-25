# CHANGES - Agent Dion/Cox audit & fix (2026-09-25)

## What this repo is
Two standalone parlay engines: **Agent Dion** (NFL, `models/agent_dion_nfl.py`)
and **Agent Cox** (MLB + NCAAF, `models/agent_cox_mlb_ncaaf.py`), plus a
unified runner (`scripts/dion_cox_merger.py`). They pull live slates from
ESPN / MLB StatsAPI, score spread-moneyline-total markets per game, and build
4-5 leg parlays ranked by model expected value.

## Bugs fixed (were 100% broken before)
- **Dion's ESPN parser was wrong**: read `game['home']`/`game['away']`/`game['odds']`
  which don't exist in the ESPN API. Every game parsed as N/A. Rewrote to parse
  `competitions[0].competitors` (homeAway + team) and `odds` (spread/total/moneylines).
- **Cox's MLB fetch was dead**: iterated the top-level StatsAPI dict instead of
  `dates[].games[]`, so it always raised TypeError and returned []. Rewrote to the
  real structure, filtering on `status.detailedState` and using `gameDate`/`gamePk`.
- **Cox's NCAAF parser was wrong**: read `competitions[0]['home']` (doesn't exist),
  silently producing N/A teams. Same competitor-based rewrite as Dion.
- **NFL week hardcoded to 1** (real week: 3). Now read from the ESPN response,
  with a date-based fallback (2026 kickoff Thu 2026-09-10).
- **"Today only" game filter**: missed every game not played today. Now uses the
  week's upcoming slate (NFL/NCAAF) and today's playable schedule (MLB).

## Logic fixed (was wrong, not just broken)
- **Payout math was nonsense** (`1.5 x (confidence/50)^legs` -> ~$428 on a 4-leg).
  Now uses real American-odds conversion per leg, defaulting to standard -110
  (4-leg = ~$1,328, 5-leg = ~$2,536 on $100 - matches real sportsbooks).
- **Confidence was `random.randint` noise** relabeled as a "learning system".
  Now deterministic (sha256-seeded per game+market, reproducible runs) and
  genuinely calibrating: `record_result()` grades picks into `data/results.json`,
  and baselines shift toward your observed hit rate once 10+ picks per market exist.
- **Parlay builder combinatorial explosion** (all high-confidence picks ->
  ~700k combos). Now caps the pool at the top 24 by confidence.
- **Correlated legs**: parlays could stack spread+moneyline+total from the same
  game. Now one market per game per parlay, max 2 legs of the same market.
- **Inconsistent thresholds** (Dion 65, Cox undocumented 62). Both 65 now.
- **Picks had no lines or selections** (just "spread 68%"). Now every leg shows
  the real line from the feed (e.g. "Spread Bengals +3.5", "O/U 50.5") with
  stated conventions (favorite/home/Over) when the feed lacks a line.

## Added (was referenced in docs but missing)
- `scripts/dion_cox_merger.py` - the unified runner QUICK_START promised
- `requirements.txt`, `data/`, `output/`, `logs/` scaffolding

## Honesty pass
- Removed fabricated "Week 1: 6-4 (60%)" history claims from README,
  QUICK_START, and the Dion banner. History starts with your first graded pick.
- Reports now state conventions and that confidence/EV are model estimates,
  not a proven edge. Added responsible-betting notes.
- Removed dead code (unused learning_rules dicts, never-called frozen-card path
  is now actually wired: the top Dion card freezes pre-kickoff automatically).

## Tests
- `python3 -m py_compile` on all three scripts: OK
- Live runs 2026-09-25: Dion -> 15 upcoming Week-3 games, 3 parlays, report saved;
  Cox -> 16 MLB + 18 NCAAF games, 5 parlays, report saved; merger -> unified
  ranked report saved. Determinism check: two consecutive runs byte-identical.

## Deliberately left alone
- `config/settings.json` multi-sport flags (nba/nhl/mls/tennis have no agents;
  harmless config, would need new agents to matter).
- No player-prop legs: no props data source exists; fabricating prop lines would
  be dishonest. Add a props feed (e.g. the-odds-api player props) to enable them.
- No real-odds fetching per game beyond what the scoreboard feed includes;
  -110 default is standard and labeled.
- `record_result()` grading is manual - auto-grading needs a scores/results feed.

## Real history recovered (2026-09-25)
Kenneth uploaded his Termux/phone archives. The Week 1 Master Ledger
(`Agent_Dion_2026_Week1_Master_Ledger_20_hv2e.docx`) contains genuinely graded
picks with actuals. Converted the STRICT audit record only (4-4) into
`data/results.json` — the 8 pregame-frozen picks:
- W1 NE@SEA: Stevenson UNDER 55.5 rush (actual 51) WIN
- W1 SF@LA: Game total UNDER 48.5 (34) WIN; Stafford OVER 263.5 pass (155) LOSS;
  Puka OVER 90.5 rec (74) LOSS; Kittle OVER 37.5 rec (12) LOSS;
  CMC OVER 60.5 rush (68) WIN; Kyren OVER 56.5 rush (41) LOSS;
  Corum OVER 35.5 rush (54) WIN
Deliberately EXCLUDED from the learning loop (lookahead bias): the 4 Game-1
retrospective replays (game total, SEA moneyline, JSN over, Price under —
all marked RETROSPECTIVE_REPLAY in the ledger), the 3 Game-2 PASS diagnostics
(directionally correct but not qualified picks), and the Darnold injury
no-grade. The ledger's "working 6-4" keeps user-kept retrospective picks;
the learning system uses strict 4-4. Calibration needs 10+ graded per market;
with 8 spread across markets it stays on defaults for now — correct behavior.
Also archived: `data/week1/` (seed board, game lines, market benchmark, player
props CSVs), `data/week2/` (Thu + Sunday game lines/props inputs,
`refresh_dion_odds.py` — the Odds-API odds refresher; needs ODDS_API_KEY).
Note: the uploaded Week-1 sqlite (`agent_dion.sqlite3`) had EMPTY picks and
weekly_summary tables (market_weights only, 0 observations) — the docx ledger
is the real record, not the db. Week 2 has inputs but no graded results yet.
