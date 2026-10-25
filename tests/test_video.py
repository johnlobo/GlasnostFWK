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


MODEL = load_module("video_model", ROOT / "tools" / "video_model.py")


class VideoModelTests(unittest.TestCase):
    def profile(self, name: str) -> dict:
        return json.loads((ROOT / "profiles" / name).read_text())

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

    def test_generation_is_reproducible(self):
        profile = ROOT / "profiles" / "standard-160x200.json"
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            for directory in (a, b):
                subprocess.run(
                    ["python3", str(ROOT / "tools" / "gen_video.py"), str(profile), "--out-dir", directory],
                    check=True,
                )
            for suffix in ("inc", "json", "md"):
                self.assertEqual(
                    (Path(a) / f"standard-160x200.{suffix}").read_bytes(),
                    (Path(b) / f"standard-160x200.{suffix}").read_bytes(),
                )


if __name__ == "__main__":
    unittest.main()
