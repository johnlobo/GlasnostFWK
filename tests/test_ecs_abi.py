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

    def test_cadence_is_normative(self):
        for contract in (
            "`ECS_E_CADENCE` | siguiente | 1",
            "(fase << 4) | (cada - 1)",
            "((fwk_ecs_tick XOR fase) AND (cada - 1)) = 0",
            "NO es el contador\n  de interrupciones de 50 Hz",
            "`FWK_ECS_ERR_TEMPLATE`",
            "`fwk_ecs_system_run_any`",
        ):
            self.assertIn(contract, self.source)

    def test_systems_never_hard_code_entity_offsets(self):
        # The ABI forbids numeric field offsets in systems (section 3): they break
        # silently when the generated layout changes. ecs_render.s indexes its own
        # 8-byte work entries with numbers, which are not entity fields.
        offenders = []
        for path in sorted((ROOT / "src" / "core").glob("ecs_*.s")):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                code = line.split(";", 1)[0]
                if re.search(r"(?<![\w+])\d+\(i[xy]\)", code):
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
        self.assertEqual(offenders, [])

    def test_render_has_no_layout_dependent_immediates(self):
        # ecs_render.s once assumed the previous rectangle sat 6 bytes after the
        # current one; adding a header field made every box wrong and the whole
        # scene redrew each frame. Its only numeric 16-bit immediates may be 8,
        # the size of a work-array entry; entity distances come from the profile.
        code = "\n".join(
            line.split(";", 1)[0] for line in (ROOT / "src/video/ecs_render.s").read_text().splitlines()
        )
        numbers = {int(n, 0) for n in re.findall(r"ld (?:bc|de|hl), #(0x[0-9A-Fa-f]+|\d+)\b", code)}
        self.assertLessEqual(numbers, {0, 8})

    def test_system_adapters_take_component_masks_from_the_profile(self):
        # `ld bc, #0x0010` in ecs_platform.s kept working only until a component
        # bit moved. The adapters use ECS_C_* symbols.
        offenders = []
        for path in sorted((ROOT / "src" / "core").glob("ecs_*.s")):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(r"ld bc, #(0x[0-9A-Fa-f]+|\d+)\b", line.split(";", 1)[0]):
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
        self.assertEqual(offenders, [])

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
