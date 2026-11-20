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

    def test_mode1_320x200_uses_standard_crtc_geometry(self):
        p = self.profile("mode1-320x200.json")
        self.assertEqual(GENERATOR.validate(p)["visible_bytes"], 16000)
        self.assertEqual((p["mode"], p["width_pixels"], p["width_bytes"], p["height_lines"]),
                         (1, 320, 80, 200))
        self.assertEqual(p["crtc"]["registers"], {"R1": 40, "R6": 25, "R9": 7})
        self.assertEqual(MODEL.address(p, 79, 199), 0xFFCF)
        self.assertNotIn(0xC7D0, MODEL.visible_addresses(p))

    def test_scroll_profiles_have_expected_fixed_origin_geometry(self):
        for name, mode, width, r1, r2, r13, base in (
            ("scroll-mode0-128x128.json", 0, 64, 32, 42, 0, 0xC000),
            ("scroll-mode1-128x128.json", 1, 32, 16, 34, 0, 0xC000),
        ):
            with self.subTest(profile=name):
                p = self.profile(name)
                self.assertEqual((p["mode"], p["height_lines"], p["width_bytes"]), (mode, 128, width))
                self.assertEqual(p["crtc"]["registers"],
                                 {"R1": r1, "R2": r2, "R6": 16, "R9": 7, "R12": 48, "R13": r13})
                self.assertEqual(GENERATOR.validate(p)["visible_bytes"], width * 128)
                self.assertTrue(p["raster_bank_wrap_2k"])
                self.assertIn("FWK_VIDEO_RASTER_BANK_WRAP_2K = 1", GENERATOR.asm(p, GENERATOR.validate(p)))
                self.assertEqual(MODEL.address(p, 0, 0), base)
                self.assertEqual(MODEL.address(p, 0, 8), base + width)
                self.assertEqual(MODEL.address(p, width - 1, 127),
                                 base + 0x3800 + width * 16 - 1)

    def test_128_pixel_horizontal_candidate_overlaps_visible_next_row(self):
        for name, tile_width in (
            ("scroll-mode0-128x128.json", 4),
            ("scroll-mode1-128x128.json", 2),
        ):
            with self.subTest(profile=name):
                p = self.profile(name)
                current = MODEL.visible_at_origin(p, 0)
                self.assertEqual(len(current), p["width_bytes"] * 128)
                base = MODEL.address(p, 0, 0)
                self.assertEqual(MODEL.address_at_origin(p, 0, 0, tile_width), base + tile_width)
                self.assertEqual(MODEL.address_at_origin(p, 0, 0, -tile_width),
                                 base + 0x800 - tile_width)
                self.assertEqual(MODEL.address_at_origin(p, 0, 1, -tile_width),
                                 base + 0x1000 - tile_width)
                east_conflict = MODEL.unsafe_pre_switch_fill(p, 0, tile_width, "east", tile_width)
                west_conflict = MODEL.unsafe_pre_switch_fill(p, 0, -tile_width, "west", tile_width)
                self.assertTrue(east_conflict)
                self.assertTrue(west_conflict)
                # The next row's first byte is an entering right-edge byte.
                self.assertIn(base + p["width_bytes"], east_conflict)

    def test_scroll_candidate_full_camera_grid_cannot_prefill_horizontal_strip(self):
        for name, tile_width, horizontal_conflict in (
            ("scroll-mode0-128x128.json", 4, 480),
            ("scroll-mode1-128x128.json", 2, 240),
        ):
            with self.subTest(profile=name):
                p = self.profile(name)
                row_bytes = p["width_bytes"]
                for y in range(9):
                    for x in range(9):
                        current = x * tile_width + y * row_bytes
                        for direction, dx, dy in (("east", 1, 0), ("west", -1, 0),
                                                  ("south", 0, 1), ("north", 0, -1)):
                            if not (0 <= x + dx <= 8 and 0 <= y + dy <= 8):
                                continue
                            next_origin = (x + dx) * tile_width + (y + dy) * row_bytes
                            unsafe = MODEL.unsafe_pre_switch_fill(
                                p, current, next_origin, direction, tile_width)
                            self.assertEqual(len(unsafe), horizontal_conflict if dx else 0,
                                             (name, x, y, direction))

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
