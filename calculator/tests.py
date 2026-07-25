import unittest
from pkg.calculator import NBAPredictor

class TestNBAPredictor(unittest.TestCase):
    def setUp(self) -> None:
        self.predictor = NBAPredictor()

    def test_predict_score_basic(self) -> None:
        team1_name = "Lakers"
        team1_strength = 90
        team2_name = "Warriors"
        team2_strength = 95
        
        predicted_scores = self.predictor.predict_score(team1_name, team1_strength, team2_name, team2_strength)
        
        self.assertIsInstance(predicted_scores, dict)
        self.assertIn(team1_name, predicted_scores)
        self.assertIn(team2_name, predicted_scores)
        self.assertIsInstance(predicted_scores[team1_name], int)
        self.assertIsInstance(predicted_scores[team2_name], int)
        
        # Check if scores are within a reasonable range (e.g., 80-140)
        self.assertGreaterEqual(predicted_scores[team1_name], 80)
        self.assertLessEqual(predicted_scores[team1_name], 140)
        self.assertGreaterEqual(predicted_scores[team2_name], 80)
        self.assertLessEqual(predicted_scores[team2_name], 140)

    def test_predict_score_equal_strength(self) -> None:
        team1_name = "Celtics"
        team1_strength = 90
        team2_name = "Heat"
        team2_strength = 90
        
        predicted_scores = self.predictor.predict_score(team1_name, team1_strength, team2_name, team2_strength)
        
        self.assertIsInstance(predicted_scores, dict)
        self.assertIn(team1_name, predicted_scores)
        self.assertIn(team2_name, predicted_scores)

    def test_predict_score_one_much_stronger(self) -> None:
        team1_name = "Bulls"
        team1_strength = 75
        team2_name = "Knicks"
        team2_strength = 100
        
        predicted_scores = self.predictor.predict_score(team1_name, team1_strength, team2_name, team2_strength)
        
        self.assertIsInstance(predicted_scores, dict)
        self.assertIn(team1_name, predicted_scores)
        self.assertIn(team2_name, predicted_scores)
        
    def test_invalid_strength_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            self.predictor.predict_score("TeamA", -10, "TeamB", 90)
        
        with self.assertRaises(ValueError):
            self.predictor.predict_score("TeamA", 90, "TeamB", -5)
            
        with self.assertRaises(ValueError):
            self.predictor.predict_score("TeamA", "invalid", "TeamB", 90) # type: ignore
            
        with self.assertRaises(ValueError):
            self.predictor.predict_score("TeamA", 90, "TeamB", "invalid") # type: ignore


if __name__ == "__main__":
    unittest.main()
