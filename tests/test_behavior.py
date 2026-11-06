import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BehaviorTests(unittest.TestCase):
    def test_wait_macro_terminates_its_condition_table(self):
        include = (ROOT / "src/extensions/behavior.inc").read_text()
        wait_macro = include.split(".macro FWK_BEHAVIOR_WAIT", 1)[1].split(
            ".endm", 1
        )[0]
        self.assertIn("FWK_BEHAVIOR_CONDITION timeout, _next", wait_macro)
        self.assertIn("FWK_BEHAVIOR_CONDITIONS_END", wait_macro)


if __name__ == "__main__":
    unittest.main()
