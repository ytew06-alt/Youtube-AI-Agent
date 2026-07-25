import sys
import json
from pkg.calculator import NBAPredictor

def main() -> None:
    predictor = NBAPredictor()
    
    if len(sys.argv) < 5:
        print("NBA Score Predictor App")
        print('Usage: python main.py <team1_name> <team1_strength> <team2_name> <team2_strength>')
        print('Example: python main.py "Lakers" 90 "Warriors" 95')
        return

    try:
        team1_name = sys.argv[1]
        team1_strength = int(sys.argv[2])
        team2_name = sys.argv[3]
        team2_strength = int(sys.argv[4])

        if team1_strength < 0 or team2_strength < 0:
            raise ValueError("Team strengths cannot be negative.")

        print(f"Predicting score for {team1_name} (strength: {team1_strength}) vs {team2_name} (strength: {team2_strength})")
        predicted_scores = predictor.predict_score(team1_name, team1_strength, team2_name, team2_strength)
        
        print("\n--- Predicted Scores ---")
        for team, score in predicted_scores.items():
            print(f"{team}: {score}")

    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
