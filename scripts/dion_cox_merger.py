#!/usr/bin/env python3
"""
Dion + Cox unified runner.
Runs Agent Dion (NFL) and Agent Cox (MLB/NCAAF), merges all parlays,
ranks by model expected value, and writes a unified daily report.

Usage:
    python scripts/dion_cox_merger.py        # from repo root
"""

import os
import sys
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "models"))

from agent_dion_nfl import AgentDion
from agent_cox_mlb_ncaaf import AgentCox

OUTPUT_DIR = os.path.join(REPO_ROOT, "output")


def run_agent(name, agent):
    print("=" * 50)
    print(f"RUNNING {name}")
    print("=" * 50 + "\n")
    try:
        return agent.run() or []
    except Exception as e:
        print(f"{name} failed: {e}")
        return []


def unified_report(dion_parlays, cox_parlays) -> str:
    all_p = [("DION", p) for p in dion_parlays] + [("COX", p) for p in cox_parlays]
    all_p.sort(key=lambda t: t[1]["expected_value"], reverse=True)

    lines = [
        "# Dion + Cox - Unified Parlay Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"- **Dion (NFL) parlays:** {len(dion_parlays)}",
        f"- **Cox (MLB/NCAAF) parlays:** {len(cox_parlays)}",
        "- **Ranked by:** model expected value",
        "",
        "> For entertainment only. Model EV is not a proven edge. Bet responsibly.",
        "",
    ]
    for i, (tag, p) in enumerate(all_p, 1):
        sports = p.get("sports_included", [p.get("sport", "?")])
        sports = " + ".join(s.upper() for s in sports)
        payout = p.get("estimated_payout", p.get("parlay_payout"))
        lines += [
            f"### #{i} [{tag}] {sports} ({p['legs']}-leg)",
            f"**Avg confidence:** {p['combined_confidence']}%",
            f"**Model hit probability:** {p['parlay_probability']}%",
            f"**Payout on $100:** ${payout:,.2f}",
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


def main():
    print(
        "\n"
        "  DION + COX UNIFIED PARLAY ENGINE\n"
        f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    dion_parlays = run_agent("AGENT DION (NFL)", AgentDion())
    print()
    cox_parlays = run_agent("AGENT COX (MLB/NCAAF)", AgentCox())

    print("=" * 50)
    print("MERGING RESULTS")
    print("=" * 50 + "\n")

    report = unified_report(dion_parlays, cox_parlays)
    print(report)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = os.path.join(OUTPUT_DIR, "dion_cox_unified_parlays.md")
    with open(out, "w") as f:
        f.write(report)
    print(f"\nUnified report saved: {out}")


if __name__ == "__main__":
    main()
