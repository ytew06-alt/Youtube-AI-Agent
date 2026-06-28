# calculator/pkg/calculator.py

class GPACalculator:
    def calculate_gpa(self, courses: list[dict]) -> float:
        total_points = 0.0
        total_credits = 0.0
        grade_to_points = {
            "A": 4.0, "A-": 3.7,
            "B+": 3.3, "B": 3.0, "B-": 2.7,
            "C+": 2.3, "C": 2.0, "C-": 1.7,
            "D+": 1.3, "D": 1.0,
            "F": 0.0
        }

        for course in courses:
            grade = course.get("grade", "").upper()
            credits = course.get("credits", 0)

            if grade in grade_to_points and credits > 0:
                total_points += grade_to_points[grade] * credits
                total_credits += credits
            else:
                raise ValueError(f"Invalid grade or credits for course: {course}")

        if total_credits == 0:
            return 0.0  # Avoid division by zero if no valid courses

        return total_points / total_credits
