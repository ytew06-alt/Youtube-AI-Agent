import random

def play_game(attempts=5):
    number_to_guess = random.randint(1, 100)
    print(f"You have {attempts} attempts to guess the number between 1 and 100.")
    
    for attempt in range(1, attempts + 1):
        try:
            guess = int(input(f'Attempt {attempt}/{attempts}: '))
            
            if guess < number_to_guess:
                print('Too low!')
            elif guess > number_to_guess:
                print('Too high!')
            else:
                print('Congratulations! You guessed the number.')
                return
        except ValueError:
            print('Please enter a valid number')
    
    print(f'Game over! The number was {number_to_guess}')

if __name__ == "__main__":
    play_game()
