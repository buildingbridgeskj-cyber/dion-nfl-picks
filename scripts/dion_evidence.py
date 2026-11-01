#!/usr/bin/env python3
"""Evidence-based NFL player-prop research. Uncalibrated; NO betting automation.

Recent ESPN box scores -> player game logs, team totals, and opponent allowance.
Genuine DraftKings event quotes -> break-even probabilities and estimated edges.
Fail closed when data is absent. Backtesting/calibration required before real bets.
"""
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import time

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
CACHE = Path(__file__).resolve().parents[1] / "data" / "dion_evidence_cache"
STAT_MAP = {
    "Passing yards": ("passing", "yds"),
    "Rushing yards": ("rushing", "yds"),
    "Receiving yards": ("receiving", "yds"),
    "Receptions": ("receiving", "rec"),
    "Passing TDs": ("passing", "td"),
    "Anytime TD": ("touchdowns", "td"),
}
FLOORS = {"Passing yards": 50, "Rushing yards": 18, "Receiving yards": 17,
          "Receptions": 1.7, "Passing TDs": 0.9}


def fetch(path, params=None, ttl=86400):
    CACHE.mkdir(parents=True, exist_ok=True)
    key = path.replace("/", "_") + "_" + str(sorted((params or {}).items()))
    import hashlib
    name = hashlib.sha256(key.encode()).hexdigest() + ".json"
    out = CACHE / name
    if out.exists() and time.time() - out.stat().st_mtime < ttl:
        try:
            return json.loads(out.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    url = BASE + "/" + path + ("?" + urlencode(params) if params else "")
    req = Request(url, headers={"User-Agent": "AgentDionResearch/1.0"})
    with urlopen(req, timeout=22) as resp:
        data = json.load(resp)
    out.write_text(json.dumps(data), encoding="utf-8")
    return data


def stat_numeric(value):
    try:
        value = str(value).replace(",", "").strip()
        if not value or "/" in value or value in ("--", "N/A"):
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def extract_boxscore(payload):
    """Return name/team/category stats; unknown layouts produce no fictitious 0s."""
    box = payload.get("boxscore") or {}
    ids = {str(t.get("team", {}).get("id")): t.get("team", {}).get("abbreviation")
           for t in box.get("teams", [])}
    players = defaultdict(dict)
    totals = defaultdict(float)
    for group in box.get("players", []):
        team_info = group.get("team") or {}
        team = team_info.get("abbreviation") or ids.get(str(team_info.get("id")))
        if not team:
            continue
        for cat in group.get("statistics", []):
            name = (cat.get("name") or cat.get("displayName") or "").lower()
            if "pass" in name:
                category = "passing"
            elif "rush" in name:
                category = "rushing"
            elif "receiv" in name:
                category = "receiving"
            else:
                continue
            labels = [str(v).strip().lower() for v in cat.get("labels", [])]
            for entry in cat.get("athletes", []):
                athlete = entry.get("athlete") or {}
                player = (athlete.get("fullName") or athlete.get("displayName") or "").strip().casefold()
                values = entry.get("stats") or []
                if not player or not isinstance(values, list):
                    continue
                candidates = {}
                if labels and len(labels) == len(values):
                    for key, value in zip(labels, values):
                        if key in ("yds", "yards") and "yds" not in candidates:
                            candidates["yds"] = stat_numeric(value)
                        if key in ("td", "tds") and "td" not in candidates:
                            candidates["td"] = stat_numeric(value)
                        if key in ("rec", "receptions"):
                            candidates["rec"] = stat_numeric(value)
                elif category == "passing" and len(values) == 5:
                    # ESPN documented five-column compact passing layout.
                    candidates["yds"] = stat_numeric(values[0])
                    candidates["td"] = stat_numeric(values[2])
                for metric, value in candidates.items():
                    if value is None:
                        continue
                    players[(team, player)][(category, metric)] = value
                    totals[(team, category, metric)] += value
    # Anytime TD covers offensive rush + receiving only; returning and defensive
    # scores aren't captured by these categories, so avoid suggesting this prop.
    return dict(players), dict(totals)


def finished_events(team, target, season, limit=8):
    data = fetch(f"teams/{team}/schedule", {"season": season}, ttl=21600)
    events = []
    cutoff = datetime.fromisoformat(target).replace(tzinfo=timezone.utc)
    for ev in data.get("events", []):
        try:
            stamp = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        status = ev.get("status") or {}
        completed = status.get("type", {}).get("completed")
        if completed is None:
            comps = ev.get("competitions") or []
            completed = bool(comps and comps[0].get("status", {}).get("type", {}).get("completed"))
        if completed and stamp < cutoff:
            events.append((stamp, str(ev["id"])))
    events.sort(reverse=True)
    return events[:limit]


def collect_history(games, target, max_games=8):
    """Returns per-team, per-player sequential samples; no lookahead."""
    season = int(target[:4])
    team_events = {}
    warnings = []
    for g in games:
        for team in (g["home_abbr"], g["away_abbr"]):
            if team in team_events:
                continue
            try:
                team_events[team] = finished_events(team, target, season, max_games)
            except Exception as ex:
                team_events[team] = []
                warnings.append(f"{team} schedule unavailable: {type(ex).__name__}")
    summaries = {}
    for _, ev in sorted({item for history in team_events.values() for item in history}):
        try:
            summaries[ev] = extract_boxscore(fetch("summary", {"event": ev}, ttl=259200))
        except Exception:
            continue
    player_games = defaultdict(list)
    team_games = defaultdict(list)
    for team, history in team_events.items():
        for stamp, event_id in sorted(history):
            data = summaries.get(event_id)
            if not data:
                continue
            players, totals = data
            for (t, player), metrics in players.items():
                if t == team:
                    player_games[(team, player)].append((stamp, metrics))
            others = [t for t, category, metric in totals if t != team]
            opposing_team = others[0] if others else None
            team_games[team].append((stamp, totals, team, event_id, opposing_team))
    return player_games, team_games, team_events, warnings


def last_values(player_games, team, player, stat, target):
    key = STAT_MAP.get(stat)
    if not key:
        return []
    samples = []
    for stamp, metrics in player_games.get((team, player.casefold()), []):
        if key in metrics:
            samples.append((stamp, metrics[key]))
    return samples[-10:]


def opponent_factor(team, opponent, market, team_games, team_events):
    """Cap opponent allowed per-game impact to ±5%; require >=4 valid games."""
    key = STAT_MAP.get(market)
    if not key or market == "Anytime TD":
        return 1.0, False
    own = [totals.get((team, *key)) for _, totals, _, _, _ in team_games.get(team, [])]
    own = [v for v in own if v is not None and v > 0]
    allowed = [
        totals.get((other, *key))
        for _, totals, _, _, other in team_games.get(opponent, [])
        if other
    ]
    allowed = [v for v in allowed if v is not None and v > 0]
    if len(allowed) < 4 or len(own) < 4:
        return 1.0, False
    own_avg = statistics.mean(own)
    allow_avg = statistics.mean(allowed)
    if own_avg <= 0:
        return 1.0, False
    ratio = max(.90, min(1.10, allow_avg / own_avg))
    # Half-weighted ratio only; noisy aggregate defense, not position-level grades.
    return 1 + .5 * (ratio - 1), True


def injury_status(roster_entries, team, name):
    """ESPN roster-derived tag; NOT a replacement for final inactive verification."""
    status = (roster_entries.get((team, name.casefold())) or "").lower()
    if any(w in status for w in ("reserve", "out", "suspend", "pup", "inactive")):
        return "OUT/IR"
    if "doubtful" in status:
        return "DOUBTFUL"
    if "questionable" in status:
        return "QUESTIONABLE"
    return "UNVERIFIED ACTIVE"


def estimate_candidate(item, player_games, team_games, team_events, roster_entries, target):
    """Estimate one quoted market side from past actuals; never claim calibration."""
    p = dict(item)
    market = p["market"]
    p["sample"] = 0
    p["last5"] = "N/A"
    p["last10"] = "N/A"
    p["projection"] = None
    p["model_pct"] = None
    p["edge_pct"] = None
    p["elite_score"] = None
    p["status"] = "PASS: insufficient evidence"
    p["injury"] = injury_status(roster_entries, p["team"], p["player"])
    try:
        threshold = float(p["line"])
    except (ValueError, TypeError):
        threshold = 0.5 if market == "Anytime TD" else None
    samples = last_values(player_games, p["team"], p["player"], market, target)
    values = [float(v) for _, v in samples]
    n = len(values)
    p["sample"] = n
    if p["injury"] in ("OUT/IR", "DOUBTFUL"):
        p["status"] = "PASS: injured/inactive"
        return p
    if market == "Anytime TD":
        p["status"] = "PASS: no verified full offensive/return TD attribution"
        return p
    if n < 5 or threshold is None or p["selection"] not in ("Over", "Under"):
        return p
    side = p["selection"]
    def hit(v):
        return v > threshold if side == "Over" else v < threshold
    # Pushes neither count as wins nor losses; indicate denominators.
    recent = values[-5:]
    p["last5"] = f"{sum(hit(v) for v in recent)}/{len(recent)}"
    p["last10"] = f"{sum(hit(v) for v in values)}/{n}"
    forecast = .65 * statistics.mean(recent) + .35 * statistics.mean(values)
    opponent = p.get("opponent", "")
    adj, matchup_ready = opponent_factor(p["team"], opponent, market, team_games, team_events)
    forecast *= adj
    p["defense_adjustment_pct"] = round((adj - 1) * 100, 1) if matchup_ready else None
    sd = statistics.stdev(values) if n > 1 else 0.0
    sd = max(sd, FLOORS.get(market, 1), abs(forecast) * .22)
    p["projection"] = round(forecast, 1)
    z = (threshold - forecast) / sd
    over_p = .5 * math.erfc(z / math.sqrt(2))
    raw_p = over_p if side == "Over" else 1 - over_p
    try:
        price = float(p["odds"])
        break_even = (-price / (100 - price)) if price < 0 else (100 / (price + 100))
    except (ValueError, TypeError, ZeroDivisionError):
        p["status"] = "PASS: odds missing"
        return p
    if not 0 < break_even < 1:
        p["status"] = "PASS: invalid price"
        return p
    fair_market = p.get("market_prob")
    if fair_market is None:
        fair_market = break_even
    # Uncalibrated model: aggressively shrink toward vig-removed market,
    # especially at small sample sizes. Never treat this as a proven EV.
    model_weight = min(.60, .20 + .04 * n)
    estimate = model_weight * raw_p + (1 - model_weight) * fair_market
    p["model_pct"] = round(100 * estimate, 1)
    edge = estimate - break_even
    p["edge_pct"] = round(edge * 100, 1)
    # Evidence-quality / prioritization score, not probability of success.
    # No fixed starting 96/99; losses can still occur even on high ratings.
    hit_rate = sum(hit(v) for v in recent) / len(recent)
    count_component = min(25, n * 3)
    signal_component = min(15, int(abs(hit_rate - .5) * 22))
    edge_component = max(0, min(30, round(160 * edge)))
    days_since = (datetime.fromisoformat(target).replace(tzinfo=timezone.utc) - samples[-1][0]).days
    freshness_component = 8 if days_since <= 16 else 3
    p["elite_score"] = min(99, int(10 + count_component + signal_component + edge_component + freshness_component + (5 if matchup_ready else 0)))
    if p["injury"] == "QUESTIONABLE":
        p["elite_score"] = min(p["elite_score"], 55)
        p["status"] = "HOLD: questionable"
    elif n < 6 or edge < .05:
        p["status"] = "PASS: no supported 5% edge"
    else:
        p["status"] = "REVIEW ONLY: uncalibrated edge; verify inactives & line"
    return p


def roster_health_from_api(games):
    """Roster is current only to refresh period; absence from injury list != active."""
    result = {}
    for team in {x for g in games for x in (g["home_abbr"], g["away_abbr"])}:
        try:
            data = fetch(f"teams/{team}/roster", ttl=1800)
        except Exception:
            continue
        def walk(items):
            if isinstance(items, list):
                for value in items:
                    walk(value)
            elif isinstance(items, dict):
                a = items.get("athlete")
                if a and isinstance(a, dict):
                    name = (a.get("fullName") or a.get("displayName") or "").strip()
                    injury = a.get("injuryStatus") or a.get("status") or items.get("status") or ""
                    if isinstance(injury, dict):
                        injury = injury.get("displayName") or injury.get("name") or injury.get("type") or ""
                    result[(team, name.casefold())] = str(injury)
                for key in ("athletes", "items"):
                    if key in items:
                        walk(items[key])
        walk(data.get("athletes", []))
    return result


def evaluate(games, slate_props, target):
    """Attach per-pick data-driven model output. Returns results + coverage notes."""
    player_games, team_games, team_events, warnings = collect_history(games, target)
    roster_entries = roster_health_from_api(games)
    evaluated = {}
    for game in games:
        game_id = game["id"]
        evaluated[game_id] = [
            estimate_candidate(
                {**item, "opponent": game["away_abbr"] if item["team"] == game["home_abbr"]
                 else game["home_abbr"]},
                player_games, team_games, team_events, roster_entries, target
            )
            for item in slate_props.get(game_id, [])
        ]
    return evaluated, warnings
