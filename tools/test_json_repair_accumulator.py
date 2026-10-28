"""Semantic and deterministic copying controls for the JSON-repair accumulator.

The counter measures lengths of concat/slice results and explicit snapshots in
hosted Python. It is a logical copied-code-point model, not native allocation
bytes, GC counts or a substitute for an end-to-end performance measurement.
"""
from contextlib import contextmanager
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PORTS = Path(__file__).resolve().parents[1] / "ports"
sys.path.insert(0, str(PORTS))
try:
    parser = importlib.import_module("json_repair.parse_string")
    from json_repair import repair_json
finally:
    sys.path.pop(0)


class CopyCounter:
    def __init__(self):
        self.concat_chars = 0
        self.slice_chars = 0
        self.snapshot_chars = 0
        self.largest_piece_copy = 0
        self.snapshots = {}
        self.states = {}

    @property
    def copied_chars(self):
        return self.concat_chars + self.slice_chars + self.snapshot_chars

    def piece(self, kind, length):
        self.largest_piece_copy = max(self.largest_piece_copy, length)
        if kind == "concat":
            self.concat_chars += length
        else:
            self.slice_chars += length


@contextmanager
def count_copies():
    counter = CopyCounter()

    class TrackedStr(str):
        def __add__(self, other):
            value = str.__add__(self, other)
            counter.piece("concat", len(value))
            return TrackedStr(value)

        def __radd__(self, other):
            value = str.__add__(other, self)
            counter.piece("concat", len(value))
            return TrackedStr(value)

        def __getitem__(self, key):
            value = str.__getitem__(self, key)
            if isinstance(key, slice):
                counter.piece("slice", len(value))
            return TrackedStr(value)

        def __iter__(self):
            for char in str.__iter__(self):
                yield TrackedStr(char)

    append = parser._append_string_content
    snapshot = parser.StringParseState.string_acc.fget

    def tracked_append(state, content):
        # Retain each state so id reuse cannot combine two snapshot counts.
        counter.states[id(state)] = state
        return append(state, TrackedStr(content))

    def tracked_snapshot(state):
        counter.snapshots[id(state)] = counter.snapshots.get(id(state), 0) + 1
        counter.snapshot_chars += state.string_length
        return snapshot(state)

    with patch.object(parser, "_append_string_content", tracked_append), patch.object(
        parser.StringParseState, "string_acc", property(tracked_snapshot)
    ):
        yield counter


def bounded_work(counter, input_length):
    # Bound every growing-prefix operation and the total work independently.
    # The fixed 64 is deliberate: silently lifting the chunk bound must not
    # weaken the regression test along with the implementation.
    return (counter.largest_piece_copy <= 64
            and counter.copied_chars <= 256 * input_length
            and all(count <= 1 for count in counter.snapshots.values()))


class JsonRepairAccumulatorTests(unittest.TestCase):
    def measure(self, size, fragment="x\\n", expected_fragment="x\n"):
        source = '{"a":"' + fragment * size + 'end",}'
        with count_copies() as counter:
            result = repair_json(source, return_objects=True)
        self.assertEqual(result, {"a": expected_fragment * size + "end"})
        self.assertTrue(counter.snapshots, "the repair accumulator must execute")
        return counter, len(source)

    def test_escape_copy_work_scales_with_input_not_prefix(self):
        previous = None
        for size in (128, 256, 512):
            with self.subTest(size=size):
                counter, length = self.measure(size)
                self.assertTrue(bounded_work(counter, length), vars(counter))
                if previous is not None:
                    # Exact cycles differ at a chunk boundary; permit a fixed
                    # chunk's worth of work, rather than a timing tolerance.
                    self.assertLessEqual(counter.copied_chars, 2 * previous + 256)
                previous = counter.copied_chars

    def test_unicode_and_surrogates_have_code_point_bounds(self):
        for fragment, expected in (("é🌲\\n", "é🌲\n"), ("\\ud800\\t", "\ud800\t")):
            with self.subTest(fragment=fragment):
                counter, length = self.measure(256, fragment, expected)
                self.assertTrue(bounded_work(counter, length), vars(counter))

    def test_regex_tail_quotes_do_not_materialize_prefixes(self):
        for gap in ("", "\u2003"):
            source = '{"a":"[' + "é" * 257 + gap + '\"x\"y]tail",}'
            expected = repair_json(source, return_objects=True, skip_json_loads=True)
            with count_copies() as counter:
                result = repair_json(source, return_objects=True, skip_json_loads=True)
            self.assertEqual(result, expected)
            self.assertTrue(counter.snapshots)
            self.assertTrue(bounded_work(counter, len(source)), vars(counter))

    def test_unbounded_tail_negative_control_breaks_copy_budget(self):
        # This reproduces the old growing-prefix strategy inside the actual
        # parser. The complete answer still matches, but the copy guard fails.
        with patch.object(parser, "STRING_CHUNK_SIZE", 1 << 30):
            counter, length = self.measure(512)
        self.assertGreater(counter.largest_piece_copy, 64)
        self.assertGreater(counter.copied_chars, 256 * length)
        self.assertFalse(bounded_work(counter, length))

    def test_extra_snapshots_negative_control_breaks_budget(self):
        original = parser._append_string_content

        def flatten_after_append(state, content):
            original(state, content)
            _ = state.string_acc

        with patch.object(parser, "_append_string_content", flatten_after_append):
            counter, length = self.measure(128)
        self.assertGreater(max(counter.snapshots.values()), 1)
        self.assertFalse(bounded_work(counter, length))


if __name__ == "__main__":
    unittest.main()
