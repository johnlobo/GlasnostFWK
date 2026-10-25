#!/usr/bin/env python3
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ArchitectureTests(unittest.TestCase):
    def test_framework_never_imports_examples(self):
        offenders = []
        for source in (ROOT / "src").rglob("*.s"):
            if re.search(r"(?:examples/|game/)", source.read_text()):
                offenders.append(str(source.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_manifests_select_existing_modules(self):
        for manifest_path in (ROOT / "examples").glob("*/example.json"):
            manifest = json.loads(manifest_path.read_text())
            for module in manifest["modules"]:
                self.assertTrue((ROOT / "src" / module).is_file(), f"{manifest_path}: {module}")

    def test_optional_modules_are_not_universally_selected(self):
        selections = {
            path.parent.name: set(json.loads(path.read_text())["modules"])
            for path in (ROOT / "examples").glob("*/example.json")
        }
        self.assertNotIn("resources/bank.s", selections["minimal"])
        self.assertNotIn("extensions/motion_u8.s", selections["board"])
        self.assertIn("resources/bank.s", selections["resources128"])


if __name__ == "__main__":
    unittest.main()
