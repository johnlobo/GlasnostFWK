import json
import re
import tempfile
import unittest
from pathlib import Path

from tools.build_examples import _invalidate_objects_if_profile_changed


ROOT = Path(__file__).resolve().parents[1]


class ECSManagerTests(unittest.TestCase):
    def test_public_api_and_descriptor_match_approved_abi(self):
        include = (ROOT / "src/core/ecs_manager.inc").read_text()
        source = (ROOT / "src/core/ecs_manager.s").read_text()
        expected_offsets = {
            "FWK_ECS_MANAGER_STORAGE": 0,
            "FWK_ECS_MANAGER_CAPACITY": 2,
            "FWK_ECS_MANAGER_STRIDE": 3,
            "FWK_ECS_MANAGER_ACTIVE_COUNT": 4,
            "FWK_ECS_MANAGER_LIVE_COUNT": 5,
            "FWK_ECS_MANAGER_LOCK": 6,
            "FWK_ECS_MANAGER_FLAGS": 7,
            "FWK_ECS_MANAGER_SIZE": 8,
        }
        for symbol, value in expected_offsets.items():
            self.assertRegex(include, rf"(?m)^{symbol}\s*=\s*{value}$")
        for routine in (
            "fwk_ecs_manager_init",
            "fwk_ecs_entity_create",
            "fwk_ecs_entity_mark_destroy",
            "fwk_ecs_entity_disable",
            "fwk_ecs_entity_enable",
            "fwk_ecs_entity_set_mask",
            "fwk_ecs_system_run",
            "fwk_ecs_manager_collect",
        ):
            self.assertIn(f"{routine}::", source)

    def test_manager_is_exercised_by_an_executable_example(self):
        manifest = json.loads(
            (ROOT / "examples/ecsmanager/example.json").read_text()
        )
        main = (ROOT / "examples/ecsmanager/main.s").read_text()
        self.assertIn("core/ecs_manager.s", manifest["modules"])
        self.assertEqual(manifest["ecs"]["components"], ["behavior", "test"])
        self.assertIn("core/ecs_behavior.s", manifest["modules"])
        self.assertIn("core/ecs_motion.s", manifest["modules"])
        self.assertIn("call fwk_ecs_system_run", main)
        self.assertIn("call fwk_ecs_system_behavior", main)
        self.assertIn("call fwk_ecs_system_motion_u8", main)
        self.assertIn("call fwk_ecs_manager_collect", main)
        self.assertIn("ld a, #0x5A", main)

    def test_manager_consumes_the_selected_profile(self):
        source = (ROOT / "src/core/ecs_manager.s").read_text()
        profile = (ROOT / "examples/ecsmanager/generated/ecs_profile.inc").read_text()
        self.assertIn('.include "ecs_profile.inc"', source)
        self.assertIn("ECS_COMPONENT_VALID_MASK", source)
        self.assertIn("ECS_ENTITY_SIZE", source)
        self.assertIn("ECS_C_RENDER_BIT", profile)

    def test_behavior_and_motion_system_contract_is_exported(self):
        manager_include = (ROOT / "src/core/ecs_manager.inc").read_text()
        behavior = (ROOT / "src/core/ecs_behavior.s").read_text()
        motion = (ROOT / "src/core/ecs_motion.s").read_text()
        self.assertIn("fwk_ecs_system_behavior", manager_include)
        self.assertIn("fwk_ecs_system_motion_u8", manager_include)
        self.assertIn("fwk_ecs_system_run", behavior)
        self.assertIn("fwk_ecs_system_run", motion)
        self.assertIn("ECS_E_BEHAVIOR_PROGRAM", behavior)
        self.assertIn("ECS_E_MOTION_VELOCITY_X", motion)

    def test_motion_system_uses_carry_and_leaves_platform_entities_alone(self):
        motion = (ROOT / "src/core/ecs_motion.s").read_text()
        # Regression: `jp m` on the u8 sum zeroed every coordinate above 127.
        self.assertNotIn("jp m", motion)
        self.assertIn("_fwk_ecs_motion_axis", motion)
        # Regression: PLATFORM entities were integrated twice and tunnelled.
        self.assertIn(".ifdef ECS_C_PLATFORM", motion)
        self.assertIn("and #ECS_C_PLATFORM", motion)

    def test_platformer_ecs_player_spawns_airborne(self):
        # physics_platform applies gravity only to airborne bodies: a grounded
        # spawn hovers at its spawn height forever.
        main = (ROOT / "examples/platformer_ecs/main.s").read_text()
        self.assertIn("ld ECS_E_MOTION_FLAGS(iy), #FWK_PLATFORM_AIRBORNE", main)

    def test_platformer_ecs_smoke_covers_landing_walk_and_jump(self):
        smoke = (ROOT / "tests/emulator_smoke.py").read_text()
        section = smoke.split('if name == "platformer_ecs":', 1)[1].split(
            'if name == "audio":', 1
        )[0]
        for label in (
            "ECS platformer settles",
            "ECS platformer first jump",
            "ECS platformer first landing",
            "ECS platformer right approach",
            "ECS platformer platform approach",
            "ECS platformer upper-right coin",
            "ECS platformer win state",
            "ECS platformer door touch",
        ):
            # The label must be the argument of a waiting call, not a stray
            # string in dead code.
            self.assertRegex(
                section,
                rf"(?s)(wait_for|hold_keys_until)\((?:(?!\n            \w).)*?[\"']{label}[\"']",
            )
        self.assertIn("raise RuntimeError", section)

    def test_input_jump_leaves_airborne_to_the_platform_step(self):
        # Regression: setting AIRBORNE on jump made gravity act before the first
        # move, so the jump rose 28 px instead of the original 36.
        code = "\n".join(
            line for line in (ROOT / "src/core/ecs_input.s").read_text().splitlines()
            if not line.lstrip().startswith(";;")
        )
        self.assertNotIn("FWK_PLATFORM_AIRBORNE_BIT", code)

    def test_platformer_ecs_enemy_turns_match_the_original(self):
        # Original: H and V alternate frames, V2 runs every frame, and enemies
        # stop hurting once the game is won.
        main = (ROOT / "examples/platformer_ecs/main.s").read_text()
        frame = main.split("platformer_ecs_frame:", 1)[1]
        self.assertIn("ld (_pfe_phase), a", frame)
        self.assertEqual(frame.count("call _pfe_enemy_turn"), 1)
        self.assertIn("ld ix, #platformer_ecs_v", frame.split("call _pfe_enemy_turn")[0])
        self.assertIn("ld ix, #platformer_ecs_h", frame.split("call _pfe_enemy_turn")[0])
        self.assertIn("ld ix, #platformer_ecs_manager\n    call fwk_ecs_system_behavior", frame)
        collisions = main.split("_pfe_collisions:", 1)[1].split("_pfe_apply_events:", 1)[0]
        self.assertIn("ld a, (platformer_ecs_won)", collisions)

    def test_platformer_ecs_hud_and_flash_match_the_original(self):
        original = (ROOT / "examples/platformer/main.s").read_text()
        constants = (ROOT / "examples/platformer/game.inc").read_text()
        main = (ROOT / "examples/platformer_ecs/main.s").read_text()

        def number(text, name):
            return int(re.search(rf"^{name}\s*=\s*(\w+)", text, re.M).group(1), 0)

        # Same texts, in the same places.
        strings = {
            "COINS: 0/4": "platformer_score_str",
            "ALL COINS": "platformer_all_coins_str",
            "COLLECT ALL COINS": "platformer_hint_str",
            "GO TO THE DOOR": "platformer_win_str",
            "LIFE: 10": "platformer_life_str",
        }
        for text, original_label in strings.items():
            self.assertIn(f'{original_label}:: .ascii "{text}"', original)
            self.assertIn(f'.asciz "{text}"', main)
        self.assertEqual(number(main, "PFE_HUD_Y"), number(constants, "PF_HUD_Y"))
        # Field columns: first tile column * 4 bytes = the original text x.
        for field, label in ((0x00, "COINS"), (0x06, "HINT"), (0x10, "LIVES")):
            self.assertEqual(field * 4, number(constants, f"PF_HUD_{label}_X"))
            self.assertRegex(main, rf"ld bc, #0x{field:02X}[0-9A-F]{{2}}\n\s+j[pr] _pfe_hud_field")
        # Life flash: pen 16, red 0x1C then black 0x14, three times, 0x1000 loops.
        self.assertEqual(number(main, "PFE_BORDER_PEN"), 16)
        self.assertEqual(number(main, "PFE_BORDER_RED"), 0x1C)
        self.assertEqual(number(main, "PFE_BORDER_BLACK"), 0x14)
        self.assertEqual(number(main, "PFE_FLASH_COUNT"), 3)
        loop = main.split("_pfe_hud_update:", 1)[1].split("_pfe_border:", 1)[0]
        self.assertIn("ld b, #PFE_FLASH_COUNT\n_pfe_flash:", loop)
        self.assertIn("djnz _pfe_flash", loop)
        # No life below zero (the original returns without a flash at 0 lives).
        enemy_cb = main.split("_pfe_enemy_cb:", 1)[1].split("_pfe_collisions:", 1)[0]
        self.assertIn("ld a, (platformer_ecs_lives)\n    or a\n    jr z, _pfe_cb_ok", enemy_cb)
        # Taking the last coin wins before any enemy is checked.
        collisions = main.split("_pfe_collisions:", 1)[1].split("_pfe_apply_events:", 1)[0]
        self.assertIn("ld hl, #_pfe_all_coins\n    or (hl)\n    ret nz", collisions)
        self.assertEqual(number(main, "PFE_FLASH_DELAY"), 0x1000)
        flash = original.split("_pf_lose_life_flash:", 1)[1].split("ret", 1)[0]
        self.assertIn("ld l, #16", flash)
        self.assertIn("ld h, #0x1C", flash)
        self.assertIn("ld h, #0x14", flash)
        self.assertEqual(flash.count("ld de, #0x1000"), 2)
        self.assertIn("ld b, #3", original.split("_pf_lose_life_flash:", 1)[0].rsplit("_pf_lose_life:", 1)[1])

    def test_ci_verifies_the_new_bin_and_cdt(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        artifact_section = workflow.split("Verify distributable artifacts", 1)[1]
        self.assertGreaterEqual(artifact_section.count("ecsmanager"), 2)

    def test_profile_change_invalidates_staged_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "obj" / "core").mkdir(parents=True)
            (target / "obj" / "core" / "ecs_manager.rel").write_bytes(b"old")
            _invalidate_objects_if_profile_changed(target, False)
            self.assertTrue((target / "obj").exists())
            _invalidate_objects_if_profile_changed(target, True)
            self.assertFalse((target / "obj").exists())


if __name__ == "__main__":
    unittest.main()
