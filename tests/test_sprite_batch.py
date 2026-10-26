import unittest


CAPTURED = 1


def stable_insert(entries, sprite, buffer, key, capacity):
    if len(entries) >= capacity:
        return False
    slot = 0
    while slot < len(entries) and entries[slot][2] <= key:
        slot += 1
    entries.insert(slot, [sprite, buffer, key, 0])
    return True


def draw_pass(entries, screen, backgrounds):
    if any(entry[3] & CAPTURED for entry in entries):
        return False
    for entry in entries:
        sprite, buffer, _, _ = entry
        backgrounds[buffer] = screen.copy()
        screen.append(sprite)
        entry[3] |= CAPTURED
    return True


def restore_pass(entries, screen, backgrounds):
    for entry in reversed(entries):
        if entry[3] & CAPTURED:
            screen[:] = backgrounds[entry[1]]
            entry[3] &= ~CAPTURED


def storage_fits(base, capacity):
    return capacity > 0 and base + capacity * 6 <= 0xFFFF


class SpriteBatchTests(unittest.TestCase):
    def test_insertion_is_stable_and_sorted(self):
        entries = []
        self.assertTrue(stable_insert(entries, "upper", "bu", 20, 4))
        self.assertTrue(stable_insert(entries, "lower-a", "ba", 10, 4))
        self.assertTrue(stable_insert(entries, "lower-b", "bb", 10, 4))
        self.assertEqual([entry[0] for entry in entries], ["lower-a", "lower-b", "upper"])

    def test_capacity_failure_keeps_entries(self):
        entries = []
        stable_insert(entries, "a", "ba", 1, 1)
        before = [entry.copy() for entry in entries]
        self.assertFalse(stable_insert(entries, "b", "bb", 2, 1))
        self.assertEqual(entries, before)

    def test_reverse_restore_removes_overlapping_layers(self):
        entries = []
        stable_insert(entries, "lower", "bl", 10, 2)
        stable_insert(entries, "upper", "bu", 20, 2)
        screen = ["background"]
        backgrounds = {}
        self.assertTrue(draw_pass(entries, screen, backgrounds))
        self.assertEqual(screen, ["background", "lower", "upper"])
        restore_pass(entries, screen, backgrounds)
        self.assertEqual(screen, ["background"])
        self.assertTrue(all(entry[3] == 0 for entry in entries))

    def test_draw_rejects_double_capture_without_changes(self):
        entries = []
        stable_insert(entries, "sprite", "buffer", 1, 1)
        screen = ["background"]
        backgrounds = {}
        self.assertTrue(draw_pass(entries, screen, backgrounds))
        before = screen.copy()
        self.assertFalse(draw_pass(entries, screen, backgrounds))
        self.assertEqual(screen, before)

    def test_storage_span_must_not_wrap(self):
        self.assertTrue(storage_fits(0x4000, 16))
        self.assertFalse(storage_fits(0xFFF0, 3))
        self.assertFalse(storage_fits(0x4000, 0))


if __name__ == "__main__":
    unittest.main()
