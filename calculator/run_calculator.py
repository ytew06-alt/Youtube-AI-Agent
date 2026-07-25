import subprocess
import sys

if __name__ == "__main__":
    # Example 1: Lakers vs Warriors
    subprocess.run([sys.executable, "main.py", "Lakers", "90", "Warriors", "85"])

    # Example 2: Celtics vs Heat (more even match)
    subprocess.run([sys.executable, "main.py", "Celtics", "88", "Heat", "88"])

    # Example 3: Bulls vs Knicks (one much stronger)
    subprocess.run([sys.executable, "main.py", "Bulls", "75", "Knicks", "95"])
