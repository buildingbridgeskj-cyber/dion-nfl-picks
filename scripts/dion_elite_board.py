#!/usr/bin/env python3
"""Agent Dion game-by-game board: up to 6 player props per team and 12 per game.

Research only. Real prices are not proven predictive edges. Never places bets.
Optional The Odds API feed requires ODDS_API_KEY; calls consume API quota.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.agent_dion_nfl import AgentDion

ET = ZoneInfo("America/New_York")
API_ROOT = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
MARKETS = (
    "player_pass_yds", "player_rush_yds", "player_reception_yds",
    "player_receptions", "player_anytime_td", "player_pass_tds",
)
MARKET_LABELS = {
    "player_pass_yds": "Passing yards",
    "player_rush_yds": "Rushing yards",
    "player_reception_yds": "Receiving yards",
    "player_receptions": "Receptions",
    "player_anytime_td": "Anytime TD",
    "player_pass_tds": "Passing TDs",
}
CACHE_DIR = ROOT / "data" / "dion_live_cache"


def today_et():
    return datetime.now(ET).date().isoformat()


def eastern_date(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET).date().isoformat()


def safe(value):
    return str(value).replace("|", "/").replace("\n", " ").strip()


def load_cached_json(name, ttl, fetcher):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / name
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    result = fetcher()
    path.write_text(json.dumps(result), encoding="utf-8")
    return result


def get_json(url, params=None):
    full = url + ("?" + urlencode(params) if params else "")
    # Never print the API key as part of an error message.
    with urlopen(full, timeout=25) as response:
        return json.load(response)


def fetch_odds_api(path, api_key, params=None):
    return get_json(
        f"{API_ROOT}/{path}",
        dict(params or {}, apiKey=api_key),
    )


def names_from_roster(payload):
    """Handle ESPN's grouped athletes[] and flat roster shapes."""
    names = set()
    def walk(item):
        if isinstance(item, list):
            for entry in item:
                walk(entry)
        elif isinstance(item, dict):
            if "items" in item:
                walk(item["items"])
            if "athletes" in item:
                walk(item["athletes"])
            if "fullName" in item and item.get("id"):
                names.add(item["fullName"].strip().casefold())
            elif "displayName" in item and item.get("id") and item.get("position"):
                names.add(item["displayName"].strip().casefold())
    walk(payload.get("athletes", []))
    return names


def player_team_map(games):
    """Only attribute a player to a team when listed on ESPN's current roster."""
    result = {}
    seen_teams = {}
    for game in games:
        for side in ("home", "away"):
            abbr = game.get(side + "_abbr", "")
            if abbr not in seen_teams:
                seen_teams[abbr] = game.get(side, "")
    for abbr in seen_teams:
        try:
            payload = load_cached_json(
                "roster_" + abbr + ".json", 21600,
                lambda a=abbr: get_json(
                    f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{a}/roster"
                ),
            )
            for name in names_from_roster(payload):
                if name in result and result[name] != abbr:
                    result[name] = None  # Ambiguous transfer/duplicate; do not guess.
                else:
                    result[name] = abbr
        except Exception as exc:
            print(f"Roster unavailable for {abbr}: {type(exc).__name__}", file=sys.stderr)
    return result


def normalize_team(value):
    return re.sub(r"[^a-z0-9]", "", value.lower()).replace("losangeles", "la")


def event_matches(game, event):
    return (
        normalize_team(game["home"]) == normalize_team(event.get("home_team", ""))
        and normalize_team(game["away"]) == normalize_team(event.get("away_team", ""))
    )


def implied_probability(american):
    price = float(american)
    if price < 0:
        return -price / (100 - price)
    if price > 0:
        return 100 / (100 + price)
    return None


def display_odds(value):
    try:
        value = int(float(value))
        return f"{value:+d}"
    except (TypeError, ValueError):
        return "N/A"


def live_props(games, key, roster):
    """Read real DraftKings quotes from The Odds API; no guessed prop lines."""
    if not games:
        return {}, 0, []
    try:
        events = load_cached_json(
            "events_" + today_et() + ".json", 900,
            lambda: fetch_odds_api(f"sports/{SPORT}/events", key),
        )
    except Exception as exc:
        return {}, 0, [f"Event feed unavailable ({type(exc).__name__})"]
    output = {}
    calls = 0
    warnings = []
    for game in games:
        game_id = game["id"]
        matched = next((ev for ev in events if event_matches(game, ev)), None)
        if not matched:
            warnings.append(f"No odds event match for {game['away_abbr']} @ {game['home_abbr']}")
            continue
        odds_id = matched["id"]
        cache_file = f"props_{odds_id}.json"
        cache_path = CACHE_DIR / cache_file
        was_cached = cache_path.exists() and time.time() - cache_path.stat().st_mtime < 900
        try:
            detail = load_cached_json(
                cache_file, 900,
                lambda ev_id=odds_id: fetch_odds_api(
                    f"sports/{SPORT}/events/{ev_id}/odds", key,
                    {"bookmakers": "draftkings", "markets": ",".join(MARKETS),
                     "oddsFormat": "american", "dateFormat": "iso"},
                ),
            )
            if not was_cached:
                calls += 1
        except Exception as exc:
            warnings.append(f"Props unavailable for {game['away_abbr']} @ {game['home_abbr']}: {type(exc).__name__}")
            continue
        # Collect directional prices, then normalize paired Over/Under to remove vig.
        by_market = {}
        books = [b for b in detail.get("bookmakers", []) if b.get("key") == "draftkings"]
        for book in books:
            for market in book.get("markets", []):
                category = market.get("key")
                if category not in MARKET_LABELS:
                    continue
                for outcome in market.get("outcomes", []):
                    player = safe(outcome.get("description", ""))
                    if not player:
                        # Some touchdown markets use the name field for the player.
                        if category == "player_anytime_td":
                            player = safe(outcome.get("name", ""))
                    name = outcome.get("name", "")
                    if not player or player in ("Yes", "No", "Over", "Under"):
                        continue
                    team = roster.get(player.casefold())
                    if team not in (game["home_abbr"], game["away_abbr"]):
                        continue
                    try:
                        price = float(outcome["price"])
                        probability = implied_probability(price)
                    except (KeyError, TypeError, ValueError, ZeroDivisionError):
                        continue
                    if probability is None:
                        continue
                    point = outcome.get("point")
                    side = str(name) if name in ("Over", "Under") else "Yes"
                    if category != "player_anytime_td" and point is None:
                        continue
                    market_key = (player, team, category, str(point))
                    by_market.setdefault(market_key, {})[side] = {
                        "price": price, "probability": probability, "point": point,
                    }
        entries = []
        for (player, team, category, _), sides in by_market.items():
            # Choose the higher implied-likelihood direction for each player/market.
            # This is market pricing, NOT independent model analysis or a value signal.
            side, quoted = max(sides.items(), key=lambda x: x[1]["probability"])
            if category == "player_anytime_td":
                side = "Yes"
            fair_prob = quoted["probability"]
            if "Over" in sides and "Under" in sides:
                denominator = sides["Over"]["probability"] + sides["Under"]["probability"]
                fair_prob = fair_prob / denominator if denominator else fair_prob
            entries.append({
                "game": f'{game["away_abbr"]} @ {game["home_abbr"]}',
                "team": team, "player": player,
                "market": MARKET_LABELS[category],
                "selection": side,
                "line": str(quoted["point"]) if quoted["point"] is not None else "Yes",
                "odds": display_odds(quoted["price"]),
                "score": min(99, max(1, round(100 * fair_prob))),
                "note": "Market-implied pricing score; not a forecast or proven edge",
                "source": "DraftKings via The Odds API",
            })
        output[game_id] = entries
    return output, calls, warnings


def imported_props(path, games):
    """Optional manual prop CSV; team and game must match this slate."""
    output = {}
    if not path.exists():
        return output
    game_map = {f'{g["away_abbr"]} @ {g["home_abbr"]}': g for g in games}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            game = game_map.get(row.get("game", ""))
            if not game or not row.get("player"):
                continue
            team = row.get("team", "").upper()
            if team not in (game["home_abbr"], game["away_abbr"]):
                continue
            try:
                score = round(float(row["elite_score"])) if row.get("elite_score") else None
                score = min(99, max(1, score)) if score is not None else None
            except (ValueError, TypeError):
                score = None
            entry = {
                "game": row["game"], "team": team,
                "player": row["player"], "market": row.get("market", "Player prop"),
                "selection": row.get("selection", "?"), "line": row.get("line", "?"),
                "odds": row.get("odds", "N/A"), "score": score,
                "note": "Imported CSV; freshness and model score not independently verified",
                "source": row.get("source", "Manual CSV"),
            }
            output.setdefault(game["id"], []).append(entry)
    return output


def sort_key(item):
    return (item["score"] is None, -(item["score"] or 0),
            item["player"].casefold(), item["market"])


def choose_top_12(candidates, game):
    """Try 6 unique team-specific selections each, then backfill to 12."""
    # Deduplicate overlapping feeds and exact repeats.
    unique = {}
    for item in candidates:
        key = (item["team"], item["player"].casefold(), item["market"], item["selection"], item["line"])
        if key not in unique or sort_key(item) < sort_key(unique[key]):
            unique[key] = item
    pool = sorted(unique.values(), key=sort_key)
    chosen = []
    consumed = set()
    for team in (game["away_abbr"], game["home_abbr"]):
        seen_players = set()
        team_rows = [r for r in pool if r["team"] == team]
        for row in team_rows:
            if len(seen_players) >= 6:
                break
            if row["player"].casefold() in seen_players:
                continue
            chosen.append(row)
            consumed.add(id(row))
            seen_players.add(row["player"].casefold())
        for row in team_rows:
            if len([r for r in chosen if r["team"] == team]) >= 6:
                break
            if id(row) not in consumed:
                chosen.append(row)
                consumed.add(id(row))
    # Fill remaining slots if one side has fewer markets, without inventing picks.
    for row in pool:
        if len(chosen) >= 12:
            break
        if id(row) not in consumed:
            chosen.append(row)
            consumed.add(id(row))
    return sorted(chosen[:12], key=sort_key)


def game_lines(game):
    parts = []
    if game.get("spread") is not None:
        parts.append(f'Spread: {game["spread"]}')
    if game.get("total") is not None:
        parts.append(f'Total: {game["total"]}')
    if game.get("home_ml") is not None:
        parts.append(f'Home ML: {display_odds(game["home_ml"])}')
    if game.get("away_ml") is not None:
        parts.append(f'Away ML: {display_odds(game["away_ml"])}')
    return ", ".join(parts) if parts else "No game-line quotes available"


def make_report(groups, day, errors, used_api):
    lines = [
        "# AGENT DION — TOP 12 PICKS PER GAME",
        f"Date (Eastern): {day} | Games: {len(groups)}",
        "",
        "**Goal: six player-prop selections from EACH team, 12 per matchup, sorted best-to-worst.**",
        "Elite Rank 99–88 is DISPLAY ORDER within each game, not a 99% success claim.",
        "Market % is derived from quoted market-implied prices, NOT an independent forecast, value edge, or win-rate estimate.",
        "Missing player props are never invented. Check injury, status, freshness and DraftKings lines.",
        "",
    ]
    for game, kickoff, picks in groups:
        title = f'{game["away_abbr"]} @ {game["home_abbr"]}'
        away = sum(p["team"] == game["away_abbr"] for p in picks)
        home = sum(p["team"] == game["home_abbr"] for p in picks)
        lines += [
            f"## {title} — {kickoff}",
            f"**Player picks: {len(picks)}/12 | {game['away_abbr']}: {away} | {game['home_abbr']}: {home}**",
            "",
            "| # | Elite Rank | Market % | Team | Player | Market | Pick | Line | Odds |",
            "|---:|---:|---:|---|---|---|---|---|---:|",
        ]
        for rank, p in enumerate(picks, 1):
            score = f'{p["score"]}/100' if p["score"] is not None else "N/R"
            values = [rank, f"{100-rank}/100", score, p["team"], p["player"], p["market"],
                      p["selection"], p["line"], p["odds"]]
            lines.append("| " + " | ".join(safe(value) for value in values) + " |")
        if not picks:
            lines.append("| — | — | — | — | No verified player-prop feed | — | — | — | — |")
        if len(picks) < 10:
            lines.append(f"\n**DATA SHORTFALL:** Only {len(picks)} verified/attributed markets; cannot honestly supply 10–12.")
        lines += ["", f"**Game lines (reference only):** {game_lines(game)}", ""]
    if errors:
        lines += ["### Feed warnings", *("- " + safe(msg) for msg in errors), ""]
    if not used_api:
        lines.append("Live prop feed was not enabled; set ODDS_API_KEY to retrieve available DraftKings props.")
    lines += [
        "Market quotes and source coverage may change; no ticket or bet was submitted.",
        "Output is a research board, not investment or wagering advice.",
    ]
    return "\n".join(lines)


def fetch_date_slate(agent, target):
    """Query the requested Eastern date, including future 9:30 AM international games."""
    params = {"dates": target.replace("-", ""), "limit": 100}
    response = get_json(
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        params,
    )
    games = []
    for event in response.get("events", []):
        game = agent._parse_game(event)
        if game and not game["final"] and eastern_date(game["date"]) == target:
            games.append(game)
    if games:
        return games
    # Fallback when ESPN date-scoped endpoint does not cover the requested date.
    return [game for game in agent.fetch_nfl_games()
            if eastern_date(game["date"]) == target]


def main():
    parser = argparse.ArgumentParser(description="Top 12 NFL player props per game, six from each team if available.")
    parser.add_argument("--date", default=today_et(), help="Eastern YYYY-MM-DD (default today)")
    parser.add_argument("--props", type=Path, default=ROOT / "data" / "player_props_today.csv")
    parser.add_argument("--no-live", action="store_true", help="Skip Odds API (avoids usage credits)")
    args = parser.parse_args()
    agent = AgentDion()
    try:
        games = fetch_date_slate(agent, args.date)
    except Exception as exc:
        print(f"ESPN schedule unavailable ({type(exc).__name__}); no stale schedule used.", file=sys.stderr)
        return 1
    key = os.getenv("ODDS_API_KEY", "").strip()
    live_data = {}
    credits_calls = 0
    warnings = []
    if key and not args.no_live and games:
        roster = player_team_map(games)
        live_data, credits_calls, warnings = live_props(games, key, roster)
    else:
        warnings.append("No live DraftKings prop feed; ODDS_API_KEY missing or --no-live selected.")
    manual = imported_props(args.props, games)
    groups = []
    for game in sorted(games, key=lambda item: item.get("date", "")):
        kickoff = datetime.fromisoformat(game["date"].replace("Z", "+00:00")).astimezone(ET).strftime("%I:%M %p %Z")
        pool = live_data.get(game["id"], []) + manual.get(game["id"], [])
        groups.append((game, kickoff, choose_top_12(pool, game)))

    report = make_report(groups, args.date, warnings, bool(key and not args.no_live))
    output = ROOT / "output" / f'dion_elite_{args.date}.md'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    mission = Path.home() / "v14-mission-control"
    if mission.is_dir():
        (mission / "dion_elite_today.md").write_text(report, encoding="utf-8")

    print(f"AGENT DION | {args.date} | {len(groups)} GAMES | SIX PER TEAM / 12 PER GAME")
    print("ELITE RANK 99-88 = DISPLAY ORDER ONLY; MARKET % IS NOT MODEL HIT PROBABILITY")
    for game, kickoff, picks in groups:
        print("\n" + "=" * 78)
        print(f'{game["away_abbr"]} @ {game["home_abbr"]} | {kickoff} | {len(picks)}/12 picks')
        print("=" * 78)
        for rank, row in enumerate(picks, 1):
            score = f'{row["score"]:02d}/100' if row["score"] is not None else "N/R"
            print(f'{rank:2d}. {100-rank:02d}/100 | Market {score:>6} | {row["team"]:3s} | {row["player"][:19]:19s} | '
                  f'{row["market"][:15]:15s} | {row["selection"]} {row["line"]} ({row["odds"]})')
        if len(picks) < 10:
            print(f'  DATA SHORTFALL: Only {len(picks)} real available picks; no fabricated selections.')
        print(f'  Game lines: {game_lines(game)}')
    print(f"\nSAVED: {output}")
    print(f"New per-event Odds API requests: {credits_calls} (additional usage may apply).")
    print("NO BETS PLACED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
