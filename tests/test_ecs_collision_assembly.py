import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.gen_ecs_profile import DEFAULT_PORTFOLIO, generate

ROOT = Path(__file__).resolve().parents[1]
CPCT = Path(os.environ.get("CPCT_NEXT_PATH", "/config/workspace/cpctelera_next/cpctelera"))
ASSEMBLER = CPCT / "tools/sdcc-4.5.0/bin/sdasz80"


def _manifest(components: list[str], custom: int = 0) -> dict:
    return {
        "ecs": {
            "x_format": "u8",
            "y_format": "u8",
            "components": components,
            "custom_components": [
                {"name": f"c{i}", "dependencies": [], "fields": []} for i in range(custom)
            ],
        }
    }


@unittest.skipUnless(ASSEMBLER.is_file(), "CPCtelera Next assembler is not installed")
class CollisionAssemblyTests(unittest.TestCase):
    """core/ecs_collision.s must assemble wherever the profile puts COLLISION."""

    def assemble(self, manifest: dict) -> subprocess.CompletedProcess:
        portfolio = json.loads(DEFAULT_PORTFOLIO.read_text(encoding="utf-8"))
        profile = json.loads((ROOT / "profiles/standard-160x200.json").read_text())
        include = generate(manifest, portfolio, profile).include
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "core").mkdir()
            (work / "ecs_profile.inc").write_text(include, encoding="ascii")
            for name in ("ecs_manager.inc", "ecs_collision.inc", "ecs_collision.s"):
                shutil.copy(ROOT / "src/core" / name, work / "core" / name)
            return subprocess.run(
                [str(ASSEMBLER), "-l", "-o", "core/ecs_collision.s"],
                cwd=work,
                capture_output=True,
                text=True,
            )

    def test_collision_in_the_first_byte_of_the_mask(self):
        result = self.assemble(_manifest(["collision"]))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_collision_in_the_second_byte_of_the_mask(self):
        # RENDER + eight custom components put COLLISION on bit 9, where a bare
        # `bit n, ECS_E_COMPONENTS(ix)` is not encodable.
        manifest = _manifest([f"c{i}" for i in range(8)] + ["collision"], custom=8)
        include = generate(
            manifest,
            json.loads(DEFAULT_PORTFOLIO.read_text(encoding="utf-8")),
            json.loads((ROOT / "profiles/standard-160x200.json").read_text()),
        ).include
        self.assertIn("ECS_C_COLLISION_BIT = 9", include)
        result = self.assemble(manifest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
