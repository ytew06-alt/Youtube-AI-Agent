import random

def roll_dice(times=1):
    results = []
    for _ in range(times):
        die1 = random.randint(1, 6)
        die2 = random.randint(1, 6)
        results.append((die1, die2))
    return results

if __name__ == "__main__":
    # Simulate rolling 3 times
    for roll in roll_dice(3):
        print(f'Rolled: {roll}')
