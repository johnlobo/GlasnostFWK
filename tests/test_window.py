import unittest


def window_geometry_valid(
    x, y, width, height, screen_width=80, screen_height=200
):
    """Mirror the fixed Z80 validation contract used by ui/window.s."""
    if width < 2:
        return False
    if x + width > 0xFF or x + width > screen_width:
        return False
    if height < 2:
        return False
    if y + height > 0xFFFF:
        return False
    return y + height <= screen_height


class WindowGeometryTests(unittest.TestCase):
    def test_accepts_drawable_and_exactly_fitting_regions(self):
        self.assertTrue(window_geometry_valid(10, 40, 20, 16))
        self.assertTrue(window_geometry_valid(60, 184, 20, 16))

    def test_rejects_regions_outside_the_screen(self):
        self.assertFalse(window_geometry_valid(75, 40, 10, 10))
        self.assertFalse(window_geometry_valid(10, 190, 10, 16))
        self.assertFalse(window_geometry_valid(10, 40, 0, 16))
        self.assertFalse(window_geometry_valid(10, 40, 10, 1))

    def test_rejects_y_plus_height_wrap(self):
        self.assertFalse(window_geometry_valid(10, 0xFFFF, 10, 2))
        self.assertFalse(window_geometry_valid(10, 0xFFFE, 10, 2))
        self.assertFalse(window_geometry_valid(10, 0xFFF0, 10, 0x20))


if __name__ == "__main__":
    unittest.main()
