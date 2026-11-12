"""Integration contracts for public examples and internal CPC validations."""

import json
import tempfile
import unittest
from pathlib import Path

from tools.build.program_catalog import manifest_path, program_folder, program_folders, program_names
from tools.build.build_test_disk import program_bin_name
from tools.glasnost.glasnost import example_names

ROOT = Path(__file__).resolve().parents[1]


class ProgramCatalogTests(unittest.TestCase):
    def test_public_catalog_excludes_internal_and_retired_programs(self):
        examples = set(program_names(ROOT, "examples"))
        validations = set(program_names(ROOT, "validations"))
        self.assertEqual(validations, {
            "video", "ecsmanager", "ecscollision", "ecsanimation", "ecsrender", "perf", "experimental",
        })
        self.assertEqual(len(examples), 16)
        self.assertIn("text", examples)
        self.assertIn("mode1", examples)
        self.assertFalse({"board", "vertical"} & set(program_names(ROOT)))
        self.assertFalse(examples & validations)
        self.assertEqual(set(example_names(ROOT)), examples)
        for name in validations | {"board", "vertical"}:
            self.assertFalse((ROOT / "examples" / name).exists(), name)

    def test_disk_catalog_reads_internal_manifest_amsdos_override(self):
        self.assertEqual(program_bin_name(ROOT, "ecsrender"), "ECSREND.BIN")
        folder = program_folder(ROOT, "ecsrender")
        self.assertEqual(folder, ROOT / "framework/validations/ecsrender")

    def test_media_filter_respects_disk_only_programs(self):
        tapes = set(program_names(ROOT, media="cdt"))
        self.assertNotIn("perf", tapes)
        self.assertNotIn("diskload", tapes)
        self.assertEqual(len(tapes), len(program_names(ROOT)) - 2)

    def test_ambiguous_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for prefix in ("examples", "framework/validations"):
                manifest = root / prefix / "same/glasnost.manifest.json"
                manifest.parent.mkdir(parents=True)
                manifest.write_text(json.dumps({"name": "same"}))
            with self.assertRaisesRegex(ValueError, "duplicate program"):
                program_folders(root)
            with self.assertRaisesRegex(ValueError, "duplicate program"):
                program_folder(root, "same")

    def test_legacy_manifests_are_discovered_without_being_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "examples/old"
            folder.mkdir(parents=True)
            legacy = folder / "example.json"
            raw = b'{ "name": "old", "media": ["dsk"], "amsdos_name": "LEGACY" }\n'
            legacy.write_bytes(raw)
            self.assertEqual(program_names(root), ("old",))
            self.assertEqual(program_names(root, media="cdt"), ())
            self.assertEqual(program_bin_name(root, "old"), "LEGACY.BIN")
            self.assertEqual(manifest_path(folder), legacy)
            self.assertEqual(legacy.read_bytes(), raw)
            self.assertFalse((folder / "glasnost.manifest.json").exists())

    def test_both_manifest_names_are_rejected_even_when_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "framework/validations/ambiguous"
            folder.mkdir(parents=True)
            for name in ("example.json", "glasnost.manifest.json"):
                (folder / name).write_text('{"name":"ambiguous"}')
            with self.assertRaisesRegex(ValueError, "ambiguous manifests"):
                program_names(root)
            with self.assertRaisesRegex(ValueError, "ambiguous manifests"):
                program_bin_name(root, "ambiguous")


if __name__ == "__main__":
    unittest.main()
