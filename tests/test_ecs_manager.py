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

    def test_platformer_player_spawns_airborne(self):
        # physics_platform applies gravity only to airborne bodies: a grounded
        # spawn hovers at its spawn height forever.
        main = (ROOT / "examples/platformer/main.s").read_text()
        self.assertIn("ld ECS_E_MOTION_FLAGS(iy), #FWK_PLATFORM_AIRBORNE", main)

    def test_platformer_smoke_covers_landing_walk_and_jump(self):
        smoke = (ROOT / "tests/emulator_smoke.py").read_text()
        section = smoke.split('if name == "platformer":', 1)[1].split(
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

    def test_platformer_enemy_turns(self):
        # H and V alternate frames, V2 runs every frame, and enemies stop
        # hurting once the game is won.
        main = (ROOT / "examples/platformer/main.s").read_text()
        frame = main.split("platformer_frame:", 1)[1]
        self.assertIn("ld (_pfe_phase), a", frame)
        self.assertEqual(frame.count("call _pfe_enemy_turn"), 1)
        self.assertIn("ld ix, #platformer_v", frame.split("call _pfe_enemy_turn")[0])
        self.assertIn("ld ix, #platformer_h", frame.split("call _pfe_enemy_turn")[0])
        self.assertIn("ld ix, #platformer_manager\n    call fwk_ecs_system_behavior", frame)
        collisions = main.split("_pfe_collisions:", 1)[1].split("_pfe_apply_events:", 1)[0]
        self.assertIn("ld a, (platformer_won)", collisions)

    def test_platformer_hud_and_flash(self):
        main = (ROOT / "examples/platformer/main.s").read_text()

        def number(text, name):
            return int(re.search(rf"^{name}\s*=\s*(\w+)", text, re.M).group(1), 0)

        for text in ("COINS: 0/4", "ALL COINS", "COLLECT ALL COINS", "GO TO THE DOOR", "LIFE: 10"):
            self.assertIn(f'.asciz "{text}"', main)
        self.assertEqual(number(main, "PFE_HUD_Y"), 10)
        # Field first tile columns: coins, hint, lives.
        for field in (0x00, 0x06, 0x10):
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
        self.assertIn("ld a, (platformer_lives)\n    or a\n    jr z, _pfe_cb_ok", enemy_cb)
        # Taking the last coin wins before any enemy is checked.
        collisions = main.split("_pfe_collisions:", 1)[1].split("_pfe_apply_events:", 1)[0]
        self.assertIn("ld hl, #_pfe_all_coins\n    or (hl)\n    ret nz", collisions)
        self.assertEqual(number(main, "PFE_FLASH_DELAY"), 0x1000)

    def test_platformer_second_level_restarts_like_the_boot(self):
        main = (ROOT / "examples/platformer/main.s").read_text()
        assets = (ROOT / "examples/platformer/assets/generated/assets.inc").read_text()

        def number(text, name):
            return int(re.search(rf"^{name}\s*=\s*(\w+)", text, re.M).group(1), 0)

        # One view serves both maps, so they must have the same size.
        self.assertEqual(number(assets, "PLATFORMER_MAP2_WIDTH"), number(assets, "PLATFORMER_MAP_WIDTH"))
        self.assertEqual(number(assets, "PLATFORMER_MAP2_HEIGHT"), number(assets, "PLATFORMER_MAP_HEIGHT"))
        # Boot and the door run the same start routine.
        boot = main.split("_main::", 1)[1].split("platformer_frame:", 1)[0]
        self.assertIn("call _pfe_start_level", boot)
        events = main.split("_pfe_apply_events:", 1)[1].split("_pfe_enemy_turn:", 1)[0]
        self.assertIn("jp _pfe_start_level", events)
        self.assertIn("call fwk_zx7b_unpack", events)
        self.assertIn("ld (_pfe_map_desc), hl", events)
        # Lives are never written on the door path (a reset there would survive
        # the smoke whenever no enemy had hit the player earlier).
        self.assertNotIn("platformer_lives", events)
        # The start routine clears the level state but never the lives.
        start = main.split("_pfe_start_level:", 1)[1].split("_main::", 1)[0]
        for reset in ("platformer_score", "platformer_won", "_pfe_all_coins", "_pfe_door_hit", "_pfe_phase"):
            self.assertIn(f"ld ({reset}), a", start)
        self.assertNotIn("platformer_lives", start)
        # The state clears are plain zero stores: no load of another value between
        # `xor a` and the last clear (a stray `inc a` would start the phase at 1).
        clears = start.split("    xor a\n    ld (platformer_score), a", 1)[1].split("ld (_pfe_phase), a", 1)[0]
        for line in clears.strip().splitlines():
            self.assertRegex(line.strip(), r"^ld \(\w+\), a$")
        # The player's physics and the HUD follow the active map.
        self.assertIn("ld hl, (_pfe_map_desc)", start)
        self.assertIn("ld ix, (_pfe_map_desc)", main.split("_pfe_hud_restore:", 1)[1].split("_pfe_hud_score:", 1)[0])

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
