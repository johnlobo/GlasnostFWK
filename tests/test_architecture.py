#!/usr/bin/env python3
import json
import re
import unittest
from pathlib import Path

from tools.build.program_catalog import program_folders

ROOT = Path(__file__).resolve().parents[1]


class ArchitectureTests(unittest.TestCase):
    def test_framework_never_imports_examples(self):
        offenders = []
        for source in (ROOT / "framework" / "src").rglob("*.s"):
            if re.search(r"(?:examples/|game/)", source.read_text()):
                offenders.append(str(source.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_manifests_select_existing_modules(self):
        for manifest_path in (folder / "glasnost.manifest.json" for folder in program_folders(ROOT)):
            manifest = json.loads(manifest_path.read_text())
            for module in manifest["modules"]:
                self.assertTrue((ROOT / "framework" / "src" / module).is_file(), f"{manifest_path}: {module}")

    def test_game_sources_are_local_and_exist(self):
        for manifest_path in (folder / "glasnost.manifest.json" for folder in program_folders(ROOT)):
            manifest = json.loads(manifest_path.read_text())
            sources = manifest.get("game_sources", ["main.s"])
            self.assertIn("main.s", sources)
            for source in sources:
                relative = Path(source)
                self.assertFalse(relative.is_absolute(), f"{manifest_path}: {source}")
                self.assertNotIn("..", relative.parts, f"{manifest_path}: {source}")
                self.assertTrue((manifest_path.parent / relative).is_file(), f"{manifest_path}: {source}")

    def test_disk_files_are_local_unique_and_dsk_only(self):
        for manifest_path in (folder / "glasnost.manifest.json" for folder in program_folders(ROOT)):
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
            for path in (folder / "glasnost.manifest.json" for folder in program_folders(ROOT))
        }
        self.assertNotIn("resources/bank.s", selections["minimal"])
        resources_manifest = json.loads(
            (ROOT / "examples/resources128/glasnost.manifest.json").read_text()
        )
        self.assertTrue(resources_manifest["extended_memory"])
        self.assertNotIn("resources/bank.s", selections["resources128"])
        self.assertNotIn("resources/disk.s", selections["resources128"])
        self.assertIn("resources/disk.s", selections["diskload"])
        self.assertIn("resources/zx7b.s", selections["diskload"])
        self.assertIn("audio/akg.s", selections["audio"])
        self.assertNotIn("audio/akg.s", selections["minimal"])
        self.assertIn("ui/window.s", selections["window"])
        self.assertNotIn("ui/window.s", selections["text"])
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
        self.assertIn("video/sprite.s", selections["spriteclip"])
        self.assertNotIn("video/sprite.s", selections["minimal"])
        self.assertNotIn("ui/window.s", selections["spriteclip"])
        self.assertIn("video/sprite.s", selections["spritemask"])
        self.assertIn("video/ecs_render.s", selections["platformer"])

    def test_transparency_consumers_declare_the_project_capability(self):
        consumers = {"ui/text.s", "ui/text_mode1.s", "extensions/tilemap_render_masked.s"}
        for path in (folder / "glasnost.manifest.json" for folder in program_folders(ROOT)):
            manifest = json.loads(path.read_text())
            if consumers & set(manifest["modules"]):
                self.assertIn("transparency", manifest, str(path))

    def test_platformer_follows_the_common_inc_convention(self):
        # Project convention: every .globl, constant and macro of a game lives in
        # common.inc, which every .s file of the project imports.
        project = ROOT / "examples/platformer"
        common = (project / "common.inc").read_text()
        self.assertIn(".globl", common)
        manifest = json.loads((project / "glasnost.manifest.json").read_text())
        self.assertIn("common.inc", manifest["game_sources"])
        for name in manifest["game_sources"]:
            if not name.endswith(".s"):
                continue
            lines = [l for l in (project / name).read_text().splitlines() if not l.lstrip().startswith(";;")]
            code = "\n".join(lines)
            self.assertIn('.include "common.inc"', code, name)
            self.assertNotRegex(code, r"(?m)^\.globl", name)
            self.assertNotRegex(code, r"(?m)^[A-Za-z_][A-Za-z0-9_]*\s*=", name)
            self.assertNotRegex(code, r"(?m)^\.macro", name)

    def test_no_pre_ecs_module_survives(self):
        # Gate G4: the old entity model is gone from sources, manifests and tools.
        removed = (
            "framework/src/core/pool.s", "framework/src/core/pool.inc",
            "framework/src/video/entity_render.s", "framework/src/video/entity_render.inc",
            "framework/src/extensions/animation.s", "framework/src/extensions/animation.inc",
            "framework/src/extensions/collision_bodies.s", "framework/src/extensions/collision_bodies.inc",
            "framework/src/extensions/motion_u8.s", "framework/src/extensions/motion_u8.inc",
        )
        for name in removed:
            self.assertFalse((ROOT / name).exists(), name)
        for example in ("platform", "collision", "renderorder", "animation", "platformer_ecs"):
            self.assertFalse((ROOT / "examples" / example).exists(), example)
        legacy = re.compile(
            r"core/pool\.|video/entity_render\.|extensions/animation\.|"
            r"extensions/collision_bodies\.|extensions/motion_u8\.|"
            r"\bfwk_pool_|\bfwk_entity_render_|\bfwk_motion_u8_step\b|\bfwk_collision_body"
        )
        offenders = []
        for base in ("framework", "examples", "tools", "Makefile", ".github"):
            root = ROOT / base
            files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
            for path in files:
                if path.suffix in {".s", ".inc", ".json", ".py", ".yml", ""} and "generated" not in path.parts:
                    if legacy.search(path.read_text(errors="replace")):
                        offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
