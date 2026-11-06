import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EcsAbiSpecificationTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "docs" / "ecs-abi-2.0.md"
        self.source = self.path.read_text(encoding="utf-8")

    def test_universal_header_and_size_limit_are_normative(self):
        required = (
            "`ECS_E_COMPONENTS` | 0 | 2",
            "`ECS_E_STATUS` | 2 | 1",
            "`ECS_E_TYPE` | 3 | 1",
            "`ECS_E_X` | 4 | `ECS_X_SIZE`",
            "`ECS_ENTITY_SIZE` DEBE estar entre 1 y 128 bytes",
            "X y anchura usan bytes de pantalla",
        )
        for contract in required:
            self.assertIn(contract, self.source)

    def test_lifecycle_values_are_complete_and_unique(self):
        values = {
            name: int(value, 10)
            for name, value in re.findall(
                r"`(ECS_STATUS_[A-Z_]+)` \| (\d+) \|", self.source
            )
        }
        self.assertEqual(
            values,
            {
                "ECS_STATUS_FREE": 0,
                "ECS_STATUS_ACTIVE": 1,
                "ECS_STATUS_PENDING_DESTROY": 2,
                "ECS_STATUS_DISABLED": 3,
            },
        )

    def test_manager_api_and_error_codes_are_fixed(self):
        routines = {
            "fwk_ecs_manager_init",
            "fwk_ecs_entity_create",
            "fwk_ecs_entity_mark_destroy",
            "fwk_ecs_entity_disable",
            "fwk_ecs_entity_enable",
            "fwk_ecs_entity_set_mask",
            "fwk_ecs_system_run",
            "fwk_ecs_manager_collect",
        }
        for routine in routines:
            self.assertIn(f"`{routine}`", self.source)

        errors = {
            name: int(value, 16)
            for name, value in re.findall(
                r"`(FWK_ECS_(?:OK|ERR_[A-Z_]+))` \| `0x([0-9A-F]{2})`",
                self.source,
            )
        }
        self.assertEqual(len(errors), 12)
        self.assertEqual(set(errors.values()), set(range(12)))

    def test_render_and_collision_contracts_are_explicit(self):
        required = (
            "`ECS_C_RENDER`",
            "`ECS_RENDER_HAS_BACKGROUND`",
            "`ECS_E_RENDER_PREVIOUS_SORT_Y`",
            "`fwk_ecs_collide`",
            "`ECS_E_COLLISION_CONTACT`",
            "`ECS_COLLISION_ENTER=1`",
            "`EXIT=3`",
            "necesita su propio canal",
            "300 bytes de código y ninguna\ntabla ni buffer",
        )
        for contract in required:
            self.assertIn(contract, self.source)

    def test_phase_gate_remains_explicit_in_all_state_documents(self):
        master = (ROOT / "docs" / "ecs-2.0-master-plan.md").read_text(
            encoding="utf-8"
        )
        status = (ROOT / "PROJECT_STATUS.md").read_text(encoding="utf-8")
        manual = (ROOT / "docs" / "manual.html").read_text(encoding="utf-8")
        self.assertIn("docs/ecs-abi-2.0.md", master)
        self.assertIn("docs/ecs-abi-2.0.md", status)
        self.assertIn('href="ecs-abi-2.0.md"', manual)
        self.assertIn("Puerta G1 aprobada", self.source)
        self.assertIn("Fase 1: completada, G1 aprobada", status)
        self.assertIn("Estado: normativa aprobada", self.source)


if __name__ == "__main__":
    unittest.main()
