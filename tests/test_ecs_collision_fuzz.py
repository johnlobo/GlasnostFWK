import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import ecs_collision_fuzz as fuzz  # noqa: E402

CORRECTNESS = [name for name in fuzz.SUITES if not name.startswith("perf")]
# Modelling the 255-slot worlds costs seconds on the host; the emulator run
# (tests/ecs_collision_fuzz.py) is where those are checked.
HEAVY = {"big", "big2", "single", "perf", "perf255", "perf255x"}


class FuzzModelTests(unittest.TestCase):
    """The emulator run is manual and slow; these keep the host side honest."""

    def test_every_suite_builds_cases_and_models_run(self):
        for name in fuzz.SUITES:
            with self.subTest(suite=name):
                cases = fuzz.SUITES[name]()
                self.assertTrue(cases)
                if name in HEAVY:
                    continue
                for case in cases[:25]:
                    records = fuzz.Model(case, 0x4000, 0x8000).run()
                    self.assertEqual(len(records), len(case.calls))

    def test_cases_are_deterministic(self):
        for name in CORRECTNESS:
            with self.subTest(suite=name):
                first = b"".join(fuzz.blob([c]) for c in fuzz.SUITES[name]()[:10])
                second = b"".join(fuzz.blob([c]) for c in fuzz.SUITES[name]()[:10])
                self.assertEqual(first, second)

    def test_harness_example_is_registered_and_documented(self):
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("ecsfuzz", makefile.split("EXAMPLES :=", 1)[1].splitlines()[0])
        self.assertIn("ecs_collision_fuzz.py", (ROOT / "docs/manual.html").read_text())


if __name__ == "__main__":
    unittest.main()
