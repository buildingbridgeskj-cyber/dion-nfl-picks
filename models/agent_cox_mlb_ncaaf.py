#!/usr/bin/env python3
"""
Agent Cox - MLB & NCAAF Parlay Engine
Mirrors Agent Dion's framework for baseball and college football.
Fetches today's MLB schedule (StatsAPI) and the current NCAAF week's slate
(ESPN), scores spread / moneyline / total markets, and builds 4-5 leg
parlays ranked by expected value.

Same confidence model as Dion: deterministic baseline estimates, calibrated
over time by real graded results in data/results.json.

For entertainment purposes only. Not financial advice. Bet responsibly.
"""

import hashlib
import itertools
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
OUTPUT_DIR = os.path.join(REPO_ROOT, "output")

STD_DECIMAL = 100 / 110 + 1  # -110 American -> 1.9091 decimal
CONF_THRESHOLD = 65  # aligned with Dion (was an undocumented 62)
MAX_POOL = 24
PLAYABLE_MLB = {"Scheduled", "Pre-Game", "Warmup", "In Progress", "Live"}


def american_to_decimal(odds) -> float:
    if odds is None:
        return STD_DECIMAL
    odds = float(odds)
    return odds / 100 + 1 if odds > 0 else 100 / abs(odds) + 1


def parlay_payout(legs: List[Dict], stake: float = 100.0) -> float:
    dec = 1.0
    for leg in legs:
        dec *= american_to_decimal(leg.get("american_odds"))
    return round(stake * dec, 2)


def parlay_probability(legs: List[Dict]) -> float:
    prob = 1.0
    for leg in legs:
        prob *= leg["confidence"] / 100.0
    return round(prob * 100, 2)


def expected_value(legs: List[Dict], stake: float = 100.0) -> float:
    return round(parlay_probability(legs) / 100 * parlay_payout(legs, stake) - stake, 2)


def load_results() -> List[Dict]:
    try:
        with open(os.path.join(DATA_DIR, "results.json")) as f:
            return json.load(f)
    except Exception:
        return []


def calibrated_base(sport: str, market: str, default: float) -> float:
    graded = [r for r in load_results()
              if r["sport"] == sport and r["market"] == market and r["won"] in (True, False)]
    if len(graded) < 10:
        return default
    hit_rate = sum(1 for r in graded if r["won"]) / len(graded) * 100
    observed = 50 + (hit_rate - 50) * 0.7
    return round(default * 0.5 + observed * 0.5, 1)


def seeded_variance(key: str, low: int = -5, high: int = 5) -> int:
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return low + h % (high - low + 1)


class AgentCox:
    BASE_SCORES = {"spread": 63, "moneyline": 58, "total": 65}

    def __init__(self):
        self.today = datetime.now().strftime("%Y-%m-%d")

    # ------------------------------------------------------------ fetching
    def fetch_mlb_games(self) -> List[Dict]:
        """Today's MLB schedule from StatsAPI (only pre-game / live)."""
        import requests
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={self.today}"
        resp = requests.get(url, timeout=15)
        games = []
        for day in resp.json().get("dates", []):
            for g in day.get("games", []):
                parsed = self._parse_mlb(g)
                if parsed:
                    games.append(parsed)
        return games

    @staticmethod
    def _parse_mlb(g: Dict) -> Optional[Dict]:
        try:
            state = (g.get("status") or {}).get("detailedState", "")
            if state not in PLAYABLE_MLB:
                return None
            teams = g.get("teams") or {}
            home = ((teams.get("home") or {}).get("team") or {}).get("name", "Unknown")
            away = ((teams.get("away") or {}).get("team") or {}).get("name", "Unknown")
            return {
                "sport": "mlb",
                "id": str(g.get("gamePk", "")),
                "home": home,
                "away": away,
                "date": g.get("gameDate", ""),
                "state": state,
                "final": False,
            }
        except Exception:
            return None

    def fetch_ncaaf_games(self) -> List[Dict]:
        """Current NCAAF week's slate from ESPN (games not yet final)."""
        import requests
        url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
        resp = requests.get(url, timeout=15)
        games = []
        for ev in resp.json().get("events", []):
            parsed = self._parse_espn(ev, "ncaaf")
            if parsed and not parsed["final"]:
                games.append(parsed)
        return games

    @staticmethod
    def _parse_espn(ev: Dict, sport: str) -> Optional[Dict]:
        try:
            comp = (ev.get("competitions") or [{}])[0]
            teams = {}
            for c in comp.get("competitors", []):
                side = c.get("homeAway")
                team = c.get("team") or {}
                teams[side] = {
                    "abbr": team.get("abbreviation", "?"),
                    "name": team.get("displayName", "Unknown"),
                }
            if "home" not in teams or "away" not in teams:
                return None
            status = ((comp.get("status") or {}).get("type")) or {}
            game = {
                "sport": sport,
                "id": str(ev.get("id", "")),
                "home": teams["home"]["name"],
                "home_abbr": teams["home"]["abbr"],
                "away": teams["away"]["name"],
                "away_abbr": teams["away"]["abbr"],
                "date": ev.get("date", ""),
                "final": bool(status.get("completed")),
                "spread": None,
                "total": None,
                "home_ml": None,
                "away_ml": None,
            }
            odds = comp.get("odds") or []
            if odds:
                o = odds[0]
                game["spread"] = o.get("spread")
                game["total"] = o.get("overUnder")
                for key, out in (("homeTeamOdds", "home_ml"), ("awayTeamOdds", "away_ml")):
                    raw = (o.get(key) or {})
                    val = raw.get("summary") if isinstance(raw, dict) else raw
                    if isinstance(val, str):
                        try:
                            game[out] = float(val.replace("\u2212", "-"))
                        except ValueError:
                            pass
                    elif isinstance(val, (int, float)):
                        game[out] = float(val)
            return game
        except Exception:
            return None

    # ------------------------------------------------------------- scoring
    def _calc_confidence(self, sport: str, game_id: str, market: str) -> float:
        base = calibrated_base(sport, market, self.BASE_SCORES.get(market, 60))
        var = seeded_variance(f"{sport}:{game_id}:{market}")
        return max(50, min(90, round(base + var, 1)))

    @staticmethod
    def _spread_selection(game: Dict) -> Dict:
        if game.get("spread") is not None:
            try:
                sp = float(game["spread"])
                fav = game["home"] if sp < 0 else game["away"]
                return {"selection": fav, "line": f"{sp:+g}"}
            except (TypeError, ValueError):
                pass
        return {"selection": game["home"], "line": "N/A (home convention)"}

    def score_picks(self, games: List[Dict]) -> List[Dict]:
        picks = []
        for game in games:
            sport = game["sport"]
            spread = self._spread_selection(game)
            # MLB has no spread market in this feed -> run line noted as N/A
            markets = [
                {"market": "spread", "selection": spread["selection"],
                 "line": f"Spread {spread['line']}", "american_odds": None},
                {"market": "moneyline", "selection": game["home"],
                 "line": (f"ML {game['home_ml']:+g}" if game.get("home_ml") is not None
                          else "ML home (convention)"),
                 "american_odds": game.get("home_ml")},
                {"market": "total", "selection": "Over",
                 "line": (f"O/U {game['total']:g}" if game.get("total") is not None
                          else "O/U N/A (Over convention)"),
                 "american_odds": None},
            ]
            for m in markets:
                picks.append({
                    "sport": sport,
                    "game_id": f"{sport}:{game['id']}",
                    "game": f"{game['away']} @ {game['home']}",
                    "market": m["market"],
                    "selection": m["selection"],
                    "line": m["line"],
                    "american_odds": m["american_odds"],
                    "confidence": self._calc_confidence(sport, game["id"], m["market"]),
                    "timestamp": datetime.now().isoformat(),
                })
        return picks

    # ------------------------------------------------------------- parlays
    def build_parlays(self, picks: List[Dict], top_n: int = 5) -> List[Dict]:
        pool = sorted(
            (p for p in picks if p["confidence"] >= CONF_THRESHOLD),
            key=lambda p: p["confidence"], reverse=True,
        )[:MAX_POOL]
        if len(pool) < 4:
            print("Not enough high-confidence picks for a parlay.")
            return []

        parlays = []
        for legs in (4, 5):
            combos = (
                c for c in itertools.combinations(pool, legs)
                if len({p["game_id"] for p in c}) == legs
                and max(
                    sum(1 for p in c if p["market"] == m) for m in ("spread", "moneyline", "total")
                ) <= 2  # max 2 legs of the same market per parlay
            )
            ranked = sorted(
                combos,
                key=lambda c: sum(p["confidence"] for p in c) / len(c),
                reverse=True,
            )[:10]
            for combo in ranked:
                combo = list(combo)
                parlays.append({
                    "legs": legs,
                    "picks": combo,
                    "combined_confidence": round(sum(p["confidence"] for p in combo) / legs, 2),
                    "parlay_probability": parlay_probability(combo),
                    "parlay_payout": parlay_payout(combo),
                    "expected_value": expected_value(combo),
                    "sports_included": sorted({p["sport"] for p in combo}),
                    "timestamp": datetime.now().isoformat(),
                })
        return sorted(parlays, key=lambda p: p["expected_value"], reverse=True)[:top_n]

    # -------------------------------------------------------------- report
    def generate_report(self, parlays: List[Dict], n_games: int) -> str:
        lines = [
            "# Agent Cox - MLB & NCAAF Parlays",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"- **Games in slate:** {n_games}",
            f"- **Parlays:** {len(parlays)} (4-5 legs, MLB + NCAAF)",
            "",
            "> Conventions: spread takes the favorite (home team if no line); "
            "moneyline takes home; totals take the Over. Confidence is a baseline "
            "estimate, not a proven edge. For entertainment only.",
            "",
        ]
        for i, p in enumerate(parlays, 1):
            sports = " + ".join(s.upper() for s in p["sports_included"])
            lines += [
                f"### Parlay #{i} ({p['legs']}-leg, {sports})",
                f"**Avg confidence:** {p['combined_confidence']}%",
                f"**Model hit probability:** {p['parlay_probability']}%",
                f"**Payout on $100:** ${p['parlay_payout']:,.2f}",
                f"**Model expected value:** ${p['expected_value']:,.2f}",
                "",
                "**Legs:**",
            ]
            for leg in p["picks"]:
                lines.append(
                    f"- [{leg['sport'].upper()}] {leg['game']}: "
                    f"{leg['market'].title()} {leg['selection']} ({leg['line']}) - {leg['confidence']}%")
            lines.append("")
        return "\n".join(lines)

    # ----------------------------------------------------------------- run
    def run(self):
        print("Agent Cox - MLB + NCAAF Parlay Engine")
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        games: List[Dict] = []
        try:
            print("Fetching MLB schedule...")
            mlb = self.fetch_mlb_games()
            print(f"  {len(mlb)} playable MLB games")
            games += mlb
        except Exception as e:
            print(f"  MLB feed unavailable: {e}")
        try:
            print("Fetching NCAAF slate...")
            ncaaf = self.fetch_ncaaf_games()
            print(f"  {len(ncaaf)} upcoming NCAAF games")
            games += ncaaf
        except Exception as e:
            print(f"  NCAAF feed unavailable: {e}")

        if not games:
            print("No playable games found right now.")
            return None

        picks = self.score_picks(games)
        print(f"\nScored {len(picks)} market picks\n")

        parlays = self.build_parlays(picks)
        if not parlays:
            return None
        print(f"Generated {len(parlays)} parlays\n")

        report = self.generate_report(parlays, len(games))
        print(report)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out = os.path.join(OUTPUT_DIR, "cox_mlb_ncaaf_parlays.md")
        with open(out, "w") as f:
            f.write(report)
        print(f"\nReport saved: {out}")
        return parlays


if __name__ == "__main__":
    AgentCox().run()
