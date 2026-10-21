"""Controls for measurement; do not certify today's eight-field result as correct."""
import unittest
from unittest.mock import patch

from compiler_state_nested_probe import Gen, has_violations, measure


class NestedBoundaryProbeTests(unittest.TestCase):
    def test_established_frame_fields_at_increasing_depth(self):
        for depth in (1, 2, 3):
            with self.subTest(depth=depth):
                report = measure(depth, ("line", "ltype"))
                self.assertEqual([event["level"] for event in report["boundaries"]], list(range(1, depth + 1)))
                self.assertFalse(has_violations([report]))

    def test_entry_leak_is_detected(self):
        original = Gen.enter

        def broken(g, f, body):
            original(g, f, body)
            g.line = 999

        with patch.object(Gen, "enter", broken):
            report = measure(2, ("line",))
        self.assertTrue(has_violations([report]))
        for event in report["boundaries"]:
            self.assertEqual(event["entry_leaks"], ["line"])
            self.assertEqual(event["caller_restore_changes"], [])

    def test_missing_restore_is_detected(self):
        original = Gen.restore

        def broken(g, frame):
            callee_line = g.line
            original(g, frame)
            g.line = callee_line

        with patch.object(Gen, "restore", broken):
            report = measure(3, ("line",))
        self.assertTrue(has_violations([report]))
        for event in report["boundaries"]:
            self.assertEqual(event["entry_leaks"], [])
            self.assertEqual(event["caller_restore_changes"], ["line"])

    def test_equal_value_replacement_and_in_place_mutation_are_detected(self):
        original = Gen.restore
        for replace in (False, True):
            with self.subTest(replace=replace):
                def broken(g, frame, replace=replace):
                    original(g, frame)
                    if replace:
                        g.ltype = dict(g.ltype)
                    else:
                        g.ltype["marker"] = "changed"

                with patch.object(Gen, "restore", broken):
                    report = measure(2, ("ltype",))
                self.assertTrue(has_violations([report]))
                for event in report["boundaries"]:
                    self.assertEqual(event["caller_restore_changes"], ["ltype"])

    def test_depth_is_bounded(self):
        for depth in (0, 9):
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                measure(depth)

    def test_missing_attributes_are_reported(self):
        enter = Gen.enter
        restore = Gen.restore

        def broken_enter(g, f, body):
            enter(g, f, body)
            del g.line

        def broken_restore(g, frame):
            restore(g, frame)
            del g.ltype

        with patch.object(Gen, "enter", broken_enter), patch.object(Gen, "restore", broken_restore):
            report = measure(2, ("line", "ltype"))
        self.assertTrue(has_violations([report]))
        for event in report["boundaries"]:
            self.assertEqual(event["entry_leaks"], ["line"])
            self.assertEqual(event["caller_restore_changes"], ["ltype"])


if __name__ == "__main__":
    unittest.main()
