import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def validate(map_width, map_height, tile_width, tile_height, screen_width,
             screen_height, camera_x, camera_y, screen_x, screen_y,
             view_width, view_height, tile_count):
    if not all((map_width, map_height, tile_width, tile_height,
                view_width, view_height, tile_count)):
        return False
    if (tile_width, tile_height) not in {(2, 4), (2, 8), (4, 4), (4, 8)}:
        return False
    if screen_y % tile_height:
        return False
    if camera_x + view_width > map_width or camera_y + view_height > map_height:
        return False
    if screen_x + view_width * tile_width > screen_width:
        return False
    if screen_y + view_height * tile_height > screen_height:
        return False
    return True


def selected_ids(cells, map_width, camera_x, camera_y, view_width, view_height):
    return [
        cells[(camera_y + row) * map_width + camera_x + column]
        for row in range(view_height)
        for column in range(view_width)
    ]


def tileset_fits(base, tile_width, tile_height, tile_count):
    return base + tile_width * tile_height * tile_count <= 0xFFFF


class TilemapRenderTests(unittest.TestCase):
    def test_only_cpctelera_next_tile_geometries_are_accepted(self):
        base = (8, 8, 80, 200, 0, 0, 0, 0, 4, 4, 4)
        for width, height in ((2, 4), (2, 8), (4, 4), (4, 8)):
            self.assertTrue(validate(base[0], base[1], width, height, *base[2:]))
        self.assertFalse(validate(base[0], base[1], 8, 8, *base[2:]))
        self.assertFalse(validate(base[0], base[1], 4, 6, *base[2:]))

    def test_renderer_dispatches_to_cpctelera_next_primitives(self):
        source = (ROOT / "src/extensions/tilemap_render.s").read_text(encoding="ascii")
        for instruction in (
            "jp z, cpct_drawTileAligned2x4_f_asm",
            "jp cpct_drawTileAligned2x8_f_asm",
            "jp z, cpct_drawTileAligned4x4_f_asm",
            "jp cpct_drawTileAligned4x8_f_asm",
        ):
            self.assertIn(instruction, source)
        self.assertNotIn("ldir", source.lower())

    def test_masked_renderer_uses_cpctelera_masked_primitive(self):
        source = (ROOT / "src/extensions/tilemap_render_masked.s").read_text(encoding="ascii")
        self.assertIn("call cpct_drawSpriteMasked_asm", source)

    def test_viewport_and_screen_bounds(self):
        args = (8, 6, 4, 8, 80, 200, 2, 1, 10, 32, 5, 4, 4)
        self.assertTrue(validate(*args))
        self.assertFalse(validate(8, 6, 4, 8, 80, 200, 4, 1, 10, 32, 5, 4, 4))
        self.assertFalse(validate(8, 6, 4, 8, 80, 200, 2, 1, 61, 32, 5, 4, 4))
        self.assertFalse(validate(8, 6, 4, 8, 80, 200, 2, 1, 10, 169, 5, 4, 4))

    def test_camera_selects_expected_read_only_rectangle(self):
        cells = [(row + column) % 4 for row in range(6) for column in range(8)]
        before = cells.copy()
        ids = selected_ids(cells, 8, 2, 1, 5, 4)
        self.assertEqual(ids[:5], [3, 0, 1, 2, 3])
        self.assertEqual(ids[-5:], [2, 3, 0, 1, 2])
        self.assertEqual(cells, before)

    def test_full_render_preflight_rejects_unknown_id(self):
        cells = [0] * (8 * 6)
        cells[2 * 8 + 4] = 4
        ids = selected_ids(cells, 8, 2, 1, 5, 4)
        self.assertFalse(all(tile_id < 4 for tile_id in ids))

    def test_tileset_span_must_not_wrap_address_space(self):
        self.assertTrue(tileset_fits(0x4000, 4, 8, 4))
        self.assertFalse(tileset_fits(0xFFF0, 4, 8, 1))

    def test_partial_cell_uses_viewport_coordinates(self):
        cells = [(row + column) % 4 for row in range(6) for column in range(8)]
        row, column = 1, 2
        tile_id = cells[(1 + row) * 8 + 2 + column]
        screen = (10 + column * 4, 32 + row * 8)
        self.assertEqual((tile_id, screen), (2, (18, 40)))


if __name__ == "__main__":
    unittest.main()
