import json
import unittest
from pathlib import Path


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
        self.assertEqual(manifest["ecs"]["components"], ["test"])
        self.assertIn("call fwk_ecs_system_run", main)
        self.assertIn("call fwk_ecs_manager_collect", main)
        self.assertIn("ld a, #0x5A", main)

    def test_manager_consumes_the_selected_profile(self):
        source = (ROOT / "src/core/ecs_manager.s").read_text()
        profile = (ROOT / "examples/ecsmanager/generated/ecs_profile.inc").read_text()
        self.assertIn('.include "ecs_profile.inc"', source)
        self.assertIn("ECS_COMPONENT_VALID_MASK", source)
        self.assertIn("ECS_ENTITY_SIZE", source)
        self.assertIn("ECS_C_RENDER_BIT", profile)

    def test_ci_verifies_the_new_bin_and_cdt(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        artifact_section = workflow.split("Verify distributable artifacts", 1)[1]
        self.assertGreaterEqual(artifact_section.count("ecsmanager"), 2)


if __name__ == "__main__":
    unittest.main()
