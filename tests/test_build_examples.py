import tempfile
import unittest
from pathlib import Path

from tools import build_examples


class DiskStagingTests(unittest.TestCase):
    def test_stages_hex_payload_and_generates_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = root / "example"
            target = root / "target"
            example.mkdir()
            (target / "src").mkdir(parents=True)
            (example / "payload.hex").write_text("00 41 ff\n", encoding="ascii")
            manifest = {
                "media": ["dsk"],
                "disk_files": [
                    {
                        "source": "payload.hex",
                        "encoding": "hex",
                        "name": "DATA.BIN",
                        "symbol": "data",
                        "compression": "none",
                    }
                ],
            }
            entries = build_examples.stage_disk_files(
                example, manifest, target, root / "unused-cpct"
            )
            self.assertEqual((target / "dsk" / "DATA.BIN").read_bytes(), b"\x00A\xff")
            self.assertEqual(entries[0]["size"], 3)
            include = (target / "src" / "disk_files.inc").read_text()
            self.assertIn("FWK_DISK_DATA_SIZE = 0x0003", include)
            self.assertIn("FWK_DISK_DATA_UNPACKED_SIZE = 0x0003", include)

    def test_rejects_invalid_amsdos_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "invalid AMSDOS"):
                build_examples.stage_disk_files(
                    root,
                    {
                        "media": ["dsk"],
                        "disk_files": [
                            {
                                "source": "payload.bin",
                                "name": "TOO-LONG-NAME.BIN",
                                "symbol": "data",
                            }
                        ],
                    },
                    root / "target",
                    root / "cpct",
                )

    def test_rejects_symbols_that_collide_after_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.bin").write_bytes(b"one")
            (root / "two.bin").write_bytes(b"two")
            entries = [
                {"source": "one.bin", "name": "ONE.BIN", "symbol": "data"},
                {"source": "two.bin", "name": "TWO.BIN", "symbol": "DATA"},
            ]
            with self.assertRaisesRegex(ValueError, "duplicate disk symbol"):
                build_examples.stage_disk_files(
                    root,
                    {"media": ["dsk"], "disk_files": entries},
                    root / "target",
                    root / "cpct",
                )

    def test_rejects_symlink_outside_example(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = root / "example"
            example.mkdir()
            outside = root / "outside.bin"
            outside.write_bytes(b"data")
            (example / "payload.bin").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "unsafe example path"):
                build_examples._safe_example_file(example, "payload.bin")


if __name__ == "__main__":
    unittest.main()
