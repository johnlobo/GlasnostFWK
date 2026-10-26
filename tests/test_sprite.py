import unittest


def clip_axis(position, size, limit):
    if size <= 0:
        raise ValueError("size must be positive")
    source = max(0, -position)
    destination = max(0, position)
    visible = min(size - source, limit - destination)
    if source >= size or destination >= limit or visible <= 0:
        return 0, 0, 0
    return source, destination, visible


def clipped_rectangle(x, y, width, height, screen_width, screen_height):
    source_x, destination_x, visible_width = clip_axis(x, width, screen_width)
    source_y, destination_y, visible_height = clip_axis(y, height, screen_height)
    if not visible_width or not visible_height:
        return None
    return (
        source_x,
        source_y,
        destination_x,
        destination_y,
        visible_width,
        visible_height,
    )


def source_rows(data, width, rectangle):
    source_x, source_y, _, _, visible_width, visible_height = rectangle
    return [
        data[(source_y + row) * width + source_x:
             (source_y + row) * width + source_x + visible_width]
        for row in range(visible_height)
    ]


def source_span_fits(base, width, height):
    return width > 0 and height > 0 and base + width * height <= 0xFFFF


class SpriteTests(unittest.TestCase):
    def test_left_and_top_clipping_offsets_source(self):
        self.assertEqual(
            clipped_rectangle(-2, -3, 6, 8, 80, 200),
            (2, 3, 0, 0, 4, 5),
        )

    def test_right_and_bottom_clipping_limits_destination(self):
        self.assertEqual(
            clipped_rectangle(77, 196, 6, 8, 80, 200),
            (0, 0, 77, 196, 3, 4),
        )
        self.assertEqual(
            clipped_rectangle(20, 285, 6, 8, 80, 288),
            (0, 0, 20, 285, 6, 3),
        )

    def test_fully_outside_rectangle_is_empty(self):
        self.assertIsNone(clipped_rectangle(100, 20, 6, 8, 80, 200))
        self.assertIsNone(clipped_rectangle(-6, 20, 6, 8, 80, 200))
        self.assertIsNone(clipped_rectangle(20, -8, 6, 8, 80, 200))

    def test_rows_keep_original_sprite_stride(self):
        data = list(range(48))
        rectangle = clipped_rectangle(-2, -3, 6, 8, 80, 200)
        self.assertEqual(source_rows(data, 6, rectangle)[0], [20, 21, 22, 23])
        self.assertEqual(source_rows(data, 6, rectangle)[-1], [44, 45, 46, 47])

    def test_source_span_must_not_wrap(self):
        self.assertTrue(source_span_fits(0x4000, 6, 8))
        self.assertFalse(source_span_fits(0xFFF0, 6, 8))
        self.assertFalse(source_span_fits(0x4000, 0, 8))

    def test_capture_size_matches_visible_rectangle(self):
        rectangle = clipped_rectangle(-2, -3, 6, 8, 80, 200)
        self.assertEqual(rectangle[4] * rectangle[5], 20)


if __name__ == "__main__":
    unittest.main()
