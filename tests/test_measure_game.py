import unittest

from tools.dev.measure_game import FRAME_T, frames_between, label_table, summarize


class SummarizeTests(unittest.TestCase):
    def events(self, gaps, work=100_000):
        """Entry/exit events for a loop that exits the wait every `gaps` frames."""
        events, exit_t = [], 0
        for gap in gaps:
            entry_t = exit_t + work
            events.append(("entry", entry_t))
            exit_t += gap * FRAME_T
            events.append(("exit", exit_t))
        events.append(("entry", exit_t + work))
        return events

    def test_frames_between_rounds_to_whole_frames(self):
        self.assertEqual(frames_between(0, 2 * FRAME_T + 40), 2)
        self.assertEqual(frames_between(10, 3 * FRAME_T - 30), 3)

    def test_two_frame_loop(self):
        result = summarize(self.events([2, 2, 2, 2]), [], [])
        self.assertEqual(result["frames_per_iteration"], 2.0)
        self.assertEqual(result["frames_histogram"], {"2": 3})
        self.assertEqual(result["work_t"]["mean"], 100_000)
        self.assertEqual(result["idle_t"]["mean"], 2 * FRAME_T - 100_000)

    def test_mixed_loop_reports_the_share_of_slow_iterations(self):
        result = summarize(self.events([2, 3, 2, 3, 2]), [], [])
        self.assertEqual(result["frames_histogram"], {"2": 2, "3": 2})
        self.assertEqual(result["frames_per_iteration"], 2.5)

    def test_routine_totals_are_per_iteration(self):
        events = self.events([2, 2, 2])
        calls = [(0, "a", 100), (0, "a", 300), (1, "a", 200), (1, "b", 50)]
        result = summarize(events, calls, ["a", "b", "never"])
        # Three iterations: 600 T of "a" in 3 calls, 50 T of "b" in 1 call.
        self.assertEqual(result["routines"]["a"], {"calls_per_iteration": 1.0, "t_per_call": 200, "t_per_iteration": 200})
        self.assertEqual(result["routines"]["b"]["t_per_iteration"], 17)
        self.assertEqual(result["routines"]["never"]["t_per_iteration"], 0)


class LabelTests(unittest.TestCase):
    def test_local_labels_are_found_in_listings(self):
        labels = label_table("platformer")
        if not labels:
            self.skipTest("platformer is not built")
        self.assertIn("_pfe_collisions", labels)
        self.assertIn("_main", labels)


if __name__ == "__main__":
    unittest.main()
