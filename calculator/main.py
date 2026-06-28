# calculator/main.py

import sys
import json
from pkg.calculator import GPACalculator

def print_course_table(courses: list[dict]) -> None:
    print("\n--- Course Details ---")
    print(f"{'Course':<30} {'Grade':<10} {'Credits':<10}")
    print(f"{'-'*30} {'-'*10} {'-'*10}")
    for course in courses:
        name = course.get("name", "N/A")
        grade = course.get("grade", "N/A")
        credits = course.get("credits", 0)
        print(f"{name:<30} {grade:<10} {credits:<10}")
    print(f"{'-'*30} {'-'*10} {'-'*10}")

def main() -> None:
    gpa_calculator = GPACalculator()
    
    if len(sys.argv) <= 1:
        print("GPA Calculator App")
        print('Usage: python main.py "[{\"name\": \"Math\", \"grade\": \"A\", \"credits\": 3}, {\"name\": \"Science\", \"grade\": \"B+\", \"credits\": 4}]"')
        print('Example: python main.py "[{\"name\": \"Math\", \"grade\": \"A\", \"credits\": 3}, {\"name\": \"Science\", \"grade\": \"B+\", \"credits\": 4}]"')
        return

    try:
        # Assuming the input is a JSON string representing a list of course dictionaries
        courses_str = " ".join(sys.argv[1:])
        courses = json.loads(courses_str)
        
        if not isinstance(courses, list):
            raise ValueError("Input must be a JSON list of courses.")
        
        print_course_table(courses)
        gpa = gpa_calculator.calculate_gpa(courses)
        print(f"\nCalculated GPA: {gpa:.2f}")

    except json.JSONDecodeError:
        print("Error: Invalid JSON input. Please provide a valid JSON string for courses.")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
