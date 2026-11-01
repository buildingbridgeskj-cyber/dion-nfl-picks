#!/usr/bin/env python3
"""Dion unified ranked board. Research display only: no wager execution."""
import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.agent_dion_nfl import AgentDion

ET = ZoneInfo("America/New_York")


def today_et():
    return datetime.now(ET).date().isoformat()


def same_date(game, target):
    try:
        iso = game["date"].replace("Z", "+00:00")
        return datetime.fromisoformat(iso).astimezone(ET).date().isoformat() == target
    except (KeyError, ValueError, TypeError):
        return False


def source_candidates(agent, games):
    by_id = {game["id"]: game for game in games}
    rows = []
    for pick in agent.score_picks(games):
        game = by_id[pick["game_id"]]
        market = pick["market"]
        market_has_line = {
            "spread": game.get("spread") is not None,
            "moneyline": game.get("home_ml") is not None,
            "total": game.get("total") is not None,
        }.get(market, False)
        rows.append({
            "game": pick["game"],
            "market": market.upper(),
            "selection": pick["selection"],
            "line": pick["line"],
            "odds": str(pick["american_odds"]) if pick["american_odds"] is not None else "N/A",
            "score": round(pick["confidence"]) if market_has_line else None,
            "source": "ESPN game odds",
            "note": "Unvalidated baseline; confirm current sportsbook odds"
                    if market_has_line else "Missing market line; NOT RATED",
        })
    return rows


def imported_props(path):
    if not path.exists():
        return []
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for entry in csv.DictReader(handle):
            if not entry.get("player"):
                continue
            try:
                numeric = float(entry["elite_score"]) if entry.get("elite_score") else None
                score = max(0, min(99, round(numeric))) if numeric is not None else None
            except (TypeError, ValueError):
                score = None
            rows.append({
                "game": entry.get("game", "?"),
                "market": entry.get("market", "PLAYER PROP").upper(),
                "selection": f'{entry["player"]} {entry.get("selection", "")}'.strip(),
                "line": entry.get("line", "N/A"),
                "odds": entry.get("odds", "N/A"),
                "score": score,
                "source": entry.get("source", "Imported file"),
                "note": "Imported score—not independently validated; confirm injury, line and odds",
            })
    return rows


def safe(value):
    return str(value).replace("|", "/").replace("\n", " ").strip()


def report(rows, target, count, props_count):
    heading = [
        "# AGENT DION — UNIFIED ELITE BOARD",
        f"Date (Eastern): {target} | Game slate: {count} | Ranked candidates: {len(rows)}",
        "",
        "**Elite Score /100 is a research-priority ranking, NOT a win probability or verified betting edge.**",
        "Existing game-market scores come from Dion's unvalidated deterministic baseline.",
        "Imported player-prop scores are shown only if supplied; scores of 99/100 are never invented.",
        "ESPN odds can be missing or delayed. Check live sportsbook lines and injury status before use.",
        "",
        "| Rank | Elite Score | Selection | Market | Line | Game | Odds | Status |",
        "|---:|---:|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        score = f'{r["score"]}/100' if r["score"] is not None else "N/R"
        cells = [i, score, r["selection"], r["market"], r["line"],
                 r["game"], r["odds"], r["note"]]
        heading.append("| " + " | ".join(safe(x) for x in cells) + " |")
    if not rows:
        heading.append("| — | — | No qualifying games or imported props | — | — | — | — | — |")
    heading += [
        "",
        f"Player props loaded from CSV: {props_count}. No live player-prop feed is installed here.",
        "No wagers placed. Other V14 scanners and services are not modified.",
        "",
    ]
    return "\n".join(heading)


def main():
    parser = argparse.ArgumentParser(description="Print one sorted Dion Elite Board for today's NFL games.")
    parser.add_argument("--date", default=today_et(), help="Eastern date YYYY-MM-DD")
    parser.add_argument("--props", type=Path, default=ROOT / "data" / "player_props_today.csv")
    args = parser.parse_args()
    agent = AgentDion()
    try:
        all_games = agent.fetch_nfl_games()
    except Exception as exc:
        print(f"ESPN schedule unavailable: {exc}", file=sys.stderr)
        return 1
    games = [g for g in all_games if same_date(g, args.date)]
    game_rows = source_candidates(agent, games)
    prop_rows = imported_props(args.props)
    rows = game_rows + prop_rows
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0),
                             r["game"], r["market"], r["selection"]))
    final = report(rows, args.date, len(games), len(prop_rows))
    output = ROOT / "output" / f'dion_elite_{args.date}.md'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(final, encoding="utf-8")
    mission = Path.home() / "v14-mission-control"
    if mission.is_dir():
        (mission / "dion_elite_today.md").write_text(final, encoding="utf-8")
    print(f"AGENT DION — ALL MARKETS RANKED | {args.date}")
    print("Elite Score = preliminary research score, NOT probability\n")
    print("RANK SCORE   MARKET       SELECTION / LINE                       GAME")
    print("-" * 87)
    for i, r in enumerate(rows, 1):
        score = f'{r["score"]:02d}/100' if r["score"] is not None else "N/R"
        selection = safe(r["selection"] + " " + r["line"])[:37]
        print(f'{i:>3}  {score:>6}  {r["market"][:11]:<11}  {selection:<37} {r["game"]}')
    if not rows:
        print("No current-day candidates found.")
    if not prop_rows:
        print("\nPLAYER PROPS: No CSV found. They are not invented.")
    print(f"\nSAVED: {output}")
    print("NO BETS PLACED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
