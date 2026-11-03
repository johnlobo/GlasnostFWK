import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BehaviorTests(unittest.TestCase):
    def test_wait_macro_terminates_its_condition_table(self):
        include = (ROOT / "src/extensions/behavior.inc").read_text()
        wait_macro = include.split(".macro FWK_BEHAVIOR_WAIT", 1)[1].split(
            ".endm", 1
        )[0]
        self.assertIn("FWK_BEHAVIOR_CONDITION timeout, _next", wait_macro)
        self.assertIn("FWK_BEHAVIOR_CONDITIONS_END", wait_macro)

    def test_platformer_enemies_use_shared_behavior_motion_adapter(self):
        main = (ROOT / "examples/platformer/main.s").read_text()
        assets = (ROOT / "examples/platformer/assets.s").read_text()
        adapter = main.split("_pf_update_behavior_enemy:", 1)[1].split(
            ";; Routine: _pf_reset_enemies", 1
        )[0]

        for name in ("h", "v", "v2"):
            self.assertIn(f"platformer_enemy_{name}_behavior::", main)
        self.assertIn("call fwk_behavior_run", adapter)
        self.assertIn("call fwk_motion_u8_step", adapter)
        self.assertIn("_pf_sync_behavior_enemy:", adapter)
        self.assertIn("platformer_enemy_h_program::", assets)
        self.assertIn("platformer_enemy_v_program::", assets)
        self.assertNotIn("platformer_enemy_v2_program::", assets)
        self.assertNotIn("_platformer_enemy_h_dx", main)
        self.assertNotIn("_platformer_enemy_v_dy", main)
        self.assertNotIn("_pf_enemy_h_left:", main)
        self.assertNotIn("_pf_enemy_v_up:", main)

    def test_platformer_behavior_preserves_patrol_spans(self):
        constants = (ROOT / "examples/platformer/game.inc").read_text()
        self.assertIn("PF_ENEMY_H_INITIAL_TICKS = 19", constants)
        self.assertIn("PF_ENEMY_H_LEG_TICKS     = 23", constants)
        self.assertIn("PF_ENEMY_V_MIN_Y      = 56", constants)
        self.assertIn("PF_ENEMY_V_MAX_Y      = 152", constants)
        self.assertIn("PF_ENEMY_V_LEG_TICKS = 49", constants)
        self.assertEqual(36 + (19 - 1), 54)
        self.assertEqual(32 + (23 - 1), 54)
        self.assertEqual(56 + (49 - 1) * 2, 152)


if __name__ == "__main__":
    unittest.main()
