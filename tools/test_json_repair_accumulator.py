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

    append = parser._append_string_span
    snapshot = parser.StringParseState.string_acc.fget

    def tracked_append(state, source, start, end):
        # Retain each state so id reuse cannot combine two snapshot counts.
        counter.states[id(state)] = state
        return append(state, TrackedStr(source), start, end)

    def tracked_snapshot(state):
        counter.snapshots[id(state)] = counter.snapshots.get(id(state), 0) + 1
        counter.snapshot_chars += state.string_length
        return snapshot(state)

    with patch.object(parser, "_append_string_span", tracked_append), patch.object(
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

    def _measure_ordinary_spans(self, size):
        from json_repair.json_parser import JSONParser

        # Two ordinary spans separated by an escape force the repair scanner;
        # all repeated code points, including spaces, are ordinary in this state.
        left = "ordinary é🌲 " * size
        right = "tail " * size
        source = '{"a":"' + left + "\\n" + right + '",}'
        calls = {"characters": 0, "appends": 0}
        original_char = JSONParser.get_char_at
        original_append = parser._append_string_span

        def get_char(self, *args, **kwargs):
            calls["characters"] += 1
            return original_char(self, *args, **kwargs)

        def append_span(*args):
            calls["appends"] += 1
            return original_append(*args)

        with patch.object(JSONParser, "get_char_at", get_char), patch.object(
            parser, "_append_string_span", append_span
        ), count_copies() as counter:
            result = repair_json(source, return_objects=True, skip_json_loads=True)
        self.assertEqual(result, {"a": left + "\n" + right})
        self.assertTrue(counter.snapshots, "the repair accumulator must execute")
        return calls, counter, len(source)

    def _assert_ordinary_span_work(self, calls, counter, length):
        # Parser dispatch and append calls depend on the number of exceptional
        # characters, not the number of ordinary code points. Allow fixed slack
        # for surrounding JSON syntax; none of these limits scales with a span.
        self.assertLessEqual(calls["characters"], 64)
        self.assertLessEqual(calls["appends"], 8)
        # Bounded scalar concatenation is linear too, but copies a 64-character
        # tail repeatedly. This tighter budget distinguishes bulk storage from it.
        self.assertLessEqual(counter.copied_chars, 3 * length + 256)
        self.assertTrue(bounded_work(counter, length), vars(counter))

    def test_ordinary_spans_bound_parser_dispatch_and_copy_work(self):
        for size in (128, 256, 512):
            with self.subTest(size=size):
                calls, counter, length = self._measure_ordinary_spans(size)
                self._assert_ordinary_span_work(calls, counter, length)

    def test_scalar_progression_negative_control_breaks_span_work_budget(self):
        import ast
        import inspect

        # Disable only the ordinary-run branch in the real scanner. Keeping its
        # scalar fallback and all surrounding heuristics proves that correct
        # output alone cannot satisfy the work guard. AST matching avoids a copy
        # of the substantial repair parser or fragile line-number replacements.
        class ScalarProgression(ast.NodeTransformer):
            replacements = 0

            def visit_If(self, node):
                self.generic_visit(node)
                span_calls = [
                    item for statement in node.body for item in ast.walk(statement)
                    if isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
                    and item.func.id == "_append_string_span"
                ]
                scalar_calls = [
                    item for statement in node.orelse for item in ast.walk(statement)
                    if isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
                    and item.func.id == "_append_string_content"
                ]
                if span_calls and scalar_calls:
                    self.replacements += 1
                    return node.orelse
                return node

        tree = ast.parse(inspect.getsource(parser._scan_string_body))
        transform = ScalarProgression()
        tree = ast.fix_missing_locations(transform.visit(tree))
        self.assertEqual(transform.replacements, 1, "identify exactly one ordinary-run branch")
        namespace = dict(vars(parser))
        exec(compile(tree, "<scalar-string-scan-control>", "exec"), namespace)
        with patch.object(parser, "_scan_string_body", namespace["_scan_string_body"]):
            calls, counter, length = self._measure_ordinary_spans(128)
        self.assertGreater(calls["characters"], 64)
        self.assertGreater(calls["appends"], 8)
        self.assertGreater(counter.copied_chars, 3 * length + 256)
        with self.assertRaises(AssertionError):
            self._assert_ordinary_span_work(calls, counter, length)

    def _assert_text_state(self, state, expected):
        self.assertEqual(state.string_acc, expected)
        self.assertEqual(state.string_length, len(expected))
        self.assertEqual(state.string_last, expected[-1:] if expected else "")
        self.assertLess(len(state.string_tail), 64)
        self.assertTrue(all(0 < len(chunk) <= 64 for chunk in state.string_chunks))

        # Independent metadata oracle: saturating brace balance and the latest
        # bracket positions in the complete text, without accumulator helpers.
        balance = 0
        for char in expected:
            balance = max(0, balance + (char == "{") - (char == "}"))
        opening = expected.rfind("[")
        closing = expected.rfind("]")
        bracket_start = opening + 1 if opening > closing else None
        whitespace = False
        if opening >= 0:
            class_end = expected.find("]", opening + 1)
            if class_end < 0:
                class_end = len(expected)
            whitespace = any(char.isspace() for char in expected[opening + 1:class_end])
        self.assertEqual(state.object_value_unmatched_opening_braces, balance)
        self.assertEqual(state.regex_character_class_start, bracket_start)
        self.assertEqual(state.regex_character_class_has_whitespace, whitespace)

    def test_source_range_append_uses_code_point_offsets_and_keeps_snapshots(self):
        for prefix_size in (0, 1, 63, 64, 65):
            for size in (0, 1, 63, 64, 65, 129):
                with self.subTest(prefix_size=prefix_size, size=size):
                    state = parser.StringParseState()
                    prefix = "p" * prefix_size
                    parser._append_string_content(state, prefix)
                    snapshot = state.string_acc
                    content = ("é🌲\ud800" * (size + 1))[:size]
                    source = "🚧é" + content + "unused suffix"
                    # Nonzero Unicode offsets are deliberately not byte offsets.
                    parser._append_string_span(state, source, 2, 2 + size)
                    self.assertEqual(snapshot, prefix)
                    self._assert_text_state(state, prefix + content)
                    parser._append_string_span(state, source, 4, 3)
                    self._assert_text_state(state, prefix + content)

    def test_bulk_content_and_decoded_escapes_preserve_metadata(self):
        fragments = [
            "}{[" + "é" * 63,
            "\u2003🌲]tail }[",
            "\ud800" + "x" * 65 + "\t]{}",
            "[[plain]tail\n",
            "[next\u00a0class",
            "",
        ]
        state = parser.StringParseState()
        expected = ""
        for fragment in fragments:
            parser._append_string_content(state, fragment)
            expected += fragment
            self._assert_text_state(state, expected)

        for width in (63, 64, 65, 127, 128, 129):
            for seed in ("{[", "}{", "]["):
                for replacement in ("", "{\u2003[é", "]}", "\ud800\\"):
                    with self.subTest(width=width, seed=seed, replacement=replacement):
                        state = parser.StringParseState()
                        prefix = seed + "x" * (width - len(seed))
                        parser._append_string_content(state, prefix)
                        snapshot = state.string_acc
                        parser._append_string_content(state, "\\")
                        escaped_snapshot = state.string_acc
                        parser._replace_last_escape(state, replacement)
                        self.assertEqual(snapshot, prefix)
                        self.assertEqual(escaped_snapshot, prefix + "\\")
                        self._assert_text_state(state, prefix + replacement)


if __name__ == "__main__":
    unittest.main()
