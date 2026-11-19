"""Static contracts of fwk_disk_save and fwk_input_repeat; behaviour is checked in
BluePixel by tests/bluepixel_validations_smoke.py (validations disksave, uiinput)."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def constants(path: Path) -> dict[str, str]:
    return dict(re.findall(r"^(FWK_DISK_\w+)\s*=\s*(\S+)", path.read_text(encoding="ascii"), re.M))


class DiskSaveTests(unittest.TestCase):
    def test_descriptor_layout_is_contiguous(self):
        values = constants(ROOT / "framework/src/resources/disk.inc")
        fields = [("NAME", 2), ("NAME_LENGTH", 1), ("DATA", 2), ("LENGTH", 2),
                  ("BUFFER", 2), ("INKS", 2), ("MODE", 1)]
        offset = 0
        for name, size in fields:
            self.assertEqual(int(values[f"FWK_DISK_SAVE_{name}"], 0), offset, name)
            offset += size
        self.assertEqual(int(values["FWK_DISK_SAVE_SIZE"], 0), offset)
        self.assertEqual(int(values["FWK_DISK_BUFFER_SIZE"], 0), 2048)

    def test_init_keeps_the_firmware_vector_and_save_is_documented(self):
        source = (ROOT / "framework/src/resources/disk.s").read_text(encoding="ascii")
        init = source.split("fwk_disk_init::", 1)[1].split("ret", 1)[0]
        self.assertIn("_fwk_disk_firmware_vector", init)
        self.assertIn("fwk_disk_save::", source)
        self.assertIn("FWK_DISK_AMSDOS_MESSAGES", source)
        api = (ROOT / "docs/reference/architecture-and-api.md").read_text(encoding="utf-8")
        self.assertIn("`fwk_disk_save`", api)

    def test_validation_descriptors_match_the_layout(self):
        source = (ROOT / "framework/validations/disksave/main.s").read_text(encoding="ascii")
        for label in ("_descriptor:", "_plain:", "_outside:"):
            block = source.split(label, 1)[1].split("\n\n", 1)[0].split(";;", 1)[0]
            sizes = [2 if line.strip().startswith(".dw") else 1
                     for line in block.splitlines() if line.strip().startswith((".dw", ".db"))]
            self.assertEqual(sum(sizes), 12, label)


class InputRepeatTests(unittest.TestCase):
    def test_repeat_api_and_defaults(self):
        source = (ROOT / "framework/src/core/input.s").read_text(encoding="ascii")
        for symbol in ("fwk_input_repeat::", "fwk_input_set_repeat::"):
            self.assertIn(symbol, source)
        self.assertRegex(source, r"_fwk_input_repeat_delay:\s+\.db 15")
        self.assertRegex(source, r"_fwk_input_repeat_interval:\s+\.db 4")
        update = source.split("fwk_input_update::", 1)[1]
        self.assertIn("ld (fwk_input_repeat), a", update)


if __name__ == "__main__":
    unittest.main()
