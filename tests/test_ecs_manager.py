import json
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
            "ECS platformer enemy contact",
        ):
            # The label must be the argument of a waiting call, not a stray
            # string in dead code.
            self.assertRegex(
                section,
                rf"(?s)(wait_for|hold_keys_until)\((?:(?!\n            \w).)*?[\"']{label}[\"']",
            )
        self.assertIn("raise RuntimeError", section)

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
