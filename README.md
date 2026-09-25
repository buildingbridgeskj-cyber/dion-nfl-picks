# Agent Dion - NFL Parlay Analytics & Prediction System

## Overview
Agent Dion is a parlay analytics system that pulls the live NFL week's slate from ESPN, scores spread/moneyline/total markets per game, and builds 4-5 leg parlays ranked by model expected value. It includes a genuine learning loop: grade your picks with `record_result()` and confidence baselines calibrate to your real observed hit rates over time (stored in `data/results.json`).

> Confidence scores are baseline estimates, not a proven edge. For entertainment purposes only. Not financial advice. Bet responsibly.

## Core Features

### 1. **Weekly Data Collection & Storage**
- Captures all NFL Week selections (lines, props, O/U)
- Stores picks for all 32 teams
- Tracks top 20 players per team
- Maintains historical data through 2026-2027 season

### 2. **Intelligent Learning System**
- Compares week-to-week performance metrics
- Calculates hit rates and probability percentages
- Identifies high-confidence selection patterns
- Builds predictive confidence scores

### 3. **Parlay Optimization Engine**
- Generates 4-leg and 5-leg parlays
- Filters picks by confidence thresholds
- Calculates expected value (EV) for each parlay
- Ranks parlays by probability of hitting

### 4. **Performance Tracking**
- Win/loss records by week
- Accuracy metrics per pick type (lines, props, O/U)
- ROI calculations
- Trend analysis and seasonal patterns

## Directory Structure

```
dion-nfl-picks/
├── README.md
├── requirements.txt            # pip dependencies
├── config/
│   └── settings.json           # System configuration & thresholds
├── data/
│   ├── results.json            # Your graded picks (the learning history - starts empty)
│   └── week{N}/               # Frozen pre-kickoff pick cards (immutable)
├── models/
│   ├── agent_dion_nfl.py       # NFL parlay engine
│   └── agent_cox_mlb_ncaaf.py  # MLB + NCAAF parlay engine
├── scripts/
│   └── dion_cox_merger.py      # Unified Dion + Cox runner
├── output/
│   ├── dion_nfl_parlays.md
│   ├── cox_mlb_ncaaf_parlays.md
│   └── dion_cox_unified_parlays.md
└── logs/
```

## How Agent Dion Works

### Phase 1: Data Ingestion
- Pulls the current NFL week's slate live from ESPN (upcoming games only)
- Parses teams, spreads, totals, and moneylines where the feed provides them

### Phase 2: Scoring
- Assigns each game three market picks (spread, moneyline, total) using stated
  conventions: spread takes the favorite (home team if no line), moneyline takes
  home, totals take the Over
- Confidence = deterministic baseline estimate, seeded per game+market so runs
  are reproducible. Once you have graded 10+ picks of a market, baselines
  calibrate toward your real observed hit rate (`data/results.json`)

### Phase 3: Parlay Construction
- Filters picks at the 65% confidence threshold
- Builds 4-leg and 5-leg combos: max 24 candidates, one market per game,
  max 2 legs of the same market per parlay
- Payouts use real American odds when available, else standard -110 parlay math
- Ranks by model expected value

### Phase 4: Recommendations
- Generates weekly report with top selections
- Provides confidence metrics and historical accuracy
- Presents ranked parlay options with expected payouts
- Tracks results for next cycle improvement

## Key Metrics

| Metric | Definition |
|--------|-----------|
| **Hit Rate** | % of correct picks in a given week |
| **Confidence Score** | 0-100 scale based on historical accuracy |
| **Parlay Probability** | Likelihood all legs hit |
| **Expected Value** | (Probability × Payout) - Risk |
| **ROI** | Return on Investment over season |
| **Trend Score** | Performance momentum (↑ improving, ↓ declining) |

## Weekly Workflow

1. **Input:** Feed current week's game lines, props, O/U data
2. **Analysis:** Dion processes against historical data
3. **Learning:** Updates confidence models
4. **Generation:** Creates ranked 4-5 leg parlays
5. **Output:** Weekly report with picks and projected payouts
6. **Tracking:** Grade results with `record_result()` so confidence calibrates to your real hit rate

## Confidence Thresholds

- **Green Flag (75%+):** High confidence
- **Yellow Flag (65-74%):** Medium confidence - parlay candidates
- **Red Flag (<65%):** Low confidence - excluded from parlays

## Parlay Structure

- **4-leg:** mixed markets, max 2 of the same market, one market per game
- **5-leg:** same constraints, higher payout / lower hit probability
- Payouts use real American odds when the feed provides them, else standard -110 math

## Data Retention & Continuity

Your graded results persist in `data/results.json`, allowing Dion to:
- Calibrate confidence baselines to your real observed hit rates
- Compare current performance to previous weeks
- Recognize hot/cold streaks per market
- Improve estimates with each passing week

## Getting Started

1. `pip install -r requirements.txt`
2. Run `python models/agent_dion_nfl.py` (or `python scripts/dion_cox_merger.py` for everything)
3. Check `output/` for the reports
4. After games, grade your picks with `record_result()` (see `models/agent_dion_nfl.py`)
   so confidence baselines calibrate to your real results over time

---

**Agent Dion v1.0** | 2026 NFL Season | Learning System Active
