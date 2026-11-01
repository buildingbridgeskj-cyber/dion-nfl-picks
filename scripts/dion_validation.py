#!/usr/bin/env python3
"""Dion out-of-sample pregame snapshots and postgame evaluation.

No wagering action. Local snapshots are immutable. Grades are descriptive,
not proof of an edge until large samples and proper price comparisons exist.
"""
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.dion_evidence import fetch, extract_boxscore, STAT_MAP

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "dion_frozen"
ET = ZoneInfo("America/New_York")


def snapshot(day, groups):
    DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(ET)
    items = []
    for game, kickoff, picks in groups:
        try:
            start = datetime.fromisoformat(game["date"].replace("Z", "+00:00")).astimezone(ET)
        except (ValueError, KeyError, TypeError):
            continue
        if start <= now:
            continue
        for p in picks:
            if p.get("model_pct") is None or not p.get("status", "").startswith("REVIEW"):
                continue
            items.append({
                "game_id": game["id"], "game": f'{game["away_abbr"]} @ {game["home_abbr"]}',
                "kickoff": start.isoformat(), "date": day,
                "team": p["team"], "player": p["player"], "market": p["market"],
                "side": p["selection"], "line": p["line"], "odds": p["odds"],
                "model_pct": p["model_pct"], "edge_pct": p["edge_pct"],
                "elite_score": p["elite_score"], "created": now.isoformat(),
            })
    # Snapshot every run with its timestamp; never replace earlier predictions.
    path = DIR / (now.strftime("dion_%Y%m%d_%H%M%S_%f") + ".json")
    path.write_text(json.dumps({"date": day, "picks": items}, indent=2), encoding="utf-8")
    return path, len(items)


def grade_item(pick, players):
    """Final result of an individual frozen pick, or None when unresolvable."""
    key = STAT_MAP.get(pick["market"])
    if not key or pick["market"] == "Anytime TD":
        return None
    values = players.get((pick["team"], pick["player"].casefold()), {})
    actual = values.get(key)
    if actual is None:
        return None
    try:
        line = float(pick["line"])
    except (ValueError, TypeError):
        return None
    if math.isclose(actual, line):
        return "PUSH", actual
    over = actual > line
    won = over if pick["side"] == "Over" else not over
    return ("WIN" if won else "LOSS"), actual


def grade_history():
    """Read completed game results. Return past out-of-sample, unique pick stats."""
    if not DIR.exists():
        return {"graded": 0, "won": 0, "lost": 0, "push": 0, "brier": None}
    seen = set()
    samples = []
    result_cache = {}
    final_by_date = {}
    current = datetime.now(ET)
    for file in sorted(DIR.glob("dion_*.json")):
        try:
            snapshot_data = json.loads(file.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for p in snapshot_data.get("picks", []):
            try:
                kickoff = datetime.fromisoformat(p["kickoff"])
                if kickoff.date() >= current.date():
                    continue
            except (ValueError, KeyError):
                continue
            unique = (p["game_id"], p["player"], p["market"], p["side"], p["line"])
            if unique in seen:
                continue
            seen.add(unique)
            day = kickoff.strftime("%Y%m%d")
            if day not in final_by_date:
                try:
                    board = fetch("scoreboard", {"dates": day}, ttl=3600)
                    final_by_date[day] = {
                        str(ev["id"]) for ev in board.get("events", [])
                        if (ev.get("status") or {}).get("type", {}).get("completed")
                    }
                except Exception:
                    final_by_date[day] = set()
            if p["game_id"] not in final_by_date[day]:
                continue
            if p["game_id"] not in result_cache:
                try:
                    result_cache[p["game_id"]] = extract_boxscore(
                        fetch("summary", {"event": p["game_id"]}, ttl=259200)
                    )[0]
                except Exception:
                    result_cache[p["game_id"]] = {}
            item = grade_item(p, result_cache[p["game_id"]])
            if item is not None:
                result, actual = item
                samples.append((result, float(p["model_pct"]) / 100, p))
    settled = [s for s in samples if s[0] in ("WIN", "LOSS")]
    wins = sum(s[0] == "WIN" for s in settled)
    brier = (sum((prob - (1 if result == "WIN" else 0)) ** 2
                 for result, prob, _ in settled) / len(settled)) if settled else None
    metrics = {"graded": len(settled), "won": wins, "lost": len(settled) - wins,
               "push": len(samples) - len(settled),
               "hit_rate": round(100 * wins / len(settled), 1) if settled else None,
               "brier": round(brier, 4) if brier is not None else None,
               "validation": "EARLY SAMPLE" if len(settled) < 100 else "UNVERIFIED EDGE"}
    return metrics
