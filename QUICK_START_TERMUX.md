# 🚀 AGENT DION + COX - EASY TERMUX SETUP

## ⚡ Super Quick Setup (Copy-Paste Only)

### Step 1: Install & Clone (2 minutes)
```bash
pkg update && pkg install python git
cd ~
git clone https://github.com/buildingbridgeskj-cyber/dion-nfl-picks.git
cd dion-nfl-picks
pip install requests
```

### Step 2: Run Everything (1 command)
```bash
python scripts/dion_cox_merger.py
```

That's it! You'll get:
- ✅ **Dion's NFL parlays**
- ✅ **Cox's MLB/NCAAF parlays**
- ✅ **Combined best recommendations**

---

## 📊 What You Get

```
╔══════════════════════════════════════════╗
║   DION + COX UNIFIED PARLAY ENGINE       ║
║   NFL + MLB + NCAAF                      ║
║   2026-09-11 14:30:15                    ║
╚══════════════════════════════════════════╝

==================================================
RUNNING AGENT DION (NFL)
==================================================

✅ Generated 3 NFL parlays!

==================================================
RUNNING AGENT COX (MLB/NCAAF)
==================================================

✅ Generated 3 MLB/NCAAF parlays!

==================================================
MERGING RESULTS
==================================================

# Dion + Cox - Unified Daily Parlay Report
...

✅ Report saved to output/dion_cox_unified_parlays.md
```

---

## 🎯 Individual Commands

### Dion Only (NFL)
```bash
python models/agent_dion_nfl.py
```

### Cox Only (MLB/NCAAF)
```bash
python models/agent_cox_mlb_ncaaf.py
```

### Combined (Dion + Cox)
```bash
python scripts/dion_cox_merger.py
```

---

## 📁 Output Files

After running, check:

```bash
# View Dion's NFL parlays
cat output/dion_nfl_parlays.md

# View Cox's MLB/NCAAF parlays
cat output/cox_mlb_ncaaf_parlays.md

# View combined best picks
cat output/dion_cox_unified_parlays.md
```

---

## 🔄 Automate Daily (Optional)

### Cron Job (Runs Daily at 9 AM)
```bash
crontab -e

# Add this line:
0 9 * * * cd ~/dion-nfl-picks && python scripts/dion_cox_merger.py
```

### Keep Running in Background
```bash
cd ~/dion-nfl-picks
nohup python scripts/dion_cox_merger.py > dion_cox.log 2>&1 &
```

### Check Log
```bash
tail -f dion_cox.log
```

---

## 🐛 Troubleshooting

**Problem: `requests not found`**
```bash
pip install requests
```

**Problem: `No games found`**
- Likely no games today (off-season)
- Check APIs are working
- Try tomorrow

**Problem: Python version**
```bash
python --version  # Should be 3.7+
```

**Problem: Can't write files**
```bash
mkdir -p output
chmod 755 output
```

---

## 📋 What Dion Does

- Tracks all NFL picks week-by-week
- Maintains historical accuracy (Week 1: 6-4 = 60%)
- Builds 4-5 leg NFL-only parlays
- Keeps frozen picks immutable after kickoff

**Learning Rules:**
- Never overwrites prior data
- Preserves pre-game timestamps
- Separates moneyline from ATS
- Excludes injury-shortened games
- Downweights thin-edge picks
- Preserves PASS calls for calibration

---

## 📋 What Cox Does

- Tracks MLB and NCAAF picks daily
- Mirrors Dion's learning framework
- Builds 4-5 leg MLB/NCAAF-only parlays
- Tracks confidence and payouts

---

## 🏆 How Dion + Cox Merges

1. **Dion runs first** → Generates NFL parlays
2. **Cox runs second** → Generates MLB/NCAAF parlays
3. **Merger combines both** → Ranks by Expected Value
4. **Top recommendations** → Ready to use

**Ranking Formula:**
```
Expected Value = (Parlay Probability × Payout) - Risk
Higher EV = Better recommendation
```

---

## 📊 Example Output

```
# Dion + Cox - Unified Daily Parlay Report

### #1 [DION] NFL Specialist - 4-Leg Parlay
Combined Confidence: 71%
Parlay Probability: 25.3%
Estimated Payout: $347.50
Expected Value: $86.88 ⭐

Picks:
- [NFL] 49ers @ Rams - Spread (75%)
- [NFL] Patriots @ Seahawks - Over/Under (68%)
- [NFL] Lions @ Saints - Moneyline (72%)
- [NFL] Bears @ Panthers - Player Prop (69%)

---

### #2 [COX] MLB/NCAAF Specialist - 5-Leg Parlay
Combined Confidence: 68%
Parlay Probability: 14.8%
Estimated Payout: $652.30
Expected Value: $96.60 ⭐

Picks:
- [MLB] Yankees @ Mets - Over/Under (70%)
- [MLB] Dodgers @ Astros - Spread (65%)
- [NCAAF] Alabama vs Georgia - Moneyline (72%)
- [NCAAF] Ohio State vs Michigan - Spread (68%)
- [NCAAF] Notre Dame @ USC - Over/Under (62%)
```

---

## ⚙️ Configuration

Edit these files to customize:

**Change confidence thresholds:**
```bash
nano models/agent_dion_nfl.py
nano models/agent_cox_mlb_ncaaf.py
```

**Change parlay leg count (3-5):**
```python
parlays = self.build_nfl_parlays(picks, min_parlays=5)  # Change min_parlays
```

---

## 🎓 Historical Data (Week 1)

**Week 1 Summary:**
- Game 1 (Patriots @ Seahawks): 3-0 ✅
- Game 2 (49ers @ Rams): 3-4 ✅
- **Total: 6-4 (60.0% hit rate)**

All data preserved immutably in:
```
data/
├── week1/
│   ├── game1_ne_sea/
│   ├── game2_sf_la/
│   └── ...
├── week2/
├── week3/
└── ...
```

Never overwritten. Ever.

---

## 🚀 Ready to Go!

```bash
# One command to rule them all:
python scripts/dion_cox_merger.py
```

Enjoy your daily unified parlay recommendations! 🎰

---

**Agent Dion v2.0** | **Agent Cox v1.0** | NFL + MLB + NCAAF
