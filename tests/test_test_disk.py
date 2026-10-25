import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import build_test_disk


class TestDiskTests(unittest.TestCase):
    def test_uses_unique_amsdos_names(self) -> None:
        self.assertEqual(build_test_disk.amsdos_bin_name("minimal"), "MINIMAL.BIN")
        self.assertEqual(
            build_test_disk.amsdos_bin_name("resources128"), "RESOURCE.BIN"
        )

    def test_builds_one_disk_with_programs_and_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cpct = root / "cpct"
            idsk = cpct / "tools" / "iDSK-0.13" / "bin" / "iDSK"
            idsk.parent.mkdir(parents=True)
            idsk.write_bytes(b"tool")
            for example in ("minimal", "diskload"):
                base = root / ".build" / example
                (base / "obj").mkdir(parents=True)
                (base / "obj" / f"{example}.bin").write_bytes(example.encode())
                (base / "obj" / "binaryAddresses.log").write_text(
                    "Load Address = 4000\nRun  Address = 4010\n",
                    encoding="ascii",
                )
                disk_files = []
                if example == "diskload":
                    (base / "dsk").mkdir()
                    (base / "dsk" / "RAWDATA.BIN").write_bytes(b"payload")
                    disk_files = [{"name": "RAWDATA.BIN"}]
                (base / "selected-modules.json").write_text(
                    json.dumps({"disk_files": disk_files}), encoding="utf-8"
                )
                (base / f"{example}.dsk").write_bytes(b"intermediate")

            def fake_run(command, check):
                if command[-1] == "-n":
                    Path(command[1]).write_bytes(b"dsk")

            with patch.object(build_test_disk.subprocess, "run", side_effect=fake_run) as run:
                disk = build_test_disk.build_test_disk(
                    root, cpct, ("minimal", "diskload"), remove_individual=True
                )

            self.assertTrue(disk.is_file())
            self.assertEqual(run.call_count, 4)
            minimal_command = run.call_args_list[1].args[0]
            self.assertIn("-c", minimal_command)
            self.assertEqual(minimal_command[minimal_command.index("-c") + 1], "4000")
            self.assertEqual(minimal_command[minimal_command.index("-e") + 1], "4010")
            catalog = json.loads((disk.parent / "catalog.json").read_text())
            self.assertEqual(
                [entry["name"] for entry in catalog["entries"]],
                ["MINIMAL.BIN", "DISKLOAD.BIN", "RAWDATA.BIN"],
            )
            self.assertFalse((root / ".build" / "minimal" / "minimal.dsk").exists())
            self.assertFalse((root / ".build" / "diskload" / "diskload.dsk").exists())

    def test_rejects_catalog_name_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for example in ("abcdefgh1", "abcdefgh2"):
                base = root / ".build" / example
                (base / "obj").mkdir(parents=True)
                (base / "obj" / f"{example}.bin").write_bytes(b"bin")
                (base / "obj" / "binaryAddresses.log").write_text(
                    "Load Address = 4000\nRun Address = 4000\n",
                    encoding="ascii",
                )
                (base / "selected-modules.json").write_text(
                    '{"disk_files": []}', encoding="utf-8"
                )
            with self.assertRaisesRegex(ValueError, "duplicate AMSDOS filename"):
                build_test_disk.collect_entries(root, ("abcdefgh1", "abcdefgh2"))


if __name__ == "__main__":
    unittest.main()
