# Agent Dion - NFL Parlay Analytics & Prediction System

## Overview
Agent Dion is an intelligent learning system that tracks NFL game lines, player props, and over/under selections week-by-week. It learns from historical data, improves prediction accuracy, and generates optimized 3-5 leg parlays for maximum ROI.

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
- Generates minimum 3-leg to maximum 5-leg parlays
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
├── config/
│   └── settings.json           # System configuration & thresholds
├── data/
│   ├── weekly_picks/           # Week-by-week selections
│   ├── historical/             # Cumulative historical data
│   ├── team_stats/             # Per-team performance metrics
│   └── player_props/           # Top 20 players tracking
├── models/
│   ├── learning_engine.py      # ML/statistical learning
│   ├── parlay_builder.py       # Parlay optimization
│   └── confidence_scorer.py    # Prediction confidence calculation
├── scripts/
│   ├── ingest_weekly_picks.py  # Process weekly data
│   ├── analyze_performance.py  # Calculate metrics
│   └── generate_parlays.py     # Create optimized parlays
├── output/
│   ├── weekly_reports/         # Agent Dion's recommendations
│   └── parlay_selections/      # Curated 3-5 leg parlays
└── logs/
    └── agent_dion.log          # System activity tracking
```

## How Agent Dion Works

### Phase 1: Data Ingestion
- Weekly picks fed into the system
- Data validated and categorized by type
- Historical patterns stored for analysis

### Phase 2: Learning & Analysis
- Previous weeks' accuracy calculated
- Confidence levels assigned to each selection
- Probability matrices built from historical performance
- High-probability patterns identified

### Phase 3: Parlay Construction
- Filters picks meeting minimum confidence threshold (default: 65%)
- Builds 3-leg, 4-leg, and 5-leg parlay combinations
- Calculates payout probabilities for each parlay
- Ranks by expected value and hit probability

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
4. **Generation:** Creates ranked 3-5 leg parlays
5. **Output:** Weekly report with picks and projected ROI
6. **Tracking:** Records results for next week's learning cycle

## Confidence Thresholds

- **Green Flag (75%+):** High confidence - include in 3-leg parlays
- **Yellow Flag (65-74%):** Medium confidence - use in 4-5 leg parlays
- **Red Flag (<65%):** Low confidence - exclude or minimal use

## Parlay Structure Examples

### Conservative (3-leg)
- Best performing game line pick
- Best performing prop pick
- Best performing O/U pick
- **Target:** 60-70% hit rate

### Balanced (4-leg)
- 2 game line picks + 1 prop + 1 O/U
- **Target:** 50-60% hit rate

### Aggressive (5-leg)
- 2 game lines + 2 props + 1 O/U
- **Target:** 40-50% hit rate

## Data Retention & Continuity

All historical data persists through the season, allowing Dion to:
- Compare current performance to previous weeks
- Identify seasonal trends
- Recognize hot/cold streaks
- Improve predictions with each passing week

## Getting Started

1. Review `config/settings.json` for thresholds
2. Add Week 1 picks to `data/weekly_picks/`
3. Run `python scripts/generate_parlays.py`
4. Check `output/weekly_reports/` for recommendations

---

**Agent Dion v1.0** | 2026 NFL Season | Learning System Active
