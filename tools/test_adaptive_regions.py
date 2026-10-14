"""Boundary and measurement checks for the profile-selected region experiment."""

import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import adaptive_regions as regions


class OffsetInt(int):
    def __add__(self, other):
        return 1000 + other


class PretendingType(type):
    def __hash__(self):
        return hash(int)

    def __eq__(self, other):
        return other is int


class PretendingInt(OffsetInt, metaclass=PretendingType):
    pass


class MeasurementTests(unittest.TestCase):
    def test_oracle_rejects_equal_numeric_values_with_different_type_tags(self):
        application = mock.Mock(return_value=[("float", 1.0)])
        with self.assertRaisesRegex(RuntimeError, "differs from CPython"):
            regions.checked_run(application, "steady", 1, 1, expected=[("int", 1)])
        application.assert_called_once()

    def test_active_instrumentation_cannot_be_reported_as_application_timing(self):
        for hook in ("getprofile", "gettrace"):
            with self.subTest(hook=hook):
                application = mock.Mock()
                with mock.patch.object(regions.sys, hook, return_value=object()):
                    with self.assertRaisesRegex(RuntimeError, "profiling and tracing disabled"):
                        regions.checked_run(application, "steady", 1, 1, expected=[])
                application.assert_not_called()

    def test_cache_environment_is_restored_after_failed_compilation(self):
        with mock.patch.dict(os.environ, {"PYSTACHY_CACHE": "original-cache"}):
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                with regions.compiler_cache(Path("private-cache")):
                    self.assertEqual(os.environ["PYSTACHY_CACHE"], "private-cache")
                    raise RuntimeError("fixture failure")
            self.assertEqual(os.environ["PYSTACHY_CACHE"], "original-cache")


class StaticBoundaryTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory(prefix="static-region-test-"))
        self.backends = []

        def compile_variant(_source, _compiler, output, name):
            # The real integration smoke checks native compilation and ABI. These
            # tests keep dispatch guards active while controlling native errors.
            (output / f"{name}.abi3.so").write_bytes(b"fixture artifact")
            backend = mock.Mock(side_effect=regions.workloads.numeric_batch)
            self.backends.append(backend)
            return backend

        self.enterContext(mock.patch.object(regions.adaptive, "_compile_variant", side_effect=compile_variant))
        self.entry, self.counts, _sources, _sizes = regions.compile_static_region([], Path(directory))

    def test_held_out_values_preserve_python_without_entering_native(self):
        for value, n in [(True, 4), (2**70, 4), (OffsetInt(2), 4),
                         (math.inf, 4), (math.nan, 4), (3, True), (PretendingInt(2), 4)]:
            with self.subTest(value=value, n=n):
                expected = regions.workloads.numeric_batch(value, n)
                actual = self.entry(value, n)
                self.assertIs(type(actual), type(expected))
                if type(expected) is float and math.isnan(expected):
                    self.assertTrue(math.isnan(actual))
                else:
                    self.assertEqual(actual, expected)
        self.assertEqual(self.counts["native_calls"], 0)
        self.assertEqual(self.counts["fallback_calls"], 7)
        for backend in self.backends:
            backend.assert_not_called()

    def test_intermediate_overflow_replays_python_arbitrary_precision(self):
        for backend in self.backends:
            backend.side_effect = OverflowError("fixture native overflow")
        value = regions.adaptive._I64_MAX
        self.assertEqual(self.entry(value, 2), value + 3)
        self.assertEqual(self.counts, {"native_calls": 0, "fallback_calls": 1, "overflow_replays": 1})
        self.assertEqual(sum(backend.call_count for backend in self.backends), 1)

    def test_rebound_effectful_helper_falls_back_before_native_entry(self):
        seen = []

        def replacement(value, index):
            seen.append((value, index))
            return value + 10

        with mock.patch.object(regions.workloads, "numeric_step", replacement):
            self.assertEqual(self.entry(3, 2), 23)
        self.assertEqual(seen, [(3, 0), (13, 1)])
        self.assertEqual(self.counts["fallback_calls"], 1)
        for backend in self.backends:
            backend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
