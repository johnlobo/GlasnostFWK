import unittest

from tests.test_sprite import clipped_rectangle, source_rows


def masked_byte(background, mask, pixels):
    return (background & mask) | pixels


def masked_rows(background, pixels, masks, width, rectangle):
    pixel_rows = source_rows(pixels, width, rectangle)
    mask_rows = source_rows(masks, width, rectangle)
    return [
        [masked_byte(bg, mask, pixel) for bg, mask, pixel in zip(bg_row, mask_row, pixel_row)]
        for bg_row, mask_row, pixel_row in zip(background, mask_rows, pixel_rows)
    ]


def span_fits(base, width, height):
    return width > 0 and height > 0 and base + width * height <= 0xFFFF


class MaskedSpriteTests(unittest.TestCase):
    def test_transparent_and_opaque_bits_compose(self):
        self.assertEqual(masked_byte(0x55, 0xFF, 0x00), 0x55)
        self.assertEqual(masked_byte(0x55, 0x00, 0xAA), 0xAA)
        # Mode 0 packs two 4-bit pixels per byte: F0 preserves one, 0F replaces
        # the other, so transparency can be per pixel rather than per byte.
        self.assertEqual(masked_byte(0x3C, 0xF0, 0x05), 0x35)

    def test_clipping_offsets_pixels_and_mask_together(self):
        rectangle = clipped_rectangle(-2, -1, 4, 3, 80, 200)
        pixels = list(range(12))
        masks = [0x00] * 4 + [0xFF, 0xFF, 0x00, 0x00] + [0x00] * 4
        background = [[0x80, 0x81], [0x90, 0x91]]
        self.assertEqual(
            masked_rows(background, pixels, masks, 4, rectangle),
            [[0x06, 0x07], [0x0A, 0x0B]],
        )

    def test_mask_span_must_not_wrap(self):
        self.assertTrue(span_fits(0x4000, 6, 8))
        self.assertFalse(span_fits(0xFFF0, 6, 8))

    def test_asset_data_must_be_zero_under_preserved_bits(self):
        pixels = [0x00, 0x0F, 0xA0]
        masks = [0xFF, 0xF0, 0x0F]
        self.assertTrue(all((pixel & mask) == 0 for pixel, mask in zip(pixels, masks)))


if __name__ == "__main__":
    unittest.main()
