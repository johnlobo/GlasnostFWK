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

    def test_disk_files_are_local_unique_and_dsk_only(self):
        for manifest_path in (ROOT / "examples").glob("*/example.json"):
            manifest = json.loads(manifest_path.read_text())
            entries = manifest.get("disk_files", [])
            names = [entry["name"] for entry in entries]
            symbols = [entry["symbol"] for entry in entries]
            self.assertEqual(len(names), len(set(names)), str(manifest_path))
            self.assertEqual(len(symbols), len(set(symbols)), str(manifest_path))
            if entries:
                self.assertIn("dsk", manifest.get("media", ["cdt", "dsk"]))
            for entry in entries:
                relative = Path(entry["source"])
                self.assertFalse(relative.is_absolute(), f"{manifest_path}: {relative}")
                self.assertNotIn("..", relative.parts, f"{manifest_path}: {relative}")
                self.assertTrue((manifest_path.parent / relative).is_file())

    def test_optional_modules_are_not_universally_selected(self):
        selections = {
            path.parent.name: set(json.loads(path.read_text())["modules"])
            for path in (ROOT / "examples").glob("*/example.json")
        }
        self.assertNotIn("resources/bank.s", selections["minimal"])
        self.assertNotIn("extensions/motion_u8.s", selections["board"])
        self.assertIn("resources/bank.s", selections["resources128"])
        self.assertNotIn("resources/disk.s", selections["resources128"])
        self.assertIn("resources/disk.s", selections["diskload"])
        self.assertIn("resources/zx7b.s", selections["diskload"])
        self.assertIn("audio/akg.s", selections["audio"])
        self.assertNotIn("audio/akg.s", selections["minimal"])
        self.assertIn("extensions/animation.s", selections["animation"])
        self.assertNotIn("extensions/animation.s", selections["platform"])
        self.assertIn("ui/window.s", selections["window"])
        self.assertNotIn("ui/window.s", selections["board"])
        self.assertIn("extensions/motion_u8.s", selections["vertical"])
        self.assertIn("extensions/physics_platform.s", selections["gravity"])
        self.assertNotIn("extensions/physics_8_8.s", selections["gravity"])
        self.assertIn("extensions/physics_8_8.s", selections["physics88"])
        self.assertNotIn("extensions/physics_platform.s", selections["physics88"])
        self.assertIn("extensions/tilemap.s", selections["tilecoll"])
        self.assertIn("extensions/platform_tilemap.s", selections["tilecoll"])
        self.assertNotIn("extensions/physics_8_8.s", selections["tilecoll"])
        self.assertIn("extensions/tilemap.s", selections["tilerender"])
        self.assertIn("extensions/tilemap_render.s", selections["tilerender"])
        self.assertNotIn("extensions/platform_tilemap.s", selections["tilerender"])


if __name__ == "__main__":
    unittest.main()
