"""Mode 1 font geometry and public build contract."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def font_bytes(source: str, start: str, end: str | None = None) -> bytes:
    block = source.split(start, 1)[1]
    if end is not None:
        block = block.split(end, 1)[0]
    return bytes(int(value, 16) for value in re.findall(r"0x([0-9A-Fa-f]{2})", block))


class Mode1TextTests(unittest.TestCase):
    def test_deckhero_font_and_small_digits_have_expected_geometry(self) -> None:
        source = (ROOT / "framework/src/ui/text_mode1.inc").read_text(encoding="ascii")
        font = font_bytes(source, "_fwk_m1_default_font:", "_fwk_m1_default_small_digits:")
        small = font_bytes(source, "_fwk_m1_default_small_digits:")
        self.assertEqual(len(font), 43 * 9)
        self.assertEqual(len(small), 10 * 5)
        self.assertTrue((ROOT / "framework/assets/font_chars_1.png").is_file())
        # DeckHero's Mode 1 source glyphs use only pen 1 (high nibble) and
        # transparent pen 0; recolouring can safely select pens 1, 2 or 3.
        self.assertTrue(all(value & 0x0F == 0 for value in font))
        self.assertEqual(
            small,
            bytes(font[(4 + digit) * 9 + row] for digit in range(10) for row in (0, 1, 3, 5, 6)),
        )

    def test_mode1_text_exposes_the_common_api(self) -> None:
        source = (ROOT / "framework/src/ui/text_mode1.s").read_text(encoding="ascii")
        for symbol in (
            "fwk_text_init::",
            "fwk_text_set_assets::",
            "fwk_text_set_color::",
            "fwk_text_set_colors::",
            "fwk_text_draw::",
            "fwk_text_draw_small_digit::",
            "fwk_text_draw_small_u8::",
        ):
            self.assertIn(symbol, source)
        self.assertIn("sub #44", source)  # 0..9 -> glyphs 4..13
        self.assertIn("sub #48", source)  # A..Z -> glyphs 17..42


if __name__ == "__main__":
    unittest.main()
