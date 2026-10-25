import unittest


def platform_steps(state, config, count):
    x, y, vx, vy, width, height, airborne = state
    world_width, ground_y, gravity, max_fall = config
    for _ in range(count):
        x = max(0, min(world_width - width, x + vx))
        if x in {0, world_width - width}:
            vx = 0
        if airborne:
            vy = min(max_fall, vy + gravity)
        elif vy < 0:
            airborne = 1
        else:
            vy = 0
        if vy:
            y += vy
            if y < 0:
                y = 0
                vy = 0
            elif y + height - 1 >= ground_y:
                y = ground_y - height + 1
                vy = 0
                airborne = 0
    return x, y, vx, vy, width, height, airborne


def physics_8_8_steps(state, bounds, friction, count):
    x, y, vx, vy, remainder = state
    min_x, max_x, min_y, max_y = bounds
    for _ in range(count):
        ax, ay = abs(vx), abs(vy)
        if ax or ay:
            if ax >= ay:
                major, minor, major_axis = ax, ay, "x"
            else:
                major, minor, major_axis = ay, ax, "y"
            share = (
                friction * 256
                if major == minor
                else (minor * 256 // major) * friction
            ) + remainder
            remainder = share & 0xFF
            minor = max(0, minor - (share >> 8))
            major -= friction
            if major <= 0:
                major = minor = remainder = 0
            if major_axis == "x":
                ax, ay = major, minor
            else:
                ay, ax = major, minor
            vx = -ax if vx < 0 else ax
            vy = -ay if vy < 0 else ay
        x += vx
        if x < min_x * 256:
            x, vx = min_x * 256, -vx
        elif x >= (max_x + 1) * 256:
            x, vx = max_x * 256, -vx
        y += vy
        if y < min_y * 256:
            y, vy = min_y * 256, -vy
        elif y >= (max_y + 1) * 256:
            y, vy = max_y * 256, -vy
    return x, y, vx, vy, remainder


class PhysicsProfileTests(unittest.TestCase):
    def test_platform_sample_lands_and_clamps_horizontally(self):
        self.assertEqual(
            platform_steps((75, 150, 3, -8, 4, 8, 1), (80, 199, 1, 8), 48),
            (76, 192, 0, 0, 4, 8, 0),
        )

    def test_fixed_point_sample_preserves_vector_friction_and_bounces(self):
        self.assertEqual(
            physics_8_8_steps(
                (78 * 256, 70 * 256, 2 * 256, 1 * 256, 0),
                (0, 79, 0, 199),
                4,
                64,
            ),
            (0x0BDC, 0x75C0, 0x0100, 0x0080, 0),
        )


if __name__ == "__main__":
    unittest.main()
