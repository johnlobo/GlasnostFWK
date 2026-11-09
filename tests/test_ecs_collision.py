import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.gen_ecs_profile import DEFAULT_PORTFOLIO, generate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ecs_collision_model as model  # noqa: E402

E, S, X = model.ENTER, model.STAY, model.EXIT
CPCT = Path(os.environ.get("CPCT_NEXT_PATH", "/config/workspace/cpctelera_next/cpctelera"))
ASSEMBLER = CPCT / "tools/sdcc-4.5.0/bin/sdasz80"

# ABI 9 budget: the whole system must stay tiny (CPC games fit in 64 KB).
CODE_BUDGET = 300
DATA_BUDGET = 8


class CollisionModelTests(unittest.TestCase):
    """Expectations derived by hand from ABI 9, not from the model."""

    @classmethod
    def setUpClass(cls):
        cls.records = model.simulate()

    def calls(self, step):
        return self.records[step].callbacks

    def test_nothing_touching(self):
        self.assertEqual(self.calls(0), [])
        self.assertEqual(self.records[0].contact, 0)

    def test_enter_then_stay(self):
        self.assertEqual(self.calls(1), [(E, 1, 0)])
        self.assertEqual(self.records[1].contact, 1)
        self.assertEqual(self.calls(2), [(S, 1, 0)])

    def test_state_is_per_subject_so_a_second_target_is_stay(self):
        self.assertEqual(self.calls(3), [(S, 1, 0), (S, 2, 0)])

    def test_exit_once_without_target(self):
        self.assertEqual(self.calls(4), [(X, None, 0)])
        self.assertEqual(self.records[4].contact, 0)
        self.assertEqual(self.calls(5), [])

    def test_mask_filters_targets_and_edges_do_not_touch(self):
        self.assertEqual(self.calls(6), [])   # T3 has no COLLISION component
        self.assertEqual(self.calls(7), [])   # edge contact: strict overlap

    def test_destroyed_target_ends_the_contact(self):
        self.assertEqual(self.calls(8), [(E, 3, 0)])
        self.assertEqual(self.calls(9), [(X, None, 0)])

    def test_abort_and_errors_leave_contact_untouched(self):
        abort = self.records[10]
        self.assertEqual((abort.result, abort.carry, abort.contact), (0x77, 1, 0))
        self.assertEqual(abort.callbacks, [(E, 1, 0)])          # stopped at the first hit
        self.assertEqual(self.calls(11), [(E, 1, 0), (E, 2, 0)])  # still ENTER
        busy, null = self.records[12], self.records[13]
        self.assertEqual((busy.result, busy.carry, busy.contact, busy.callbacks), (6, 1, 1, []))
        self.assertEqual((null.result, null.carry, null.contact, null.callbacks), (9, 1, 1, []))

    def test_failing_exit_callback_still_clears_contact(self):
        self.assertEqual(self.calls(14), [(X, None, 0)])
        last = self.records[16]
        self.assertEqual((last.result, last.carry, last.contact), (9, 1, 0))

    def test_two_channels_do_not_disturb_each_other(self):
        self.assertEqual(self.calls(17), [(E, 1, 0)])             # channel 1: only T0
        self.assertEqual(self.records[17].contact, 1)
        self.assertEqual(self.calls(18), [(E, 1, 0), (E, 4, 0)])  # channel 2: its own ENTER
        self.assertEqual(self.records[18].contact, 3)
        self.assertEqual(self.calls(19), [(S, 1, 0)])             # channel 1 not reset by 2
        self.assertEqual(self.calls(20), [(S, 1, 0), (S, 4, 0)])
        self.assertEqual(self.calls(21), [(X, None, 0)])
        self.assertEqual(self.records[21].contact, 2)             # channel 2 survives
        self.assertEqual(self.calls(22), [(X, None, 0)])
        self.assertEqual(self.records[22].contact, 0)

    def test_a_new_target_in_an_active_channel_is_stay_not_enter(self):
        # Per-target effects (collecting a coin) must therefore run on every
        # non-EXIT call: after a coin is destroyed on ENTER, the next coin
        # that starts touching arrives as STAY.
        self.assertEqual(self.calls(23), [(E, 1, 0)])
        self.assertEqual(self.calls(24), [(S, 2, 0)])
        self.assertEqual(self.calls(25), [(X, None, 0)])

    def test_expected_log_layout(self):
        pointers = [0x1000 + 0x40 * i for i in range(5)]
        log = model.expected_log(pointers, 0x2000)
        self.assertEqual(log[:5], bytes((0, 0, 0, 0, 0)))          # step 0
        self.assertEqual(log[5:10], bytes((1, 0, 0, 1, 1)))        # step 1 header
        self.assertEqual(log[10:17], bytes((1, 0x40, 0x10, 0x00, 0x10, 0x00, 0x20)))
        self.assertEqual(len(model.describe_log(log, pointers)), len(model.SCENARIO))

    def test_committed_scenario_include_is_current(self):
        committed = (ROOT / "examples/ecscollision/scenario.inc").read_text()
        self.assertEqual(committed, model.render_include())


@unittest.skipUnless(ASSEMBLER.is_file(), "CPCtelera Next assembler is not installed")
class CollisionTraversalTests(unittest.TestCase):
    def test_collide_walks_targets_with_run_any(self):
        # A target must never vanish because of its cadence: a contact would close
        # and reopen every other iteration and emit ENTER again each time.
        source = (ROOT / "framework/src/core/ecs_collision.s").read_text()
        code = "\n".join(line.split(";", 1)[0] for line in source.splitlines())
        self.assertIn("call fwk_ecs_system_run_any", code)
        self.assertNotRegex(code, r"(?m)\b(?:call|jp)\s+fwk_ecs_system_run\b(?!_)")


@unittest.skipUnless(ASSEMBLER.is_file(), "CPCtelera Next assembler is not installed")
class CollisionBudgetTests(unittest.TestCase):
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
            for name in ("ecs_manager.inc", "ecs_collision.inc", "ecs_collision.s"):
                shutil.copy(ROOT / "framework/src/core" / name, work / "core" / name)
            result = subprocess.run(
                [str(ASSEMBLER), "-l", "-o", "core/ecs_collision.s"],
                cwd=work, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return (work / "core/ecs_collision.rel").read_text()

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
        code, data = self.sizes(self.assemble(["collision"]))
        self.assertLessEqual(code, CODE_BUDGET, f"code {code} B over the {CODE_BUDGET} B budget")
        self.assertLessEqual(data, DATA_BUDGET, f"data {data} B over the {DATA_BUDGET} B budget")

    def test_assembles_when_collision_is_not_the_first_component(self):
        self.assemble([f"c{i}" for i in range(8)] + ["collision"], custom=8)

    def test_build_stops_with_non_u8_coordinates(self):
        # The routine reads single-byte X/Y: u16 or fixed 8.8 must not assemble.
        portfolio = json.loads(DEFAULT_PORTFOLIO.read_text(encoding="utf-8"))
        profile = json.loads((ROOT / "framework/profiles/standard-160x200.json").read_text())
        manifest = {"ecs": {"x_format": "u16", "y_format": "u8", "components": ["collision"]}}
        include = generate(manifest, portfolio, profile).include
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "core").mkdir()
            (work / "ecs_profile.inc").write_text(include, encoding="ascii")
            for name in ("ecs_manager.inc", "ecs_collision.inc", "ecs_collision.s"):
                shutil.copy(ROOT / "framework/src/core" / name, work / "core" / name)
            result = subprocess.run(
                [str(ASSEMBLER), "-l", "-o", "core/ecs_collision.s"],
                cwd=work, capture_output=True, text=True,
            )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
