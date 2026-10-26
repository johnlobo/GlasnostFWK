import unittest

from tests.test_physics_profiles import platform_steps


PASSABLE = 0
SOLID = 1
ONE_WAY = 2
AIRBORNE = 1
TILE_GROUNDED = 2

HIT_LEFT = 1
HIT_RIGHT = 2
HIT_CEILING = 4
HIT_FLOOR = 8
SUPPORT_LOST = 16


def make_map():
    cells = [PASSABLE] * (20 * 25)
    for column in range(16):
        cells[5 * 20 + column] = SOLID
    for row in range(5, 20):
        cells[row * 20 + 15] = SOLID
    for column in range(20):
        cells[20 * 20 + column] = SOLID
    return cells


def query(cells, types, x, y, width=20, height=25, x_shift=2, y_shift=3):
    column = x >> x_shift
    row = y >> y_shift
    if column >= width or row >= height:
        return None
    tile_id = cells[row * width + column]
    if tile_id >= len(types):
        return None
    return types[tile_id]


def resolve(state, cells, types):
    x, y, vx, vy, width, height, flags = state
    hits = 0
    previous_y = y - vy

    if vx > 0:
        edge = x + width - 1
        if any(query(cells, types, edge, sample) == SOLID for sample in (previous_y, previous_y + height - 1)):
            x = (edge & ~3) - width
            vx = 0
            hits |= HIT_RIGHT
    elif vx < 0:
        edge = x
        if any(query(cells, types, edge, sample) == SOLID for sample in (previous_y, previous_y + height - 1)):
            x = (edge & ~3) + 4
            vx = 0
            hits |= HIT_LEFT

    if vy > 0:
        bottom = y + height - 1
        for foot in (x, x + width - 1):
            tile_type = query(cells, types, foot, bottom)
            tile_top = bottom & ~7
            crossed = bottom - vy < tile_top
            if tile_type == SOLID or (tile_type == ONE_WAY and crossed):
                y = tile_top - height
                vy = 0
                flags = (flags & ~AIRBORNE) | TILE_GROUNDED
                hits |= HIT_FLOOR
                break
    elif vy < 0:
        if any(query(cells, types, sample, y) == SOLID for sample in (x, x + width - 1)):
            y = (y & ~7) + 8
            vy = 0
            flags = (flags | AIRBORNE) & ~TILE_GROUNDED
            hits |= HIT_CEILING
    elif flags & TILE_GROUNDED:
        below = y + height
        if not any(query(cells, types, foot, below) in (SOLID, ONE_WAY) for foot in (x, x + width - 1)):
            flags = (flags | AIRBORNE) & ~TILE_GROUNDED
            hits |= SUPPORT_LOST

    return (x, y, vx, vy, width, height, flags), hits


class TilemapCollisionTests(unittest.TestCase):
    def test_read_only_query_and_bounds(self):
        cells = make_map()
        types = (PASSABLE, SOLID, ONE_WAY)
        self.assertEqual(query(cells, types, 10, 10), PASSABLE)
        self.assertEqual(query(cells, types, 60, 80), SOLID)
        self.assertIsNone(query(cells, types, 80, 10))
        broken = cells.copy()
        broken[0] = 3
        self.assertIsNone(query(broken, types, 0, 0))

    def test_sample_hits_ceiling_right_wall_and_floor(self):
        cells = make_map()
        types = (PASSABLE, SOLID, ONE_WAY)
        state = (20, 60, 0, -8, 2, 4, AIRBORNE)
        hits = 0
        for _ in range(96):
            state = platform_steps(state, (80, 199, 1, 8), 1)
            state, frame_hits = resolve(state, cells, types)
            if frame_hits & HIT_CEILING:
                state = (state[0], state[1], 2, *state[3:])
            hits |= frame_hits
        self.assertEqual(state, (58, 156, 0, 0, 2, 4, TILE_GROUNDED))
        self.assertEqual(hits, HIT_RIGHT | HIT_CEILING | HIT_FLOOR)

    def test_one_way_only_blocks_a_downward_crossing(self):
        cells = [PASSABLE] * (20 * 25)
        cells[10 * 20 + 5] = ONE_WAY
        types = (PASSABLE, SOLID, ONE_WAY)

        rising, hits = resolve((20, 81, 0, -2, 2, 4, AIRBORNE), cells, types)
        self.assertEqual((rising, hits), ((20, 81, 0, -2, 2, 4, AIRBORNE), 0))

        falling, hits = resolve((20, 78, 0, 3, 2, 4, AIRBORNE), cells, types)
        self.assertEqual(falling, (20, 76, 0, 0, 2, 4, TILE_GROUNDED))
        self.assertEqual(hits, HIT_FLOOR)

    def test_tile_grounded_state_detects_lost_support(self):
        cells = [PASSABLE] * (20 * 25)
        state, hits = resolve((20, 76, 0, 0, 2, 4, TILE_GROUNDED), cells, (PASSABLE,))
        self.assertEqual(state[-1], AIRBORNE)
        self.assertEqual(hits, SUPPORT_LOST)

        cells[10 * 20 + 5] = 1
        state, hits = resolve((20, 76, 0, 0, 2, 4, TILE_GROUNDED), cells, (PASSABLE, 7))
        self.assertEqual(state[-1], AIRBORNE)
        self.assertEqual(hits, SUPPORT_LOST)


if __name__ == "__main__":
    unittest.main()
