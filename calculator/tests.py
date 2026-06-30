import unittest
from pkg.calculator import GPACalculator


class TestGPACalculator(unittest.TestCase):
    def setUp(self) -> None:
        self.gpa_calculator = GPACalculator()

    def test_basic_gpa_calculation(self) -> None:
        courses = [
            {"name": "Math", "grade": "A", "credits": 3},
            {"name": "Science", "grade": "B", "credits": 4},
            {"name": "English", "grade": "C", "credits": 3},
        ]
        expected_gpa = (4.0 * 3 + 3.0 * 4 + 2.0 * 3) / (3 + 4 + 3)
        self.assertAlmostEqual(self.gpa_calculator.calculate_gpa(courses), expected_gpa, places=2)

    def test_gpa_with_various_grades(self) -> None:
        courses = [
            {"name": "History", "grade": "A-", "credits": 3},
            {"name": "Art", "grade": "B+", "credits": 2},
            {"name": "PE", "grade": "D", "credits": 1},
        ]
        expected_gpa = (3.7 * 3 + 3.3 * 2 + 1.0 * 1) / (3 + 2 + 1)
        self.assertAlmostEqual(self.gpa_calculator.calculate_gpa(courses), expected_gpa, places=2)

    def test_gpa_with_zero_credits(self) -> None:
        courses = [
            {"name": "Math", "grade": "A", "credits": 0},
            {"name": "Science", "grade": "B", "credits": 4},
        ]
        # Courses with zero credits should be ignored, so GPA is based only on Science
        expected_gpa = 3.0
        self.assertAlmostEqual(self.gpa_calculator.calculate_gpa(courses), expected_gpa, places=2)

    def test_empty_courses_list(self) -> None:
        courses = []
        self.assertEqual(self.gpa_calculator.calculate_gpa(courses), 0.0)

    def test_invalid_grade_raises_error(self) -> None:
        courses = [
            {"name": "Math", "grade": "X", "credits": 3},
        ]
        with self.assertRaises(ValueError):
            self.gpa_calculator.calculate_gpa(courses)

    def test_invalid_credits_raises_error(self) -> None:
        courses = [
            {"name": "Science", "grade": "A", "credits": -1},
        ]
        with self.assertRaises(ValueError):
            self.gpa_calculator.calculate_gpa(courses)
            
    def test_case_insensitivity_of_grades(self) -> None:
        courses = [
            {"name": "Math", "grade": "a", "credits": 3},
            {"name": "Science", "grade": "b+", "credits": 4},
        ]
        expected_gpa = (4.0 * 3 + 3.3 * 4) / (3 + 4)
        self.assertAlmostEqual(self.gpa_calculator.calculate_gpa(courses), expected_gpa, places=2)


if __name__ == "__main__":
    unittest.main()
