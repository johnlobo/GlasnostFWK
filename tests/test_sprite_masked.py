import unittest

from tests.test_sprite import clipped_rectangle, source_rows
from tools.project_config import mode0_mask_table


def transparent_byte(background, source, table):
    mask = table[source]
    return (background & mask) | (source & ~mask)


def transparent_rows(background, pixels, width, rectangle, table):
    pixel_rows = source_rows(pixels, width, rectangle)
    return [
        [transparent_byte(bg, pixel, table) for bg, pixel in zip(bg_row, pixel_row)]
        for bg_row, pixel_row in zip(background, pixel_rows)
    ]


def packed_mode0_pen(pen):
    pattern = 0
    for source_bit, (left_bit, right_bit) in enumerate(
        ((7, 6), (3, 2), (5, 4), (1, 0))
    ):
        bit = (pen >> source_bit) & 1
        pattern |= bit << left_bit
        pattern |= bit << right_bit
    return pattern


def recolor_byte(value, old_pen, new_pen):
    old_pattern = packed_mode0_pen(old_pen)
    new_pattern = packed_mode0_pen(new_pen)
    result = value
    if (value & 0xAA) == (old_pattern & 0xAA):
        result = (result & 0x55) | (new_pattern & 0xAA)
    if (value & 0x55) == (old_pattern & 0x55):
        result = (result & 0xAA) | (new_pattern & 0x55)
    return result


def recolor_transparent_byte(background, source, old_pen, new_pen, table):
    return transparent_byte(background, recolor_byte(source, old_pen, new_pen), table)


def span_fits(base, width, height):
    return width > 0 and height > 0 and base + width * height <= 0xFFFF


class TransparentSpriteTests(unittest.TestCase):
    def test_pen_three_can_be_transparent_or_opaque_per_pixel(self):
        table = mode0_mask_table(3)
        self.assertEqual(transparent_byte(0x55, 0xCC, table), 0x55)
        self.assertEqual(transparent_byte(0x55, 0xF0, table), 0xF0)
        # 0xE4 packs an opaque pen-5 left pixel and transparent pen-3 right.
        self.assertEqual(transparent_byte(0x3C, 0xE4, table), 0xB4)

    def test_clipping_offsets_the_single_colour_key_asset(self):
        rectangle = clipped_rectangle(-2, -1, 4, 3, 80, 200)
        pixels = [0xCC] * 4 + [0xCC, 0xCC, 0xF0, 0xAA] + [0xCC] * 4
        background = [[0x80, 0x81], [0x90, 0x91]]
        self.assertEqual(
            transparent_rows(background, pixels, 4, rectangle, mode0_mask_table(3)),
            [[0xF0, 0xAA], [0x90, 0x91]],
        )

    def test_source_span_must_not_wrap(self):
        self.assertTrue(span_fits(0x4000, 6, 8))
        self.assertFalse(span_fits(0xFFF0, 6, 8))

    def test_pen_zero_table_preserves_source_zero_bits(self):
        table = mode0_mask_table(0)
        self.assertEqual(transparent_byte(0x3C, 0xF5, table), 0xF5)

    def test_recolor_replaces_each_matching_mode_zero_pixel(self):
        self.assertEqual(recolor_byte(0xF0, 5, 15), 0xFF)
        # Mixed byte: left pen 5 is replaced; right pen 3 remains unchanged.
        self.assertEqual(recolor_byte(0xE4, 5, 15), 0xEE)

    def test_recolor_happens_before_transparency(self):
        table = mode0_mask_table(3)
        self.assertEqual(
            recolor_transparent_byte(0x55, 0xF0, 5, 3, table),
            0x55,
        )
        self.assertEqual(
            recolor_transparent_byte(0x55, 0xCC, 3, 5, table),
            0xF0,
        )

    def test_recolor_pens_are_restricted_to_mode_zero_range(self):
        for pen in (0, 15):
            self.assertEqual(pen & 0xF0, 0)
        for pen in (16, 255):
            self.assertNotEqual(pen & 0xF0, 0)


if __name__ == "__main__":
    unittest.main()
