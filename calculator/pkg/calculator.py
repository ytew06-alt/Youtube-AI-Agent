import random

class NBAPredictor:
    def predict_score(self, team1_name: str, team1_strength: int, team2_name: str, team2_strength: int) -> dict:
        if not isinstance(team1_strength, int) or not isinstance(team2_strength, int) or team1_strength < 0 or team2_strength < 0:
            raise ValueError("Team strengths must be non-negative integers.")

        # Base scores in a realistic NBA range
        base_score_team1 = 100
        base_score_team2 = 100

        # Adjust base scores based on relative strength
        # A smaller multiplier for strength to keep scores realistic
        # Difference in strength matters more than absolute strength
        strength_difference = team1_strength - team2_strength
        
        # Apply a smaller, more nuanced adjustment for strength
        score_team1 = base_score_team1 + (strength_difference * 0.5) + random.randint(-15, 15)
        score_team2 = base_score_team2 - (strength_difference * 0.5) + random.randint(-15, 15)
        
        # Ensure scores are within a plausible NBA range (e.g., 80-140)
        score_team1 = int(max(80, min(140, score_team1)))
        score_team2 = int(max(80, min(140, score_team2)))

        return {
            team1_name: score_team1,
            team2_name: score_team2
        }
