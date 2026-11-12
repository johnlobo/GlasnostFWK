#!/usr/bin/env python3
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("video_model", ROOT / "tools" / "build" / "video_model.py")
GENERATOR = load_module("gen_video", ROOT / "tools" / "build" / "gen_video.py")


class VideoModelTests(unittest.TestCase):
    def profile(self, name: str) -> dict:
        return json.loads((ROOT / "framework" / "profiles" / name).read_text())

    def test_standard_known_addresses(self):
        p = self.profile("standard-160x200.json")
        known = {
            (0, 0): 0xC000,
            (79, 0): 0xC04F,
            (0, 1): 0xC800,
            (0, 7): 0xF800,
            (0, 8): 0xC050,
            (79, 199): 0xFFCF,
        }
        for (x, y), expected in known.items():
            self.assertEqual(MODEL.address(p, x, y), expected)

    def test_standard_holes_preserved_by_visible_set(self):
        p = self.profile("standard-160x200.json")
        visible = MODEL.visible_addresses(p)
        for block in range(8):
            hole = 0xC000 + block * 0x800 + 2000
            self.assertNotIn(hole, visible)
            self.assertNotIn(hole + 47, visible)
        self.assertEqual(len(visible), 16000)

    def test_experimental_has_no_alias_and_crosses_boundary(self):
        p = self.profile("experimental-160x288.json")
        visible = MODEL.visible_addresses(p)
        self.assertEqual(len(visible), 80 * 288)
        self.assertEqual(MODEL.address(p, 0, 127), 0xBEB0)
        self.assertEqual(MODEL.address(p, 0, 128), 0xC000)
        self.assertEqual(MODEL.address(p, 79, 287), 0xFE3F)

    def test_mode1_192x192_addresses_and_holes(self):
        p = self.profile("mode1-192x192.json")
        self.assertEqual(GENERATOR.load_profile(ROOT / "framework/profiles/mode1-192x192.json"), p)
        self.assertEqual(GENERATOR.validate(p)["visible_bytes"], 48 * 192)
        self.assertEqual((p["mode"], p["width_pixels"], p["width_bytes"], p["height_lines"]),
                         (1, 192, 48, 192))
        self.assertEqual(MODEL.address(p, 0, 0), 0xC000)
        self.assertEqual(MODEL.address(p, 47, 0), 0xC02F)
        self.assertEqual(MODEL.address(p, 0, 1), 0xC800)
        self.assertEqual(MODEL.address(p, 0, 8), 0xC030)
        self.assertEqual(MODEL.address(p, 47, 191), 0xFC7F)
        visible = MODEL.visible_addresses(p)
        self.assertEqual(len(visible), 48 * 192)
        self.assertNotIn(0xC480, visible)

    def test_mode1_rejects_wrong_pixel_width(self):
        profile = self.profile("mode1-192x192.json")
        profile["width_pixels"] = 96
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, "Mode 1 requires width_pixels"):
                GENERATOR.load_profile(path)

    def test_generation_is_reproducible(self):
        profile = ROOT / "framework" / "profiles" / "standard-160x200.json"
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            for directory in (a, b):
                subprocess.run(
                    ["python3", str(ROOT / "tools" / "build" / "gen_video.py"), str(profile), "--out-dir", directory],
                    check=True,
                )
            for suffix in ("inc", "json", "md"):
                self.assertEqual(
                    (Path(a) / f"standard-160x200.{suffix}").read_bytes(),
                    (Path(b) / f"standard-160x200.{suffix}").read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
