import tempfile
import unittest
from pathlib import Path

from tools import build_examples

ROOT = Path(__file__).resolve().parents[1]


class ProjectConfigTests(unittest.TestCase):
    def test_local_config_is_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = root / "example"
            (example / "cfg").mkdir(parents=True)
            local = example / "cfg" / "build_config.mk"
            default = root / "build_config.template.mk"
            self.assertEqual(build_examples.select_project_config(example, default), default)
            local.write_text("PROJNAME := local\n", encoding="utf-8")
            self.assertEqual(build_examples.select_project_config(example, default), local)

    def test_render_rewrites_manifest_values_and_keeps_the_rest(self) -> None:
        config = (
            "CPCT_PATH      := relative/\n"
            "PROJNAME   := old\n"
            "TARGET  := $(CDT)\n"
            "Z80CODELOC := 0x0200\n"
            "Z80CCINCLUDE  := -I$(CPCT_SRC)\n"
            "Z80CCFLAGS := -DCUSTOM\n"
        )
        rendered = build_examples.render_build_config(
            config,
            name="demo",
            config_name="cfg/build_config.mk",
            cpct_path=Path("/opt/cpctelera"),
            targets=["$(DSK)"],
            code_start=0x0216,
        )
        self.assertIn("CPCT_PATH      := /opt/cpctelera/", rendered)
        self.assertIn("PROJNAME   := demo", rendered)
        self.assertIn("TARGET  := $(DSK)", rendered)
        self.assertIn("Z80CODELOC := 0x0216", rendered)
        self.assertIn("Z80CCFLAGS := -DCUSTOM", rendered)
        self.assertEqual(rendered.count("-I$(SRCDIR)"), 1)

    def test_render_does_not_duplicate_the_source_include(self) -> None:
        config = (
            "CPCT_PATH      := relative/\n"
            "PROJNAME   := old\n"
            "TARGET  := $(CDT)\n"
            "Z80CODELOC := 0x0200\n"
            "Z80CCINCLUDE  := -I$(CPCT_SRC) -I$(SRCDIR)\n"
        )
        rendered = build_examples.render_build_config(
            config,
            name="demo",
            config_name="cfg/build_config.mk",
            cpct_path=Path("/opt/cpctelera"),
            targets=["$(CDT)"],
            code_start=0x0200,
        )
        self.assertEqual(rendered.count("-I$(SRCDIR)"), 1)

    def test_render_rejects_incomplete_config(self) -> None:
        config = "CPCT_PATH      := relative/\nZ80CCINCLUDE  := -I$(CPCT_SRC)\n"
        with self.assertRaisesRegex(ValueError, "must contain exactly one 'PROJNAME :='"):
            build_examples.render_build_config(
                config,
                name="demo",
                config_name="cfg/build_config.mk",
                cpct_path=Path("/opt/cpctelera"),
                targets=["$(DSK)"],
                code_start=0x0200,
            )

    def test_platformer_ships_its_own_cpctelera_config_and_assets(self) -> None:
        config = ROOT / "examples" / "platformer" / "cfg" / "build_config.mk"
        self.assertTrue(config.is_file(), config)
        text = config.read_text(encoding="utf-8")
        for assignment in ("CPCT_PATH", "PROJNAME", "TARGET", "Z80CODELOC", "Z80CCINCLUDE"):
            self.assertRegex(text, rf"(?m)^{assignment}\s*:=")
        self.assertTrue((ROOT / "examples" / "platformer" / "assets" / "README.md").is_file())


class AssetStagingTests(unittest.TestCase):
    def test_copies_assets_into_the_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = root / "example"
            assets = example / "assets" / "tiles"
            assets.mkdir(parents=True)
            (assets / "level.s").write_text(".module level\n", encoding="utf-8")
            (example / "assets" / "level.inc").write_text("LEVEL_WIDTH = 20\n", encoding="utf-8")
            target = root / "target"
            staged = build_examples.stage_assets(example, target)
            self.assertEqual(staged, ["assets/level.inc", "assets/tiles/level.s"])
            self.assertTrue((target / "src" / "assets" / "tiles" / "level.s").is_file())
            self.assertTrue((target / "src" / "assets" / "level.inc").is_file())

    def test_missing_assets_folder_is_not_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = root / "example"
            example.mkdir()
            self.assertEqual(build_examples.stage_assets(example, root / "target"), [])

    def test_rejects_symlinked_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = root / "example"
            (example / "assets").mkdir(parents=True)
            outside = root / "outside.s"
            outside.write_text(".module outside\n", encoding="utf-8")
            (example / "assets" / "link.s").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "unsafe asset symlink"):
                build_examples.stage_assets(example, root / "target")


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
