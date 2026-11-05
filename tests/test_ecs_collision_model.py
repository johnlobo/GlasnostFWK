import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ecs_collision_model as model  # noqa: E402

E, S, X = model.ENTER, model.STAY, model.EXIT


class CollisionModelTests(unittest.TestCase):
    """The expectations below were derived by hand from ABI 9.1, not from the model."""

    @classmethod
    def setUpClass(cls):
        cls.records = model.simulate()

    def events(self, step):
        return self.records[step].events

    def test_parked_entities_do_not_touch(self):
        self.assertEqual(self.events(0), [])

    def test_enter_then_stay(self):
        self.assertEqual(self.events(1), [(0, 1, E)])
        self.assertEqual(self.events(2), [(0, 1, S)])

    def test_scan_order_enter_stay_then_exit_in_previous_order(self):
        self.assertEqual(self.events(3), [(0, 1, S), (0, 2, E), (1, 2, E)])
        self.assertEqual(self.events(4), [(1, 2, S), (0, 1, X), (0, 2, X)])

    def test_overlap_is_strict(self):
        self.assertEqual(self.events(5), [(1, 2, S)])  # A3 only touches an edge
        self.assertEqual(self.events(6), [(1, 2, S), (1, 3, E), (2, 3, E)])

    def test_disabled_entity_exits_and_reenters(self):
        self.assertEqual(self.events(7), [(1, 3, S), (1, 2, X), (2, 3, X)])
        self.assertEqual(self.events(8), [(1, 2, E), (1, 3, S), (2, 3, E)])

    def test_callback_destroys_b_once_and_slot_exits_as_free(self):
        self.assertEqual(self.events(9), [(1, 2, S), (1, 3, X), (2, 3, X)])
        self.assertEqual(self.events(10), [(1, 2, S), (1, 3, E), (2, 3, E)])
        self.assertEqual(self.events(11), [(1, 2, S), (1, 3, X), (2, 3, X)])

    def test_two_managers_report_both_role_pair_once(self):
        self.assertEqual(self.events(12), [])
        self.assertEqual(self.events(13), [(1, 5, E)])
        self.assertEqual(self.events(14), [(0, 4, E), (1, 5, S)])
        self.assertEqual(self.events(15), [(0, 4, S), (2, 6, E), (1, 5, X)])
        self.assertEqual(self.events(16), [(0, 4, S), (2, 6, X)])

    def test_overflow_keeps_first_events_and_drops_untracked_pairs(self):
        first = self.records[17]
        self.assertEqual(first.events, [(0, 1, E), (0, 2, E)])
        self.assertEqual((first.carry, first.result, first.flags, first.pair_count), (1, 0x0A, 1, 2))
        second = self.records[18]
        self.assertEqual(second.events, [(0, 1, S), (0, 2, S)])
        self.assertEqual((second.carry, second.flags, second.pair_count), (1, 1, 2))
        third = self.records[19]
        self.assertEqual(third.events, [(1, 2, E), (0, 1, X)])
        self.assertEqual((third.carry, third.flags, third.pair_count), (1, 1, 1))
        last = self.records[20]
        self.assertEqual(last.events, [(1, 2, X)])
        self.assertEqual((last.carry, last.result, last.flags, last.pair_count), (0, 0, 0, 0))

    def test_edge_cases_saturation_zero_size_and_errors(self):
        self.assertEqual(self.events(22), [(0, 1, E)])           # x saturates at 255
        self.assertEqual(self.events(23), [(0, 1, X)])           # zero width
        self.assertEqual(self.events(24), [(0, 1, E)])
        self.assertEqual(self.events(25), [(0, 1, X)])           # zero height
        self.assertEqual(self.events(26), [(0, 1, E)])
        self.assertEqual(self.events(28), [(0, 1, E)])           # y saturates at 255
        busy, null = self.records[29], self.records[30]
        self.assertEqual((busy.carry, busy.result, busy.callbacks), (1, 0x06, []))
        self.assertEqual((null.carry, null.result, null.callbacks), (1, 0x01, []))
        self.assertEqual(busy.pair_count, 1)                      # state untouched
        zero, coded = self.records[31], self.records[32]
        self.assertEqual((zero.result, zero.callbacks, zero.pair_count), (0x09, [(X, 0, 1)], 0))
        self.assertEqual((coded.result, coded.callbacks, coded.pair_count), (0x77, [(E, 0, 1)], 1))
        self.assertEqual(self.events(33), [(0, 1, S)])           # abort still committed the pair

    def test_callbacks_are_the_kept_events_in_order(self):
        for record in self.records:
            if record.result in (0, 0x0A):
                self.assertEqual(record.callbacks, [(k, a, b) for a, b, k in record.events])

    def test_pair_membership_is_never_duplicated_or_reversed(self):
        for step, record in zip(model.SCENARIO, self.records):
            seen = set()
            for a, b, _ in record.events:
                if step.mode != model.MODE_INTER:
                    self.assertLess(a, b)
                self.assertNotIn((a, b, _), seen)
                seen.add((a, b, _))

    def test_expected_log_layout(self):
        pointers = [0x1000 + 0x40 * i for i in range(7)]
        log = model.expected_log(pointers, 0x2000, 0x2100)
        # step 0: six header bytes plus a zero callback count
        self.assertEqual(log[:7], bytes((0, 0, 0, 0, 0, 0, 0)))
        # step 1 starts at 7: one ENTER(A0,A1) and its callback
        record = log[7:]
        self.assertEqual(record[:6], bytes((1, 0, 0, 0, 1, 1)))
        self.assertEqual(record[6:11], bytes((0x00, 0x10, 0x40, 0x10, 1)))
        self.assertEqual(record[11], 1)
        self.assertEqual(record[12:21], bytes((1, 0x00, 0x10, 0x40, 0x10, 0x00, 0x20, 0x00, 0x20)))
        decoded = model.describe_log(log, pointers)
        self.assertEqual(len(decoded), len(model.SCENARIO))
        self.assertIn("ENTER(A0,A1)", decoded[1])

    def test_committed_scenario_include_is_current(self):
        committed = (ROOT / "examples/ecscollision/scenario.inc").read_text()
        self.assertEqual(committed, model.render_include())


if __name__ == "__main__":
    unittest.main()
