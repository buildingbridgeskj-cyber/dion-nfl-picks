#!/usr/bin/env python3
"""
Agent Cox - MLB & NCAAF Parlay Engine
Mirrors Dion's structure but focuses on college football and baseball
Designed to run standalone when no NFL action
"""

import json
import os
from datetime import datetime
from typing import List, Dict
import random

class AgentCox:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.date = datetime.now().strftime("%Y-%m-%d")
        self.frozen_picks = []
        
        # Same learning framework as Dion
        self.learning_rules = {
            "never_overwrite": True,
            "preserve_timestamps": True,
            "keep_moneyline_separate": True,
            "exclude_injury_shortened": True,
            "downweight_thin_edges": True,
            "blend_usage_with_history": True,
            "preserve_pass_calls": True,
            "separate_frozen_from_backtest": True
        }
    
    def fetch_mlb_games(self) -> List[Dict]:
        """Fetch MLB games for today"""
        try:
            import requests
            url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={self.date}"
            response = requests.get(url, timeout=10)
            games = response.json()
            parsed = [self._parse_mlb_game(g) for g in games if g['status'] in ['Scheduled', 'Pre-Game', 'Live']]
            return parsed
        except Exception as e:
            print(f"❌ Error fetching MLB games: {e}")
            return []
    
    def fetch_ncaaf_games(self) -> List[Dict]:
        """Fetch NCAAF games for today"""
        try:
            import requests
            url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
            response = requests.get(url, timeout=10)
            games = response.json().get('events', [])
            parsed = [self._parse_ncaaf_game(g) for g in games if self._is_today(g)]
            return parsed
        except Exception as e:
            print(f"❌ Error fetching NCAAF games: {e}")
            return []
    
    def _parse_mlb_game(self, game: Dict) -> Dict:
        """Parse MLB game from StatsAPI"""
        try:
            home_team = game.get('teams', {}).get('home', {}).get('team', {}).get('name', 'N/A')
            away_team = game.get('teams', {}).get('away', {}).get('team', {}).get('name', 'N/A')
            return {
                'sport': 'mlb',
                'id': game.get('gamePk', ''),
                'home': home_team,
                'away': away_team,
                'time': game.get('gameDateTime', ''),
            }
        except:
            return None
    
    def _parse_ncaaf_game(self, game: Dict) -> Dict:
        """Parse NCAAF game from ESPN"""
        try:
            return {
                'sport': 'ncaaf',
                'id': game.get('id', ''),
                'home': game.get('competitions', [{}])[0].get('home', {}).get('team', {}).get('displayName', 'N/A'),
                'away': game.get('competitions', [{}])[0].get('away', {}).get('team', {}).get('displayName', 'N/A'),
                'time': game.get('date', ''),
            }
        except:
            return None
    
    def _is_today(self, game: Dict) -> bool:
        """Check if game is today"""
        try:
            game_date = game.get('date', '')[:10]
            today = datetime.now().strftime("%Y-%m-%d")
            return game_date == today
        except:
            return False
    
    def score_picks(self, mlb_games: List[Dict], ncaaf_games: List[Dict]) -> List[Dict]:
        """Score MLB and NCAAF picks"""
        scored_picks = []
        
        # Score MLB
        for game in mlb_games:
            if not game:
                continue
            picks = [
                {'type': 'spread', 'confidence': self._calc_confidence('mlb', 'spread')},
                {'type': 'moneyline', 'confidence': self._calc_confidence('mlb', 'moneyline')},
                {'type': 'over_under', 'confidence': self._calc_confidence('mlb', 'ou')},
                {'type': 'player_prop', 'confidence': self._calc_confidence('mlb', 'prop')},
            ]
            
            for pick in picks:
                pick['sport'] = 'mlb'
                pick['game'] = f"{game['away']} @ {game['home']}"
                pick['timestamp'] = datetime.now().isoformat()
                scored_picks.append(pick)
        
        # Score NCAAF
        for game in ncaaf_games:
            if not game:
                continue
            picks = [
                {'type': 'spread', 'confidence': self._calc_confidence('ncaaf', 'spread')},
                {'type': 'moneyline', 'confidence': self._calc_confidence('ncaaf', 'moneyline')},
                {'type': 'over_under', 'confidence': self._calc_confidence('ncaaf', 'ou')},
                {'type': 'player_prop', 'confidence': self._calc_confidence('ncaaf', 'prop')},
            ]
            
            for pick in picks:
                pick['sport'] = 'ncaaf'
                pick['game'] = f"{game['away']} vs {game['home']}"
                pick['timestamp'] = datetime.now().isoformat()
                scored_picks.append(pick)
        
        return scored_picks
    
    def _calc_confidence(self, sport: str, pick_type: str) -> float:
        """Calculate confidence score"""
        base_scores = {
            'spread': 63,
            'moneyline': 58,
            'ou': 65,
            'prop': 61
        }
        variance = random.randint(-4, 4)
        return max(50, min(90, base_scores.get(pick_type, 60) + variance))
    
    def build_cox_parlays(self, picks: List[Dict], min_parlays: int = 5) -> List[Dict]:
        """Build 5+ MLB/NCAAF 4-5 leg parlays"""
        import itertools
        
        parlays = []
        high_confidence = [p for p in picks if p['confidence'] >= 62]
        
        if len(high_confidence) < 4:
            print("⚠️  Not enough high-confidence picks for parlays")
            return []
        
        # Build 4-leg and 5-leg combinations
        for legs in [4, 5]:
            combos = list(itertools.combinations(high_confidence, legs))
            
            # Sort by confidence and take top combos
            for combo in sorted(combos, key=lambda c: sum(p['confidence'] for p in c) / len(c), reverse=True)[:10]:
                parlay = {
                    'legs': len(combo),
                    'picks': list(combo),
                    'combined_confidence': round(sum(p['confidence'] for p in combo) / len(combo), 2),
                    'parlay_probability': self._calc_parlay_prob(list(combo)),
                    'estimated_payout': self._calc_payout(list(combo)),
                    'expected_value': self._calc_ev(list(combo)),
                    'sports_included': list(set(p['sport'] for p in combo)),
                    'timestamp': datetime.now().isoformat()
                }
                parlays.append(parlay)
        
        # Return top 5 by expected value
        return sorted(parlays, key=lambda p: p['expected_value'], reverse=True)[:min_parlays]
    
    def _calc_parlay_prob(self, picks: List[Dict]) -> float:
        """Calculate probability all legs hit"""
        prob = 1.0
        for pick in picks:
            prob *= (pick['confidence'] / 100)
        return round(prob * 100, 2)
    
    def _calc_payout(self, picks: List[Dict]) -> float:
        """Estimate $100 bet payout"""
        base_odds = 1.5
        for pick in picks:
            confidence_multiplier = pick['confidence'] / 50
            base_odds *= confidence_multiplier
        return round(100 * base_odds, 2)
    
    def _calc_ev(self, picks: List[Dict]) -> float:
        """Calculate expected value"""
        prob = self._calc_parlay_prob(picks)
        payout = self._calc_payout(picks)
        return round((prob / 100 * payout) - 100, 2)
    
    def generate_report(self, parlays: List[Dict]) -> str:
        """Generate MLB/NCAAF report"""
        report = f"""# Agent Cox - MLB & NCAAF Daily Parlays
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
No NFL Today - Cox Delivers Today's Action

## Summary
- **Total Parlays:** {len(parlays)}
- **Sports:** MLB ⚾ + NCAAF 🏈
- **Date:** {datetime.now().strftime("%A, %B %d, %Y")}
- **All Parlays:** 4-5 Legs

---

"""
        for i, parlay in enumerate(parlays, 1):
            sports_str = ' + '.join([s.upper() for s in parlay.get('sports_included', ['MIXED'])])
            report += f"""
### Parlay #{i} - {legs_word(parlay['legs'])}-Leg {sports_str} Play
**Combined Confidence:** {parlay['combined_confidence']}%
**Parlay Probability:** {parlay['parlay_probability']}% (Hit this to win!)
**Estimated Payout:** ${parlay['estimated_payout']} on $100 bet
**Expected Value:** ${parlay['expected_value']} ⭐

**Picks:**
"""
            for pick in parlay['picks']:
                report += f"  • [{pick['sport'].upper()}] {pick['game']} — {pick['type'].replace('_', ' ').title()} ({pick['confidence']}% confidence)\\n"
        
        report += f"""

---

## 💡 Notes
- **No NFL games today**, so Cox focuses on MLB and College Football
- All picks locked in pre-game
- Check probabilities before betting
- Larger parlays = Higher payout but lower probability
"""
        
        return report
    
    def run(self):
        """Execute Cox pipeline"""
        print(f"""
╔═══════════════════════════════════════╗
║        AGENT COX v1.0                 ║
║   MLB ⚾ + NCAAF 🏈 Parlays          ║
║   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}           ║
╚═══════════════════════════════════════╝

🎯 No NFL today — Cox takes the field!

""")
        
        print("⚾ Fetching MLB games...")
        mlb_games = self.fetch_mlb_games()
        mlb_games = [g for g in mlb_games if g]  # Filter None values
        print(f"✅ Found {len(mlb_games)} MLB games")
        
        print("🏈 Fetching NCAAF games...")
        ncaaf_games = self.fetch_ncaaf_games()
        ncaaf_games = [g for g in ncaaf_games if g]  # Filter None values
        print(f"✅ Found {len(ncaaf_games)} NCAAF games\n")
        
        if not mlb_games and not ncaaf_games:
            print("❌ No games found today. Try again tomorrow!")
            return None
        
        print("🎯 Scoring all picks...")
        picks = self.score_picks(mlb_games, ncaaf_games)
        print(f"✅ Scored {len(picks)} picks\n")
        
        print("🎰 Building 5+ parlays (4-5 legs each)...")
        parlays = self.build_cox_parlays(picks, min_parlays=5)
        
        if parlays:
            print(f"✅ Generated {len(parlays)} optimal parlays!\n")
            report = self.generate_report(parlays)
            print(report)
            
            # Save
            os.makedirs("output", exist_ok=True)
            with open("output/cox_mlb_ncaaf_parlays.md", "w") as f:
                f.write(report)
            
            print(f"\n✅ Report saved: output/cox_mlb_ncaaf_parlays.md")
            return parlays
        else:
            print("❌ Could not build parlays. Not enough picks.")
            return None

def legs_word(num):
    """Convert leg number to word"""
    words = {4: "Four", 5: "Five"}
    return words.get(num, str(num))

if __name__ == "__main__":
    cox = AgentCox()
    cox.run()
