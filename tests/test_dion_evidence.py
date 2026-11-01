import unittest
from datetime import datetime, timedelta, timezone
from scripts.dion_evidence import extract_boxscore, estimate_candidate, opponent_factor
from scripts.dion_elite_board import choose_top_12
from scripts.dion_validation import grade_item


class EvidenceTests(unittest.TestCase):
    def test_espn_boxscore_player_stat_parse(self):
        sample = {"boxscore": {
            "teams": [{"team": {"id": "6", "abbreviation": "DAL"}}],
            "players": [{"team": {"id": "6"}, "statistics": [
                {"name": "passingYards", "labels": ["YDS", "C/ATT", "TD", "INT", "RTG"],
                 "athletes": [{"athlete": {"fullName": "Sample QB"},
                               "stats": ["285", "25/38", "3", "1", "110.0"]}]},
                {"name": "receivingYards", "labels": ["REC", "YDS", "AVG", "TD"],
                 "athletes": [{"athlete": {"fullName": "Sample WR"},
                               "stats": ["7", "91", "13.0", "1"]}]},
            ]}]}}
        players, totals = extract_boxscore(sample)
        self.assertEqual(players[("DAL", "sample qb")][("passing", "yds")], 285)
        self.assertEqual(players[("DAL", "sample qb")][("passing", "td")], 3)
        self.assertEqual(players[("DAL", "sample wr")][("receiving", "rec")], 7)
        self.assertEqual(totals[("DAL", "receiving", "yds")], 91)

    def test_recent_results_create_non_market_projection(self):
        start = datetime(2026, 9, 6, tzinfo=timezone.utc)
        history = {("DAL", "sample wr"): [
            (start + timedelta(days=7 * i), {("receiving", "yds"): value})
            for i, value in enumerate([74, 65, 80, 88, 63, 95, 77, 86])
        ]}
        item = {"team": "DAL", "player": "Sample WR", "market": "Receiving yards",
                "selection": "Over", "line": "58.5", "odds": "-110",
                "market_prob": 0.5, "source": "DraftKings via The Odds API"}
        rated = estimate_candidate(item, history, {}, {}, {},
                                   "2026-11-01")
        self.assertEqual(rated["sample"], 8)
        self.assertEqual(rated["last5"], "5/5")
        self.assertGreater(rated["model_pct"], 50)
        self.assertGreater(rated["projection"], 58.5)
        self.assertIsNotNone(rated["elite_score"])
        self.assertIn("uncalibrated", rated["status"])

    def test_missing_history_does_not_generate_score(self):
        item = {"team": "DAL", "player": "Unknown", "market": "Rushing yards",
                "selection": "Over", "line": "40.5", "odds": "-110"}
        rated = estimate_candidate(item, {}, {}, {}, {}, "2026-11-01")
        self.assertIsNone(rated["model_pct"])
        self.assertIsNone(rated["elite_score"])
        self.assertTrue(rated["status"].startswith("PASS"))

    def test_opponent_context_does_not_invent_adjustment(self):
        factor, ready = opponent_factor("DAL", "ARI", "Receiving yards", {}, {})
        self.assertEqual(factor, 1.0)
        self.assertFalse(ready)

    def test_pregame_grading_from_actual_stat(self):
        pick = {"market": "Receiving yards", "player": "Sample WR",
                "team": "DAL", "line": "67.5", "side": "Over"}
        box = {("DAL", "sample wr"): {("receiving", "yds"): 82}}
        self.assertEqual(grade_item(pick, box), ("WIN", 82))
        pick["side"] = "Under"
        self.assertEqual(grade_item(pick, box), ("LOSS", 82))
        pick["line"] = "82"
        self.assertEqual(grade_item(pick, box), ("PUSH", 82))

    def test_six_per_team_when_available(self):
        game = {"away_abbr": "ARI", "home_abbr": "DAL"}
        rows = []
        for team in ("ARI", "DAL"):
            for i in range(9):
                rows.append({"team": team, "player": f"{team} player {i}",
                             "market": "Rushing yards", "selection": "Over",
                             "line": str(40.5 + i), "odds": "-110",
                             "elite_score": 75-i, "edge_pct": 7,
                             "status": "REVIEW ONLY"})
        top = choose_top_12(rows, game)
        self.assertEqual(len(top), 12)
        self.assertEqual(sum(r["team"] == "ARI" for r in top), 6)
        self.assertEqual(sum(r["team"] == "DAL" for r in top), 6)


if __name__ == "__main__":
    unittest.main()
