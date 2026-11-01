#!/usr/bin/env python3
"""Dion grouped ranked board. Research display only: no wager execution."""
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


def grouped_games(rows, games):
    """One section per game; strongest available score first within each section."""
    by_game = {}
    for row in rows:
        by_game.setdefault(row["game"], []).append(row)
    result = []
    for game in sorted(games, key=lambda g: g.get("date") or ""):
        key = f'{game["away_abbr"]} @ {game["home_abbr"]}'
        try:
            kickoff = datetime.fromisoformat(
                game["date"].replace("Z", "+00:00")
            ).astimezone(ET).strftime("%I:%M %p %Z")
        except (KeyError, ValueError, TypeError):
            kickoff = "Kickoff unavailable"
        result.append((key, kickoff, by_game.pop(key, [])))
    for key in sorted(by_game):
        result.append((key, "Imported matchup; kickoff unverified", by_game[key]))
    for key, kickoff, entries in result:
        entries.sort(key=lambda row: (
            row["score"] is None, -(row["score"] or 0), row["market"], row["selection"]
        ))
    return result


def report(groups, target, count, props_count):
    lines = [
        "# AGENT DION — ELITE RANKINGS BY GAME",
        f"Date (Eastern): {target} | Games: {count}",
        "",
        "**Elite Score /100 is a preliminary research ranking, NOT a win probability or proven edge.**",
        "Existing market scores use Dion's unvalidated baseline; player-prop scores are imported only.",
        "Verify current odds, injury status, and statistical support before considering any selection.",
        "",
    ]
    for game, kickoff, picks in groups:
        lines += [
            f"## {game} — {kickoff}",
            "",
            "| Rank | Elite Score | Market | Selection | Line | Odds | Status |",
            "|---:|---:|---|---|---|---|---|",
        ]
        for number, pick in enumerate(picks, 1):
            score = f'{pick["score"]}/100' if pick["score"] is not None else "N/R"
            values = [number, score, pick["market"], pick["selection"],
                      pick["line"], pick["odds"], pick["note"]]
            lines.append("| " + " | ".join(safe(value) for value in values) + " |")
        if not picks:
            lines.append("| — | — | — | No scored markets available | — | — | — |")
        lines.append("")
    if not groups:
        lines.append("No games or imported props found for this date.")
    lines += [
        "",
        f"Player props imported: {props_count}. No automatic live player-prop feed is installed.",
        "N/R means no valid market line or score; missing values are never invented.",
        "No bets placed. Other V14 scanners and services are not modified.",
        "",
    ]
    return "\n".join(lines)


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
    groups = grouped_games(game_rows + prop_rows, games)
    final = report(groups, args.date, len(games), len(prop_rows))
    output = ROOT / "output" / f'dion_elite_{args.date}.md'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(final, encoding="utf-8")
    mission = Path.home() / "v14-mission-control"
    if mission.is_dir():
        (mission / "dion_elite_today.md").write_text(final, encoding="utf-8")

    print(f"AGENT DION — ELITE RANKINGS BY GAME | {args.date}")
    print("Elite Scores are preliminary research rankings, not win probabilities.")
    for game, kickoff, picks in groups:
        print(f"\n{'=' * 72}")
        print(f"{game}  |  {kickoff}")
        print(f"{'=' * 72}")
        print("RANK  SCORE   MARKET       SELECTION / LINE")
        for i, row in enumerate(picks, 1):
            score = f'{row["score"]:02d}/100' if row["score"] is not None else "N/R"
            selection = safe(row["selection"] + " " + row["line"])[:49]
            print(f'{i:>3}   {score:>6}  {row["market"][:11]:<11}  {selection}')
        if not picks:
            print("No scored markets available.")
    if not groups:
        print("No games or imported props available for this date.")
    if not prop_rows:
        print("\nPLAYER PROPS: No CSV loaded; player props have not been invented.")
    print(f"\nSAVED: {output}")
    print("NO BETS PLACED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
