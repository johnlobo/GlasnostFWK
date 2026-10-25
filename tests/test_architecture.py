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

    def test_game_sources_are_local_and_exist(self):
        for manifest_path in (ROOT / "examples").glob("*/example.json"):
            manifest = json.loads(manifest_path.read_text())
            sources = manifest.get("game_sources", ["main.s"])
            self.assertIn("main.s", sources)
            for source in sources:
                relative = Path(source)
                self.assertFalse(relative.is_absolute(), f"{manifest_path}: {source}")
                self.assertNotIn("..", relative.parts, f"{manifest_path}: {source}")
                self.assertTrue((manifest_path.parent / relative).is_file(), f"{manifest_path}: {source}")

    def test_optional_modules_are_not_universally_selected(self):
        selections = {
            path.parent.name: set(json.loads(path.read_text())["modules"])
            for path in (ROOT / "examples").glob("*/example.json")
        }
        self.assertNotIn("resources/bank.s", selections["minimal"])
        self.assertNotIn("extensions/motion_u8.s", selections["board"])
        self.assertIn("resources/bank.s", selections["resources128"])
        self.assertIn("extensions/motion_u8.s", selections["vertical"])


if __name__ == "__main__":
    unittest.main()
