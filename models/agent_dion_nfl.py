#!/usr/bin/env python3
"""
Agent Dion - NFL Parlay Engine
Fetches the current NFL week's slate from ESPN, scores spread / moneyline /
total markets per game, and builds 4-5 leg parlays ranked by expected value.

Confidence model: deterministic baseline estimates (seeded per game+market),
calibrated over time by real graded results stored in data/results.json.
Run --grade flows or record_result() after games to build genuine history.

Payout math uses standard -110 parlay odds per leg unless real American odds
are available from the data feed.

For entertainment purposes only. Not financial advice. Bet responsibly.
"""

import hashlib
import itertools
import json
import os
import sys
from datetime import datetime, date
from typing import List, Dict, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
OUTPUT_DIR = os.path.join(REPO_ROOT, "output")
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "settings.json")

STD_DECIMAL = 100 / 110 + 1  # -110 American -> 1.9091 decimal
CONF_THRESHOLD = 65
MAX_POOL = 24  # cap candidate picks before combination (perf)


def load_settings() -> Dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


# ---------------------------------------------------------------- odds math

def american_to_decimal(odds: float) -> float:
    """Convert American odds to decimal odds."""
    if odds is None:
        return STD_DECIMAL
    odds = float(odds)
    if odds > 0:
        return odds / 100 + 1
    return 100 / abs(odds) + 1


def parlay_payout(legs: List[Dict], stake: float = 100.0) -> float:
    """Total return (stake included) for a $100 parlay at per-leg odds."""
    dec = 1.0
    for leg in legs:
        dec *= american_to_decimal(leg.get("american_odds"))
    return round(stake * dec, 2)


def parlay_probability(legs: List[Dict]) -> float:
    """Compound model probability (assumes independent legs)."""
    prob = 1.0
    for leg in legs:
        prob *= leg["confidence"] / 100.0
    return round(prob * 100, 2)


def expected_value(legs: List[Dict], stake: float = 100.0) -> float:
    """Model EV = P(win) * payout - stake. Model-based, not a proven edge."""
    return round(parlay_probability(legs) / 100 * parlay_payout(legs, stake) - stake, 2)


# ------------------------------------------------------- results / learning

def load_results() -> List[Dict]:
    path = os.path.join(DATA_DIR, "results.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


def record_result(game_id: str, sport: str, market: str, selection: str,
                  line: str, won: Optional[bool], week: Optional[int] = None) -> None:
    """Grade a past pick. This is what makes the 'learning system' real:
    confidence baselines calibrate to observed hit rates over time."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "results.json")
    results = load_results()
    results.append({
        "game_id": game_id,
        "sport": sport,
        "market": market,
        "selection": selection,
        "line": line,
        "won": won,
        "week": week,
        "graded_at": datetime.now().isoformat(),
    })
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Graded {sport}/{market} {selection} ({line}): {'WIN' if won else 'LOSS' if won is False else 'PENDING'}")


def calibrated_base(sport: str, market: str, default: float) -> float:
    """Shift the baseline toward the observed hit rate once we have >=10
    graded picks of that sport+market. Before that, use the default."""
    graded = [r for r in load_results()
              if r["sport"] == sport and r["market"] == market and r["won"] in (True, False)]
    if len(graded) < 10:
        return default
    hit_rate = sum(1 for r in graded if r["won"]) / len(graded) * 100
    # Blend: 50% prior default, 50% observed (shrunk toward 50 to avoid overfit)
    observed = 50 + (hit_rate - 50) * 0.7
    return round(default * 0.5 + observed * 0.5, 1)


def seeded_variance(key: str, low: int = -5, high: int = 5) -> int:
    """Deterministic per-pick variance. Same inputs -> same outputs,
    so reports are reproducible run to run."""
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return low + h % (high - low + 1)


# ------------------------------------------------------------------ agent

class AgentDion:
    BASE_SCORES = {"spread": 62, "moneyline": 58, "total": 68}

    def __init__(self):
        self.settings = load_settings()
        self.week: Optional[int] = None

    # -- week ------------------------------------------------------------
    @staticmethod
    def _fallback_week() -> int:
        """2026 season kicked off Thu 2026-09-10 = Week 1."""
        kickoff = date(2026, 9, 10)
        delta = (date.today() - kickoff).days
        return max(1, min(18, 1 + delta // 7))

    # -- fetch -----------------------------------------------------------
    def fetch_nfl_games(self) -> List[Dict]:
        """Current week's slate: games not yet final."""
        import requests
        url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        resp = requests.get(url, timeout=15)
        data = resp.json()
        self.week = (data.get("week") or {}).get("number") or self._fallback_week()
        games = []
        for ev in data.get("events", []):
            g = self._parse_game(ev)
            if g and not g["final"]:
                games.append(g)
        return games

    @staticmethod
    def _parse_game(ev: Dict) -> Optional[Dict]:
        try:
            comp = (ev.get("competitions") or [{}])[0]
            teams = {}
            for c in comp.get("competitors", []):
                side = c.get("homeAway")  # "home" | "away"
                team = c.get("team") or {}
                teams[side] = {
                    "abbr": team.get("abbreviation", "?"),
                    "name": team.get("displayName", "Unknown"),
                }
            if "home" not in teams or "away" not in teams:
                return None
            status = ((comp.get("status") or {}).get("type")) or {}
            game = {
                "sport": "nfl",
                "id": str(ev.get("id", "")),
                "home": teams["home"]["name"],
                "home_abbr": teams["home"]["abbr"],
                "away": teams["away"]["name"],
                "away_abbr": teams["away"]["abbr"],
                "date": ev.get("date", ""),
                "week": ev.get("week", {}).get("number"),
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
                # moneylines may be nested dicts or summary strings
                for key, out in (("homeTeamOdds", "home_ml"), ("awayTeamOdds", "away_ml")):
                    raw = (o.get(key) or {})
                    val = raw.get("summary") if isinstance(raw, dict) else raw
                    if isinstance(val, str):
                        val = val.replace("\u2212", "-")
                        try:
                            game[out] = float(val)
                        except ValueError:
                            pass
                    elif isinstance(val, (int, float)):
                        game[out] = float(val)
            return game
        except Exception:
            return None

    # -- scoring ---------------------------------------------------------
    def _calc_confidence(self, sport: str, game_id: str, market: str) -> float:
        base = calibrated_base(sport, market, self.BASE_SCORES.get(market, 60))
        var = seeded_variance(f"{sport}:{game_id}:{market}")
        return max(50, min(90, round(base + var, 1)))

    def _spread_selection(self, game: Dict) -> Dict:
        """Convention: take the favorite to cover when a line exists,
        else the home team. Stated openly in the report."""
        if game["spread"] is not None:
            try:
                sp = float(game["spread"])
                fav = game["home"] if sp < 0 else game["away"]
                return {"selection": fav, "line": f"{fav.split()[-1]} {sp:+g}"}
            except (TypeError, ValueError):
                pass
        return {"selection": game["home"], "line": "line N/A (home convention)"}

    def score_picks(self, games: List[Dict]) -> List[Dict]:
        picks = []
        for game in games:
            spread = self._spread_selection(game)
            markets = [
                {"market": "spread", "selection": spread["selection"],
                 "line": f"Spread {spread['line']}", "american_odds": None},
                {"market": "moneyline", "selection": game["home"],
                 "line": f"ML {game['home_ml']:+g}" if game["home_ml"] is not None else "ML home (convention)",
                 "american_odds": game["home_ml"]},
                {"market": "total", "selection": "Over",
                 "line": f"O/U {game['total']:g}" if game["total"] is not None else "O/U N/A (Over convention)",
                 "american_odds": None},
            ]
            for m in markets:
                picks.append({
                    "sport": "nfl",
                    "game_id": game["id"],
                    "game": f"{game['away_abbr']} @ {game['home_abbr']}",
                    "market": m["market"],
                    "selection": m["selection"],
                    "line": m["line"],
                    "american_odds": m["american_odds"],
                    "confidence": self._calc_confidence("nfl", game["id"], m["market"]),
                    "timestamp": datetime.now().isoformat(),
                })
        return picks

    # -- parlays ---------------------------------------------------------
    def build_parlays(self, picks: List[Dict], top_n: int = 3) -> List[Dict]:
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
                if len({p["game_id"] for p in c}) == legs  # one market per game
                and max(
                    sum(1 for p in c if p["market"] == m) for m in ("spread", "moneyline", "total")
                ) <= 2  # max 2 legs of the same market per parlay
            )
            ranked = sorted(
                combos,
                key=lambda c: sum(p["confidence"] for p in c) / len(c),
                reverse=True,
            )[:5]
            for combo in ranked:
                combo = list(combo)
                parlays.append({
                    "legs": legs,
                    "picks": combo,
                    "combined_confidence": round(sum(p["confidence"] for p in combo) / legs, 2),
                    "parlay_probability": parlay_probability(combo),
                    "estimated_payout": parlay_payout(combo),
                    "expected_value": expected_value(combo),
                    "sport": "nfl",
                    "timestamp": datetime.now().isoformat(),
                })
        return sorted(parlays, key=lambda p: p["expected_value"], reverse=True)[:top_n]

    # -- frozen cards ----------------------------------------------------
    def save_frozen_card(self, picks: List[Dict], label: str) -> None:
        week_dir = os.path.join(DATA_DIR, f"week{self.week or 'x'}")
        os.makedirs(week_dir, exist_ok=True)
        path = os.path.join(
            week_dir, f"frozen_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w") as f:
            json.dump({"picks": picks, "frozen_at": datetime.now().isoformat(),
                       "rule": "FROZEN_PREGAME - DO NOT MODIFY"}, f, indent=2)
        print(f"Frozen card saved: {path}")

    # -- report ----------------------------------------------------------
    def generate_report(self, parlays: List[Dict], n_games: int) -> str:
        n_graded = len([r for r in load_results() if r["won"] in (True, False)])
        lines = [
            "# Agent Dion - NFL Weekly Picks & Parlays",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Week: {self.week}",
            "",
            "## Summary",
            f"- **Games in slate:** {n_games}",
            f"- **Parlays:** {len(parlays)} (4-5 legs)",
            f"- **Graded historical picks:** {n_graded} (confidence calibrates once 10+ per market)",
            "",
            "> Conventions: spread takes the favorite (home team if no line); "
            "moneyline takes home; totals take the Over. Confidence is a baseline "
            "estimate, not a proven edge. For entertainment only.",
            "",
        ]
        for i, p in enumerate(parlays, 1):
            lines += [
                f"### Parlay #{i} ({p['legs']}-leg)",
                f"**Avg confidence:** {p['combined_confidence']}%",
                f"**Model hit probability:** {p['parlay_probability']}%",
                f"**Payout on $100:** ${p['estimated_payout']:,.2f} (at -110/leg unless real odds shown)",
                f"**Model expected value:** ${p['expected_value']:,.2f}",
                "",
                "**Legs:**",
            ]
            for leg in p["picks"]:
                lines.append(
                    f"- [{leg['game']}] {leg['market'].title()}: {leg['selection']} "
                    f"({leg['line']}) - {leg['confidence']}%")
            lines.append("")
        return "\n".join(lines)

    # -- run -------------------------------------------------------------
    def run(self):
        print("Agent Dion - NFL Parlay Engine")
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        print("Fetching NFL slate...")
        try:
            games = self.fetch_nfl_games()
        except Exception as e:
            print(f"Could not reach ESPN API: {e}")
            return None
        if not games:
            print("No upcoming NFL games this week.")
            return None
        print(f"Week {self.week}: {len(games)} upcoming games\n")

        picks = self.score_picks(games)
        print(f"Scored {len(picks)} market picks\n")

        parlays = self.build_parlays(picks)
        if not parlays:
            return None
        print(f"Generated {len(parlays)} parlays\n")

        # Freeze the top card pre-kickoff (immutable record)
        self.save_frozen_card(parlays[0]["picks"], "dion_top_card")

        report = self.generate_report(parlays, len(games))
        print(report)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out = os.path.join(OUTPUT_DIR, "dion_nfl_parlays.md")
        with open(out, "w") as f:
            f.write(report)
        print(f"\nReport saved: {out}")
        return parlays


if __name__ == "__main__":
    AgentDion().run()
