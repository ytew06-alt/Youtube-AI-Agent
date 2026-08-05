import random

class NBAPredictor:
    def predict_score(self, team1_name: str, team1_strength: int, team2_name: str, team2_strength: int) -> dict:
        if not isinstance(team1_strength, int) or not isinstance(team2_strength, int) or team1_strength < 0 or team2_strength < 0:
            raise ValueError("Team strengths must be non-negative integers.")

        # Updated Base scores
        base_score_team1 = 100
        base_score_team2 = 100

        # Updated Increased sensitivity to strength
        strength_difference = team1_strength - team2_strength
        
        # Updated Larger impact from strength
        score_team1 = base_score_team1 + (strength_difference * 2.0) + random.randint(-10, 10)
        score_team2 = base_score_team2 - (strength_difference * 2.0) + random.randint(-10, 10)
        
        # Ensure scores are within range
        score_team1 = int(max(90, min(150, score_team1)))
        score_team2 = int(max(90, min(150, score_team2)))

        return {
            team1_name: score_team1,
            team2_name: score_team2
        }
