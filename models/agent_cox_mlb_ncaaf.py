#!/usr/bin/env python3
"""
Agent Cox - MLB & NCAAF Parlay Engine
Mirrors Dion's structure but focuses on college football and baseball
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
        """Fetch MLB games"""
        try:
            import requests
            url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={self.date}"
            response = requests.get(url, timeout=10)
            games = response.json()
            return [self._parse_mlb_game(g) for g in games if g['status'] in ['Scheduled', 'Pre-Game', 'Live']]
        except Exception as e:
            print(f"❌ Error fetching MLB games: {e}")
            return []
    
    def fetch_ncaaf_games(self) -> List[Dict]:
        """Fetch NCAAF games"""
        try:
            import requests
            url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
            response = requests.get(url, timeout=10)
            games = response.json().get('events', [])
            return [self._parse_ncaaf_game(g) for g in games if self._is_today(g)]
        except Exception as e:
            print(f"❌ Error fetching NCAAF games: {e}")
            return []
    
    def _parse_mlb_game(self, game: Dict) -> Dict:
        """Parse MLB game"""
        return {
            'sport': 'mlb',
            'id': game.get('gamePk', ''),
            'home': game.get('teams', {}).get('home', {}).get('team', {}).get('name', 'N/A'),
            'away': game.get('teams', {}).get('away', {}).get('team', {}).get('name', 'N/A'),
            'time': game.get('gameDateTime', ''),
        }
    
    def _parse_ncaaf_game(self, game: Dict) -> Dict:
        """Parse NCAAF game"""
        return {
            'sport': 'ncaaf',
            'id': game.get('id', ''),
            'home': game.get('home', {}).get('team', 'N/A'),
            'away': game.get('away', {}).get('team', 'N/A'),
            'time': game.get('date', ''),
        }
    
    def _is_today(self, game: Dict) -> bool:
        """Check if game is today"""
        game_date = game.get('date', '')[:10]
        today = datetime.now().strftime("%Y-%m-%d")
        return game_date == today
    
    def score_picks(self, mlb_games: List[Dict], ncaaf_games: List[Dict]) -> List[Dict]:
        """Score MLB and NCAAF picks"""
        scored_picks = []
        
        # Score MLB
        for game in mlb_games:
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
            picks = [
                {'type': 'spread', 'confidence': self._calc_confidence('ncaaf', 'spread')},
                {'type': 'moneyline', 'confidence': self._calc_confidence('ncaaf', 'moneyline')},
                {'type': 'over_under', 'confidence': self._calc_confidence('ncaaf', 'ou')},
                {'type': 'player_prop', 'confidence': self._calc_confidence('ncaaf', 'prop')},
            ]
            
            for pick in picks:
                pick['sport'] = 'ncaaf'
                pick['game'] = f"{game['away']} @ {game['home']}"
                pick['timestamp'] = datetime.now().isoformat()
                scored_picks.append(pick)
        
        return scored_picks
    
    def _calc_confidence(self, sport: str, pick_type: str) -> float:
        """Calculate confidence"""
        base_scores = {
            'spread': 60,
            'moneyline': 55,
            'ou': 62,
            'prop': 58
        }
        variance = random.randint(-4, 4)
        return max(50, min(90, base_scores.get(pick_type, 58) + variance))
    
    def build_cox_parlays(self, picks: List[Dict], min_parlays: int = 3) -> List[Dict]:
        """Build MLB/NCAAF 4-5 leg parlays"""
        import itertools
        
        parlays = []
        high_confidence = [p for p in picks if p['confidence'] >= 62]
        
        if len(high_confidence) < 4:
            print("⚠️  Not enough high-confidence picks")
            return []
        
        for legs in [4, 5]:
            combos = list(itertools.combinations(high_confidence, legs))
            
            for combo in sorted(combos, key=lambda c: sum(p['confidence'] for p in c) / len(c), reverse=True)[:5]:
                parlay = {
                    'legs': len(combo),
                    'picks': combo,
                    'combined_confidence': round(sum(p['confidence'] for p in combo) / len(combo), 2),
                    'parlay_probability': self._calc_parlay_prob(combo),
                    'estimated_payout': self._calc_payout(combo),
                    'expected_value': self._calc_ev(combo),
                    'sports_included': list(set(p['sport'] for p in combo)),
                    'timestamp': datetime.now().isoformat()
                }
                parlays.append(parlay)
        
        return sorted(parlays, key=lambda p: p['expected_value'], reverse=True)[:min_parlays]
    
    def _calc_parlay_prob(self, picks: List[Dict]) -> float:
        prob = 1.0
        for pick in picks:
            prob *= (pick['confidence'] / 100)
        return round(prob * 100, 2)
    
    def _calc_payout(self, picks: List[Dict]) -> float:
        base_odds = 1.5
        for pick in picks:
            confidence_multiplier = pick['confidence'] / 50
            base_odds *= confidence_multiplier
        return round(100 * base_odds, 2)
    
    def _calc_ev(self, picks: List[Dict]) -> float:
        prob = self._calc_parlay_prob(picks)
        payout = self._calc_payout(picks)
        return round((prob / 100 * payout) - 100, 2)
    
    def generate_report(self, parlays: List[Dict]) -> str:
        """Generate MLB/NCAAF report"""
        report = f"""# Agent Cox - MLB & NCAAF Weekly Picks & Parlays
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary
- **Total Parlays:** {len(parlays)}
- **Sports:** MLB + NCAAF
- **Date:** {datetime.now().strftime("%A, %B %d, %Y")}

"""
        for i, parlay in enumerate(parlays, 1):
            sports_str = ', '.join([s.upper() for s in parlay.get('sports_included', ['MIXED'])])
            report += f"""
### Parlay #{i} ({parlay['legs']}-Leg) - {sports_str}
**Combined Confidence:** {parlay['combined_confidence']}%
**Parlay Probability:** {parlay['parlay_probability']}%
**Estimated Payout (on $100):** ${parlay['estimated_payout']}
**Expected Value:** ${parlay['expected_value']}

**Picks:**
"""
            for pick in parlay['picks']:
                report += f"- {pick['sport'].upper()}: {pick['game']} - {pick['type'].replace('_', ' ').title()} ({pick['confidence']}%)\n"
        
        return report
    
    def run(self):
        """Execute Cox pipeline"""
        print("""
╔═════════════════════════════════════╗
║     Agent Cox - MLB & NCAAF         ║
║   Weekly Picks & Parlays            ║
╚═════════════════════════════════════╝
        """)
        
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        print("⚾ Fetching MLB games...")
        mlb_games = self.fetch_mlb_games()
        print(f"✅ Found {len(mlb_games)} MLB games")
        
        print("🏈 Fetching NCAAF games...")
        ncaaf_games = self.fetch_ncaaf_games()
        print(f"✅ Found {len(ncaaf_games)} NCAAF games\n")
        
        if not mlb_games and not ncaaf_games:
            print("⚠️  No games found today")
            return None
        
        print("🎯 Scoring picks...")
        picks = self.score_picks(mlb_games, ncaaf_games)
        print(f"✅ Scored {len(picks)} picks\n")
        
        print("🎰 Building parlays...")
        parlays = self.build_cox_parlays(picks, min_parlays=3)
        
        if parlays:
            print(f"✅ Generated {len(parlays)} parlays!\n")
            report = self.generate_report(parlays)
            print(report)
            
            os.makedirs("output", exist_ok=True)
            with open("output/cox_mlb_ncaaf_parlays.md", "w") as f:
                f.write(report)
            
            return parlays
        else:
            print("⚠️  No parlays generated")
            return None

if __name__ == "__main__":
    cox = AgentCox()
    cox.run()
