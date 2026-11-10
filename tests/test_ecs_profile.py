import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.build.gen_ecs_profile import generate, layout_changes


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = json.loads(
    (ROOT / "framework/manifests/ecs-components.json").read_text(encoding="utf-8")
)
STANDARD = json.loads(
    (ROOT / "framework/profiles/standard-160x200.json").read_text(encoding="utf-8")
)


def manifest(**ecs_changes):
    ecs = {
        "x_format": "u8",
        "y_format": "u8",
        "components": [],
        "custom_components": [],
        "fields": [],
    }
    ecs.update(ecs_changes)
    return {"profile": "standard-160x200.json", "ecs": ecs}


class ECSProfileTests(unittest.TestCase):
    def test_committed_example_is_reproducible(self):
        example_path = ROOT / "framework/validations/ecsmanager/example.json"
        example = json.loads(example_path.read_text(encoding="utf-8"))
        generated = generate(example, PORTFOLIO, STANDARD)
        committed = ROOT / "framework/validations/ecsmanager/generated/ecs_profile.inc"
        self.assertEqual(committed.read_text(encoding="ascii"), generated.include)
        self.assertEqual(
            [item["name"] for item in generated.preview["components"]],
            ["render", "motion", "behavior", "test"],
        )
        self.assertEqual(generated.preview["entity_size"], 31)
        self.assertIn("ECS_COMPONENT_VALID_MASK = 0x000F", generated.include)

    def test_dependencies_are_inserted_before_the_requester(self):
        data = manifest(
            components=["actor"],
            custom_components=[
                {"name": "actor", "dependencies": ["motion"], "fields": []},
            ],
        )
        generated = generate(data, PORTFOLIO, STANDARD)
        self.assertEqual(
            [item["name"] for item in generated.preview["components"]],
            ["render", "motion", "actor"],
        )
        self.assertEqual(generated.preview["inserted_dependencies"], ["motion"])
        self.assertIn("ECS_C_MOTION_BIT = 1", generated.include)
        self.assertIn("ECS_C_ACTOR_BIT = 2", generated.include)
        self.assertIn("ECS_E_MOTION_VELOCITY_X = 24", generated.include)
        self.assertIn("ECS_E_MOTION_VELOCITY_Y = 25", generated.include)

        explicitly_requested = copy.deepcopy(data)
        explicitly_requested["ecs"]["components"] = ["actor", "motion"]
        generated = generate(explicitly_requested, PORTFOLIO, STANDARD)
        self.assertEqual(generated.preview["inserted_dependencies"], [])

    def test_coordinate_formats_change_offsets_and_velocity_sizes(self):
        data = manifest(
            x_format="u16",
            y_format="fixed_8_8",
            components=["motion"],
            custom_components=[],
            fields=[{"name": "health", "type": "u8"}],
        )
        generated = generate(data, PORTFOLIO, STANDARD)
        self.assertIn("ECS_X_SIZE = 2", generated.include)
        self.assertIn("ECS_Y_SIZE = 2", generated.include)
        self.assertIn("ECS_E_Y = 6", generated.include)
        self.assertIn("ECS_E_WIDTH = 8", generated.include)
        fields = {item["symbol"]: item for item in generated.preview["fields"]}
        self.assertEqual(fields["ECS_E_MOTION_VELOCITY_X"]["type"], "i16")
        self.assertEqual(fields["ECS_E_MOTION_VELOCITY_Y"]["type"], "fixed_8_8")
        self.assertEqual(fields["ECS_E_HEALTH"]["offset"] + 1, generated.preview["entity_size"])

    def test_cadence_is_a_universal_header_field_after_height(self):
        generated = generate(manifest(components=["motion"]), PORTFOLIO, STANDARD)
        self.assertIn("ECS_E_HEIGHT = 7\nECS_E_CADENCE = 8\nECS_E_RENDER_SPRITE = 9\n", generated.include)
        with self.assertRaisesRegex(ValueError, "reserved"):
            data = manifest(components=["motion"])
            data["ecs"]["fields"] = [{"name": "cadence", "type": "u8"}]
            generate(data, PORTFOLIO, STANDARD)

    def test_rejects_unknown_duplicate_cyclic_and_excess_components(self):
        with self.assertRaisesRegex(ValueError, "unknown ECS component"):
            generate(manifest(components=["missing"]), PORTFOLIO, STANDARD)
        with self.assertRaisesRegex(ValueError, "contains duplicates"):
            generate(manifest(components=["render", "render"]), PORTFOLIO, STANDARD)
        cyclic = manifest(
            components=["a"],
            custom_components=[
                {"name": "a", "dependencies": ["b"], "fields": []},
                {"name": "b", "dependencies": ["a"], "fields": []},
            ],
        )
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            generate(cyclic, PORTFOLIO, STANDARD)
        cyclic["ecs"]["components"] = []
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            generate(cyclic, PORTFOLIO, STANDARD)
        definitions = [
            {"name": f"c{index}", "dependencies": [], "fields": []}
            for index in range(16)
        ]
        with self.assertRaisesRegex(ValueError, "16-component"):
            generate(
                manifest(
                    components=[item["name"] for item in definitions],
                    custom_components=definitions,
                ),
                PORTFOLIO,
                STANDARD,
            )

    def test_rejects_invalid_fields_size_and_video_range(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            generate(manifest(fields=[{"name": "status", "type": "u8"}]), PORTFOLIO, STANDARD)
        with self.assertRaisesRegex(ValueError, "unsupported type"):
            generate(manifest(fields=[{"name": "health", "type": "u24"}]), PORTFOLIO, STANDARD)
        with self.assertRaisesRegex(ValueError, "128-byte ABI limit"):
            generate(manifest(fields=[{"name": "payload", "type": "bytes[110]"}]), PORTFOLIO, STANDARD)
        ambiguous_symbols = manifest(
            components=["a_b", "a"],
            custom_components=[
                {"name": "a_b", "dependencies": [], "fields": [{"name": "c", "type": "u8"}]},
                {"name": "a", "dependencies": [], "fields": [{"name": "b_c", "type": "u8"}]},
            ],
        )
        with self.assertRaisesRegex(ValueError, "duplicate generated field symbol"):
            generate(ambiguous_symbols, PORTFOLIO, STANDARD)
        tall = copy.deepcopy(STANDARD)
        tall["height_lines"] = 288
        with self.assertRaisesRegex(ValueError, "cannot represent 288 scanlines"):
            generate(manifest(y_format="fixed_8_8"), PORTFOLIO, tall)

    def test_check_mode_detects_a_stale_versioned_include(self):
        example = ROOT / "framework/validations/ecsmanager/example.json"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ecs_profile.inc"
            output.write_text("stale\n", encoding="ascii")
            result = subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools/build/gen_ecs_profile.py"),
                    str(example),
                    "--output",
                    str(output),
                    "--check",
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stale ECS profile", result.stderr)

    def test_preview_reports_added_removed_and_changed_symbols(self):
        changes = layout_changes(
            "ECS_ENTITY_SIZE = 25\nECS_C_OLD = 0x0002\n",
            "ECS_ENTITY_SIZE = 27\nECS_C_NEW = 0x0002\n",
        )
        self.assertTrue(changes["layout_changed"])
        self.assertEqual(changes["added"], {"ECS_C_NEW": 2})
        self.assertEqual(changes["removed"], {"ECS_C_OLD": 2})
        self.assertEqual(
            changes["changed"]["ECS_ENTITY_SIZE"], {"from": 25, "to": 27}
        )

    def test_cli_preview_is_read_only(self):
        example = ROOT / "framework/validations/ecsmanager/example.json"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ecs_profile.inc"
            output.write_text("previous\n", encoding="ascii")
            result = subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools/build/gen_ecs_profile.py"),
                    str(example),
                    "--output",
                    str(output),
                    "--preview",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            preview = json.loads(result.stdout)
            self.assertTrue(preview["changes"]["layout_changed"])
            self.assertEqual(output.read_text(encoding="ascii"), "previous\n")


if __name__ == "__main__":
    unittest.main()
