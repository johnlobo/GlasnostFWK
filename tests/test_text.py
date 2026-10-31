import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def bytes_between(source: str, start: str, end: str | None) -> list[int]:
    block = source.split(start, 1)[1]
    if end is not None:
        block = block.split(end, 1)[0]
    return [int(value, 16) for value in re.findall(r"0x([0-9A-Fa-f]{2})", block)]


class TextModuleTests(unittest.TestCase):
    def test_default_asset_geometry(self) -> None:
        source = (ROOT / "src/ui/text.inc").read_text(encoding="ascii")
        font = bytes_between(
            source, "_fwk_text_default_font:", "_fwk_text_default_small_digits:"
        )
        small = bytes_between(
            source,
            "_fwk_text_default_small_digits:",
            None,
        )
        self.assertEqual(len(font), 51 * 2 * 9)
        self.assertEqual(len(small), 10 * 2 * 5)
        self.assertEqual(
            hashlib.sha256(bytes(font)).hexdigest(),
            "b7d98821663e779adce7bf5a0aeab2f343f37fed6e6fb97352b445715e68d6db",
        )
        self.assertEqual(
            hashlib.sha256(bytes(small)).hexdigest(),
            "ad6e15edca2bb6f5aa7a41a04f694a197ede84ce7dbb3c82b2c647b8e7fe5dc0",
        )

    def test_public_api_and_original_character_mapping_are_present(self) -> None:
        source = (ROOT / "src/ui/text.s").read_text(encoding="ascii")
        for symbol in (
            "fwk_text_init::",
            "fwk_text_set_assets::",
            "fwk_text_set_color::",
            "fwk_text_draw::",
            "fwk_text_draw_small_digit::",
            "fwk_text_draw_small_u8::",
        ):
            self.assertIn(symbol, source)
        self.assertIn("sub #39", source)  # ASCII digits -> frames 9..18
        self.assertIn("sub #44", source)  # A..Z -> frames 21..46
        for frame in (47, 48, 49, 50):
            self.assertIn(f"ld a, #{frame}", source)


if __name__ == "__main__":
    unittest.main()
