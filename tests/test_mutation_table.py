import unittest
from pathlib import Path

from tools.mutate_platformer import MUTATIONS

ROOT = Path(__file__).resolve().parents[1]


class MutationTableTests(unittest.TestCase):
    """Kept apart from test_ecs_manager: the mutation runner executes that module
    on mutated sources, and this check must not count as a detection."""

    def test_mutation_table_still_matches_the_sources(self):
        sources = [
            (ROOT / "examples/platformer" / name).read_text() for name in ("main.s", "common.inc")
        ]
        names = [name for name, _old, _new in MUTATIONS]
        self.assertEqual(len(names), len(set(names)))
        for name, old, new in MUTATIONS:
            total = sum(text.count(old) for text in sources)
            self.assertEqual(total, 1, f"mutation {name!r} no longer matches main.s/common.inc once")
            self.assertNotEqual(old, new, name)


if __name__ == "__main__":
    unittest.main()
