import unittest
from pathlib import Path

from tools.mutate_platformer import MUTATIONS

ROOT = Path(__file__).resolve().parents[1]


class MutationTableTests(unittest.TestCase):
    """Kept apart from test_ecs_manager: the mutation runner executes that module
    on mutated sources, and this check must not count as a detection."""

    def test_mutation_table_still_matches_main_s(self):
        main = (ROOT / "examples/platformer/main.s").read_text()
        names = [name for name, _old, _new in MUTATIONS]
        self.assertEqual(len(names), len(set(names)))
        for name, old, new in MUTATIONS:
            self.assertEqual(main.count(old), 1, f"mutation {name!r} no longer matches main.s once")
            self.assertNotEqual(old, new, name)


if __name__ == "__main__":
    unittest.main()
