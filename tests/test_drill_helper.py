from datetime import date
from types import SimpleNamespace
import unittest

from app.drill_helper import default_chunks, schedule_review


class DrillHelperTests(unittest.TestCase):
    def test_schedule_review_starts_short_and_expands(self):
        today = date(2026, 7, 29)

        first = schedule_review(None, "good", today=today)
        self.assertEqual(first["interval_days"], 2)
        self.assertEqual(first["due_date"], date(2026, 7, 31))

        progress = SimpleNamespace(
            ease_factor=first["ease_factor"],
            interval_days=first["interval_days"],
            repetitions=first["repetitions"],
        )
        second = schedule_review(progress, "good", today=today)
        self.assertEqual(second["interval_days"], 5)
        self.assertEqual(second["repetitions"], 2)

    def test_schedule_review_again_resets_repetition(self):
        progress = SimpleNamespace(ease_factor=2.5, interval_days=20, repetitions=4)
        result = schedule_review(progress, "again", today=date(2026, 7, 29))

        self.assertEqual(result["repetitions"], 0)
        self.assertEqual(result["interval_days"], 1)
        self.assertAlmostEqual(result["ease_factor"], 2.3)

    def test_schedule_review_rejects_unknown_rating(self):
        with self.assertRaises(ValueError):
            schedule_review(None, "maybe")

    def test_default_chunks_reconstruct_sentence(self):
        sentence = "Please isolate the affected stock and confirm the quantity by noon."
        chunks = default_chunks(sentence)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertLessEqual(len(chunks), 7)
        self.assertEqual(" ".join(chunks), sentence)


if __name__ == "__main__":
    unittest.main()
