#!/usr/bin/env python3
import os
import subprocess
import unittest
from pathlib import Path

from tools.build.program_catalog import program_folder, program_folders

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = (
    "# Standalone build entry point for this example; see framework/cfg/example.mk.\n"
    "GLASNOST_EXAMPLE_DIR := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))\n"
    "include $(GLASNOST_EXAMPLE_DIR)/../../framework/cfg/example.mk\n"
)


class ExampleTargetTests(unittest.TestCase):
    def examples(self):
        return sorted(path.parent for path in (folder / "glasnost.manifest.json" for folder in program_folders(ROOT)))

    def make_dry_run(self, example: str, target: str, *, env=None, extra=()) -> str:
        result = subprocess.run(
            ["make", "-n", "-C", str(program_folder(ROOT, example)), target, *extra],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return result.stdout

    def test_every_example_uses_the_shared_wrapper(self):
        self.assertTrue(self.examples())
        for example in self.examples():
            makefile = example / "Makefile"
            self.assertTrue(makefile.is_file(), f"falta {makefile.relative_to(ROOT)}")
            expected = WRAPPER
            if example.parent.name == "validations":
                expected = WRAPPER.replace(
                    "include $(GLASNOST_EXAMPLE_DIR)/../../framework/cfg/example.mk",
                    "GLASNOST_ROOT := $(abspath $(GLASNOST_EXAMPLE_DIR)/../../..)\n"
                    "include $(GLASNOST_EXAMPLE_DIR)/../../cfg/example.mk",
                )
            self.assertEqual(makefile.read_text(encoding="utf-8"), expected, str(makefile))

    def test_build_target_stages_only_that_example(self):
        output = self.make_dry_run("minimal", "build")
        self.assertIn("build_examples.py minimal", output)
        for other in ("audio", "text", "platformer"):
            self.assertNotIn(f"build_examples.py {other}", output)

    def test_internal_validation_resolves_the_repository_root(self):
        output = self.make_dry_run("ecsmanager", "build")
        self.assertIn(f"{ROOT}/tools/build/build_examples.py ecsmanager", output)
        self.assertIn(str(ROOT / "build/ecsmanager/obj"), output)
        self.assertIn(str(ROOT / "framework/validations/ecsmanager"), output)

    def test_clean_target_removes_only_that_staging_directory(self):
        output = self.make_dry_run("minimal", "clean")
        self.assertIn(str(ROOT / "build" / "minimal"), output)
        self.assertNotIn(str(ROOT / "build" / "tests"), output)

    def test_build_target_copies_artifacts_next_to_the_example(self):
        output = self.make_dry_run("minimal", "build")
        staging = str(ROOT / "build" / "minimal")
        destination = str(ROOT / "examples" / "minimal")
        self.assertIn(f'source="{staging}/obj/$file"', output)
        self.assertIn(f'cp -f "$source" "{destination}/$file"', output)
        self.assertIn("minimal.bin minimal.cdt minimal.dsk", output)

    def test_clean_target_removes_local_artifact_copies(self):
        output = self.make_dry_run("minimal", "clean")
        destination = ROOT / "examples" / "minimal"
        for suffix in ("bin", "cdt", "dsk"):
            self.assertIn(str(destination / f"minimal.{suffix}"), output)

    def test_run_target_reuses_the_build(self):
        wrapper = (ROOT / "framework" / "cfg" / "example.mk").read_text(encoding="utf-8")
        self.assertRegex(wrapper, r"(?m)^run: build$")
        self.assertIn("tools/glasnost/run_example.py", wrapper)

    def test_ambient_cpct_path_cannot_replace_the_pinned_revision(self):
        ambient = dict(os.environ, CPCT_PATH="/opt/unpinned/cpctelera")
        output = self.make_dry_run("minimal", "build", env=ambient)
        self.assertNotIn("--cpct-path", output)
        # CPCT_NEXT_PATH keeps working, as in the rest of the repository.
        pinned = dict(os.environ, CPCT_NEXT_PATH="/opt/pinned/cpctelera")
        output = self.make_dry_run("minimal", "build", env=pinned)
        self.assertNotIn("--cpct-path", output)

    def test_explicit_cpct_path_is_forwarded(self):
        output = self.make_dry_run(
            "minimal", "build", extra=("CPCT_PATH=/opt/pinned/cpctelera",)
        )
        self.assertIn("--cpct-path /opt/pinned/cpctelera", output)


if __name__ == "__main__":
    unittest.main()
