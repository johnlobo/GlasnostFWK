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

import ecs_animation_model as model  # noqa: E402

CPCT = Path(os.environ.get("CPCT_NEXT_PATH", "/config/workspace/cpctelera_next/cpctelera"))
ASSEMBLER = CPCT / "tools/sdcc-4.5.0/bin/sdasz80"

# ABI 10 budget: animation must stay tiny (CPC games fit in 64 KB).
CODE_BUDGET = 150
DATA_BUDGET = 0

NONE = model.NO_SPRITE


class AnimationModelTests(unittest.TestCase):
    """Expectations derived by hand from ABI 10, not from the model.

    Entry: (frame, timer, sprite id, flags); sprite ids 0..2 are the frames of
    descriptor A (count 3, duration 2), 3..4 those of B (count 2, duration 1).
    """

    @classmethod
    def setUpClass(cls):
        cls.records = model.simulate()

    def at(self, tick, entity):
        return self.records[tick].entities[entity]

    def test_timer_counts_down_and_the_frame_advances_at_zero(self):
        self.assertEqual(self.at(0, 0), (0, 1, 0, 0))            # A: 2 -> 1, no advance
        self.assertEqual(self.at(1, 0), (1, 2, 1, model.DIRTY))  # 1 -> 0: next frame, reload 2

    def test_duration_one_advances_every_call_and_wraps(self):
        self.assertEqual(self.at(0, 1), (1, 1, 4, model.DIRTY))  # B: f1
        self.assertEqual(self.at(1, 1), (0, 1, 3, model.DIRTY))  # wraps to f0

    def test_entity_without_descriptor_is_untouched(self):
        for tick in range(10):                      # until t10 gives it descriptor D
            self.assertEqual(self.at(tick, 2), (0, 0, NONE, 0))

    def test_single_frame_animation_still_marks_dirty_every_duration(self):
        # count 1, duration 3: the sprite is re-set and DIRTY raised every third
        # call even though nothing changes (documented redraw churn).
        self.assertEqual(self.at(10, 2), (0, 2, 0, model.DIRTY))   # set + first countdown
        self.assertEqual(self.at(11, 2), (0, 1, 0, 0))
        self.assertEqual(self.at(12, 2), (0, 3, 0, model.DIRTY))   # "advance" to frame 0 again
        self.assertEqual(self.at(13, 2), (0, 2, 0, 0))

    def test_a_stopped_entity_can_be_reselected(self):
        self.assertEqual(self.at(11, 1), (0, 0, 3, 0))            # still stopped
        self.assertEqual(self.at(12, 1), (1, 1, 4, model.DIRTY))  # restarted and advanced

    def test_a_different_descriptor_restarts(self):
        # t3: E0 -> B restarts at frame 0 with a full timer, then the call
        # advances it (duration 1): frame 1.
        self.assertEqual(self.at(3, 0), (1, 1, 4, model.DIRTY))

    def test_selecting_the_active_descriptor_changes_nothing(self):
        # t4 leaves E0 on frame 0; t5 re-selects B, so the system call still
        # advances from there instead of restarting.
        self.assertEqual(self.at(4, 0), (0, 1, 3, model.DIRTY))
        self.assertEqual(self.at(5, 0), (1, 1, 4, model.DIRTY))

    def test_reselecting_a_descriptor_mid_cycle_does_not_restart(self):
        # t8 ends on A frame 1 with a full timer; t9 selects A again, so the
        # call only counts the timer down (a restart would show frame 0 DIRTY).
        self.assertEqual(self.at(8, 0), (1, 2, 1, model.DIRTY))
        self.assertEqual(self.at(9, 0), (1, 1, 1, 0))

    def test_null_descriptor_stops_and_keeps_the_sprite(self):
        self.assertEqual(self.at(5, 1), (0, 1, 3, model.DIRTY))
        for tick in range(6, 12):
            self.assertEqual(self.at(tick, 1), (0, 0, 3, 0))     # frame/timer 0, sprite kept

    def test_back_to_a_then_the_full_loop(self):
        self.assertEqual(self.at(7, 0), (0, 1, 0, model.DIRTY))  # restart, timer 2 -> 1
        self.assertEqual(self.at(8, 0), (1, 2, 1, model.DIRTY))
        self.assertEqual(self.at(9, 0), (1, 1, 1, 0))
        self.assertEqual(self.at(10, 0), (2, 2, 2, model.DIRTY))
        self.assertEqual(self.at(12, 0), (0, 2, 0, model.DIRTY))  # wraps after the last frame

    def test_counts_above_128_index_frames_in_16_bits(self):
        # E3: descriptor C has 130 frames, frame i shows sprite i % 5, and the
        # entity starts at frame 127. An 8-bit index (frame * 2) wraps at 128.
        self.assertEqual(self.at(0, 3), (128, 1, 3, model.DIRTY))   # 128 % 5 = 3, not 0
        self.assertEqual(self.at(1, 3), (129, 1, 4, model.DIRTY))   # 129 % 5 = 4, not 1
        self.assertEqual(self.at(2, 3), (0, 1, 0, model.DIRTY))     # wraps after the last

    def test_an_entity_copied_from_a_started_template_still_starts(self):
        # E4 holds descriptor B with TIMER 0 (as a template would): anim_set(B)
        # must restart it instead of treating B as "already active".
        self.assertEqual(self.at(0, 4), (1, 1, 4, model.DIRTY))
        self.assertEqual(self.at(1, 4), (0, 1, 3, model.DIRTY))

    def test_expected_log_layout(self):
        sprites = [0x1000 + 0x10 * i for i in range(5)]
        log = model.expected_log(sprites)
        self.assertEqual(len(log), (1 + 5 * model.ENTITY_COUNT) * len(model.COMMANDS))
        self.assertEqual(log[:6], bytes((0, 0, 1, 0x00, 0x10, 0)))  # tick 0, E0: f0 t1 s0
        self.assertEqual(len(model.describe_log(log, sprites)), len(model.COMMANDS))

    def test_committed_scenario_include_is_current(self):
        committed = (ROOT / "framework/validations/ecsanimation/scenario.inc").read_text()
        self.assertEqual(committed, model.render_include())


@unittest.skipUnless(ASSEMBLER.is_file(), "CPCtelera Next assembler is not installed")
class AnimationBudgetTests(unittest.TestCase):
    """The size budget is part of the contract: a regression fails the build."""

    def assemble(self, components: list[str], custom: int = 0) -> str:
        portfolio = json.loads(DEFAULT_PORTFOLIO.read_text(encoding="utf-8"))
        profile = json.loads((ROOT / "framework/profiles/standard-160x200.json").read_text())
        manifest = {
            "ecs": {
                "x_format": "u8",
                "y_format": "u8",
                "components": components,
                "custom_components": [
                    {"name": f"c{i}", "dependencies": [], "fields": []} for i in range(custom)
                ],
            }
        }
        include = generate(manifest, portfolio, profile).include
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "core").mkdir()
            (work / "ecs_profile.inc").write_text(include, encoding="ascii")
            for name in ("ecs_manager.inc", "ecs_animation.inc", "ecs_animation.s"):
                shutil.copy(ROOT / "framework/src/core" / name, work / "core" / name)
            result = subprocess.run(
                [str(ASSEMBLER), "-l", "-o", "core/ecs_animation.s"],
                cwd=work, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return (work / "core/ecs_animation.rel").read_text()

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
        code, data = self.sizes(self.assemble(["animation"]))
        self.assertLessEqual(code, CODE_BUDGET, f"code {code} B over the {CODE_BUDGET} B budget")
        self.assertLessEqual(data, DATA_BUDGET, f"data {data} B over the {DATA_BUDGET} B budget")

    def test_assembles_when_animation_is_not_the_first_component(self):
        self.assemble([f"c{i}" for i in range(8)] + ["animation"], custom=8)


if __name__ == "__main__":
    unittest.main()
