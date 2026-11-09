import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.build.gen_ecs_profile import DEFAULT_PORTFOLIO, generate

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / d) for d in ("glasnost", "build", "dev")]

import ecs_render_model as model  # noqa: E402

CPCT = Path(os.environ.get("CPCT_NEXT_PATH", "/config/workspace/cpctelera_next/cpctelera"))
ASSEMBLER = CPCT / "tools/sdcc-4.5.0/bin/sdasz80"

# ABI 8 budget, measured with project transparency ON (the larger build). The
# renderer was 1,150 bytes (a bit over half of the previous renderer, 2,078 bytes);
# the background pools (allocate, free, reset) added 235 and replaced the buffer
# every project used to declare by hand for each entity.
CODE_BUDGET = 1400
DATA_BUDGET = 40


class RenderOracleTests(unittest.TestCase):
    """The oracle must stay strong: weak scenarios let real defects through."""

    @classmethod
    def setUpClass(cls):
        cls.ideal = model.ideal_frames()

    def test_every_command_kind_is_exercised(self):
        kinds = {cmd for frame in model.SCENARIO for cmd, _, _ in frame.commands}
        self.assertEqual(kinds, set(range(6)))

    def test_images_have_the_full_visible_size(self):
        self.assertEqual(len(self.ideal), model.FRAMES)
        for image in self.ideal:
            self.assertEqual(len(image), model.SCREEN_WIDTH * model.SCREEN_HEIGHT)

    def test_an_entity_pixel_lands_where_the_layout_says(self):
        # Frame 1 places entity 0 (3 bytes wide, 8 lines) at x=20, y=60 with
        # entity 1 over it later in Y order only partly: its first byte at
        # (20, 60) is visible there.
        frame = model.SCENARIO[1].commands
        self.assertEqual(frame[0], (model.CMD_NONE, 20, 60))
        sprite = model.sprite_bytes(0)
        pixel = self.ideal[1][60 * model.SCREEN_WIDTH + 20]
        self.assertIn(pixel, (sprite[0], model.sprite_bytes(1)[0], model.sprite_bytes(2)[0],
                              model.sprite_bytes(5)[0], model.sprite_bytes(7)[0]))

    def test_background_formula_and_screen_layout(self):
        self.assertEqual(model.vram_address(0, 0), 0xC000)
        self.assertEqual(model.vram_address(0, 1), 0xC800)
        self.assertEqual(model.vram_address(79, 8), 0xC000 + 80 + 79)
        self.assertEqual(model.background_byte(0xC001), (5 * 1 + 0xC0) & 0xFF)

    def test_there_are_overlaps_whose_draw_order_differs_from_slot_order(self):
        """Mutation 'draw without sorting' only shows with such pairs on screen."""
        found = 0
        for index, frame in enumerate(model.SCENARIO[:4]):
            pos = {e: (x, y) for e, (_, x, y) in enumerate(frame.commands)}
            for a in range(len(model.ENTITIES)):
                for b in range(a + 1, len(model.ENTITIES)):
                    (xa, ya), (xb, yb) = pos[a], pos[b]
                    wa, ha = model.ENTITIES[a][1:3]
                    wb, hb = model.ENTITIES[b][1:3]
                    key_a, key_b = ya + model.ENTITIES[a][3], yb + model.ENTITIES[b][3]
                    overlap = xa < xb + wb and xb < xa + wa and ya < yb + hb and yb < ya + ha
                    if overlap and key_a > key_b:      # later slot must be drawn first
                        found += 1
        self.assertGreaterEqual(found, 4)

    def test_equal_keys_overlap_in_the_same_and_in_different_managers(self):
        """Ties made the real renderer leave ghosts; the scenario must keep them."""
        same = cross = 0
        for frame in (model.SCENARIO[1], model.SCENARIO[3]):
            pos = {e: (x, y) for e, (_, x, y) in enumerate(frame.commands)}
            for a in range(len(model.ENTITIES)):
                for b in range(a + 1, len(model.ENTITIES)):
                    (xa, ya), (xb, yb) = pos[a], pos[b]
                    wa, ha, oa = model.ENTITIES[a][1:4]
                    wb, hb, ob = model.ENTITIES[b][1:4]
                    overlap = xa < xb + wb and xb < xa + wa and ya < yb + hb and yb < ya + ha
                    if overlap and ya + oa == yb + ob:
                        if model.ENTITIES[a][0] == model.ENTITIES[b][0]:
                            same += 1
                        else:
                            cross += 1
        self.assertGreaterEqual(same, 2)
        self.assertGreaterEqual(cross, 2)

    def test_edge_clipping_case_is_present(self):
        self.assertEqual(model.SCENARIO[4].commands[0][1:], (78, 196))

    def test_committed_scenario_include_is_current(self):
        committed = (ROOT / "examples/ecsrender/scenario.inc").read_text()
        self.assertEqual(committed, model.render_include())


@unittest.skipUnless(ASSEMBLER.is_file(), "CPCtelera Next assembler is not installed")
class RenderBudgetTests(unittest.TestCase):
    """The size budget is part of the contract: a regression fails the build."""

    def assemble(self, manifest: dict, transparency: bool = True):
        portfolio = json.loads(DEFAULT_PORTFOLIO.read_text(encoding="utf-8"))
        profile = json.loads((ROOT / "framework/profiles/standard-160x200.json").read_text())
        include = generate(manifest, portfolio, profile).include
        stage = ROOT / "build" / "ecsrender" / "src"
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "core").mkdir()
            (work / "video").mkdir()
            (work / "ecs_profile.inc").write_text(include, encoding="ascii")
            config = stage / "project_config.inc"
            if not config.is_file():
                self.skipTest("run `make examples` first: project_config.inc is generated")
            text = config.read_text().replace(
                "FWK_TRANSPARENCY_ENABLED = 0", f"FWK_TRANSPARENCY_ENABLED = {int(transparency)}")
            (work / "project_config.inc").write_text(text)
            shutil.copy(ROOT / "framework/src/core/ecs_manager.inc", work / "core")
            for name in ("ecs_render.inc", "ecs_render.s", "sprite.inc"):
                shutil.copy(ROOT / "framework/src/video" / name, work / "video" / name)
            result = subprocess.run(
                [str(ASSEMBLER), "-l", "-o", "video/ecs_render.s"],
                cwd=work, capture_output=True, text=True,
            )
            rel = (work / "video/ecs_render.rel").read_text() if result.returncode == 0 else ""
            return result, rel

    @staticmethod
    def sizes(rel: str) -> tuple[int, int]:
        code = data = 0
        for area, size in re.findall(r"^A (\S+) size ([0-9A-Fa-f]+)", rel, re.M):
            if area.startswith("_CODE"):
                code += int(size, 16)
            else:
                data += int(size, 16)
        return code, data

    def test_code_and_data_stay_inside_the_budget(self):
        manifest = {"ecs": {"x_format": "u8", "y_format": "u8", "components": []}}
        result, rel = self.assemble(manifest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        code, data = self.sizes(rel)
        self.assertLessEqual(code, CODE_BUDGET, f"code {code} B over the {CODE_BUDGET} B budget")
        self.assertLessEqual(data, DATA_BUDGET, f"data {data} B over the {DATA_BUDGET} B budget")

    def test_pool_macro_accepts_1_to_255_slots_only(self):
        # A pool of 0 slots would make reset and alloc loop 256 times over garbage.
        for count, ok in ((0, False), (1, True), (255, True), (256, False)):
            with tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                (work / "video").mkdir()
                shutil.copy(ROOT / "framework/src/video/ecs_render.inc", work / "video")
                (work / "t.s").write_text(
                    f'.module t\n.include "video/ecs_render.inc"\n.area _DATA\n'
                    f"FWK_ECS_RENDER_POOL pool, 4, {count}\n"
                )
                result = subprocess.run(
                    [str(ASSEMBLER), "-l", "-o", "t.s"], cwd=work, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode == 0, ok, f"count {count}: {result.stdout}{result.stderr}")

    def test_scene_macro_accepts_1_to_255_pools_only(self):
        for count, ok in ((0, False), (1, True), (255, True), (256, False)):
            with tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                (work / "video").mkdir()
                shutil.copy(ROOT / "framework/src/video/ecs_render.inc", work / "video")
                (work / "t.s").write_text(
                    '.module t\n.include "video/ecs_render.inc"\n.area _DATA\n'
                    f"FWK_ECS_RENDER_SCENE scene, 0, 0, 0, 0, 0, {count}\n"
                )
                result = subprocess.run(
                    [str(ASSEMBLER), "-l", "-o", "t.s"], cwd=work, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode == 0, ok, f"count {count}: {result.stdout}{result.stderr}")

    def test_transparency_off_is_not_larger(self):
        manifest = {"ecs": {"x_format": "u8", "y_format": "u8", "components": []}}
        _, on = self.assemble(manifest, True)
        _, off = self.assemble(manifest, False)
        self.assertLessEqual(self.sizes(off)[0], self.sizes(on)[0])

    def test_build_stops_with_non_u8_coordinates(self):
        manifest = {"ecs": {"x_format": "u16", "y_format": "u8", "components": []}}
        result, _ = self.assemble(manifest)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
