"""Guarded scalar specialization, including native execution when LLVM is available."""
import builtins
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import textwrap
import threading
import types
import unittest
from unittest import mock

import adaptive


ROOT = Path(__file__).resolve().parents[1]


def scalar_add(a, b):
    return a + b


def scalar_subtract(a, b):
    return a - b


def scalar_divide(a, b):
    return a / b


def negative_zero(a):
    return -0.0


def integer_constant(a):
    return 1


def range_sum(n):
    total = 0
    for i in range(n):
        total = total + i
    return total


def region_step(a, b):
    return (a + b) % 97


def region_adjust(a, b):
    return region_step(a, b) + 1


def region_batch(a, n):
    total = a
    for i in range(n):
        total = region_adjust(total, i)
    return total


def recursive_helper(a):
    if a > 0:
        return recursive_helper(a - 1)
    return 0


def helper_value(a):
    other = region_step
    return other(a, a)


def helper_keyword(a):
    return region_step(a=a, b=2)


def helper_shadowed(region_step, b):
    return region_step(b, b)


def effectful_caller(a):
    return side_effect(a)


EFFECTS = []


def side_effect(a):
    EFFECTS.append(a)
    return a + 1


class OffsetInt(int):
    def __add__(self, other):
        return 9001


class DispatchTests(unittest.TestCase):
    def setUp(self):
        # These tests replace native compilation, so exercise its guards under a
        # supported host even when the test runner itself is macOS or Python 3.11.
        self.enterContext(mock.patch.object(adaptive.sys, "platform", "linux"))
        self.enterContext(mock.patch.object(adaptive.sys, "version_info", (3, 12, 0, "final", 0)))
        self.enterContext(mock.patch.object(adaptive.platform, "machine", return_value="x86_64"))
        self.enterContext(mock.patch.object(adaptive.sysconfig, "get_config_var", return_value=None))

    def specialize(self, function=scalar_add, **options):
        backend = mock.Mock(side_effect=function)
        patcher = mock.patch.object(adaptive, "_compile_variant", return_value=backend)
        compiler = patcher.start()
        self.addCleanup(patcher.stop)
        wrapped = adaptive.specialize(warmup=2, **options)(function)
        return wrapped, backend, compiler

    def prime(self, wrapped, compiler):
        for a, b in [(1, 2), (2, 3), (3, 4)]:
            self.assertEqual(wrapped(a, b), a + b)
        compiler.assert_called_once()
        self.assertIn("int,int", wrapped.adaptive_stats()["variants"])

    def test_observed_types_create_two_native_variants(self):
        wrapped, backend, compiler = self.specialize()
        self.prime(wrapped, compiler)
        for a, b in [(1.5, 2.5), (2.5, 3.5), (3.5, 4.5)]:
            self.assertEqual(wrapped(a, b), a + b)
        self.assertEqual(compiler.call_count, 2)
        self.assertEqual(set(wrapped.adaptive_stats()["variants"]), {"int,int", "float,float"})
        self.assertGreaterEqual(backend.call_count, 2)
        self.assertEqual(wrapped(10, 20), 30)
        self.assertEqual(wrapped(0.25, 0.5), 0.75)
        self.assertEqual(compiler.call_count, 2)
        # The public report can be written directly to JSON, including signature keys.
        json.dumps(wrapped.adaptive_stats())

    def test_guard_misses_preserve_python_scalar_semantics(self):
        wrapped, backend, compiler = self.specialize()
        self.prime(wrapped, compiler)
        before = backend.call_count
        for a, b, expected in [(True, False, 1), (OffsetInt(2), 3, 9001),
                               (1 << 80, 3, (1 << 80) + 3)]:
            with self.subTest(a=a, b=b):
                self.assertEqual(wrapped(a, b), expected)
        self.assertEqual(backend.call_count, before)
        compiler.assert_called_once()

    def test_nonfinite_floats_do_not_enter_a_finite_specialization(self):
        wrapped, backend, compiler = self.specialize()
        for a, b in [(1.0, 2.0), (2.0, 3.0), (3.0, 4.0)]:
            self.assertEqual(wrapped(a, b), a + b)
        before = backend.call_count
        self.assertEqual(wrapped(math.inf, 1.0), math.inf)
        self.assertEqual(wrapped(-math.inf, 1.0), -math.inf)
        self.assertTrue(math.isnan(wrapped(math.nan, 1.0)))
        self.assertEqual(backend.call_count, before)
        compiler.assert_called_once()

    def test_overflow_replays_the_pure_python_function(self):
        wrapped, backend, compiler = self.specialize()
        self.prime(wrapped, compiler)
        backend.side_effect = OverflowError("checked native operation overflowed")
        self.assertEqual(wrapped(1 << 62, 1 << 62), 1 << 63)
        self.assertEqual(wrapped.adaptive_stats()["native_errors"].get("OverflowError"), 1)
        compiler.assert_called_once()

    def test_code_replacement_invalidates_compiled_assumptions(self):
        original = types.FunctionType(scalar_add.__code__, dict(scalar_add.__globals__), "scalar_add")
        wrapped, backend, compiler = self.specialize(original)
        self.prime(wrapped, compiler)
        before = backend.call_count
        original.__code__ = scalar_subtract.__code__
        self.assertEqual(wrapped(10, 3), 7)
        self.assertEqual(wrapped(20, 4), 16)
        self.assertEqual(backend.call_count, before)
        compiler.assert_called_once()

    def test_keyword_and_invalid_calls_preserve_python_argument_binding(self):
        wrapped, backend, compiler = self.specialize()
        self.prime(wrapped, compiler)
        before = backend.call_count
        self.assertEqual(wrapped(b=3, a=10), 13)
        self.assertEqual(wrapped(10, b=3), 13)
        for args, kwargs in [((1,), {}), ((1, 2, 3), {}), ((), {"a": 1, "c": 2})]:
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(TypeError) as expected:
                    scalar_add(*args, **kwargs)
                with self.assertRaises(TypeError) as actual:
                    wrapped(*args, **kwargs)
                self.assertEqual(str(actual.exception), str(expected.exception))
        self.assertEqual(backend.call_count, before)
        compiler.assert_called_once()

    def test_shadowed_range_invalidates_compiled_assumptions(self):
        namespace = dict(range_sum.__globals__)
        original = types.FunctionType(range_sum.__code__, namespace, "range_sum")
        wrapped, backend, compiler = self.specialize(original)
        for n in [3, 4, 5]:
            self.assertEqual(wrapped(n), sum(range(n)))
        compiler.assert_called_once()
        before = backend.call_count
        namespace["range"] = lambda _n: [40, 2]
        self.assertEqual(wrapped(5), 42)
        self.assertEqual(backend.call_count, before)
        compiler.assert_called_once()

    def test_changed_builtin_range_invalidates_compiled_assumptions(self):
        namespace = {"__builtins__": dict(vars(builtins))}
        original = types.FunctionType(range_sum.__code__, namespace, "range_sum")
        wrapped, backend, compiler = self.specialize(original)
        for n in [3, 4, 5]:
            self.assertEqual(wrapped(n), sum(range(n)))
        compiler.assert_called_once()
        before = backend.call_count
        original.__builtins__["range"] = lambda _n: [40, 2]
        self.assertEqual(wrapped(5), 42)
        self.assertEqual(backend.call_count, before)
        compiler.assert_called_once()

    def test_python_exceptions_do_not_warm_a_signature_and_native_errors_replay(self):
        wrapped, backend, compiler = self.specialize(scalar_divide)
        with self.assertRaisesRegex(ZeroDivisionError, "division by zero"):
            wrapped(1, 0)
        self.assertEqual(wrapped.adaptive_stats()["variants"], [])
        compiler.assert_not_called()
        self.assertEqual(wrapped(2, 2), 1.0)
        compiler.assert_not_called()
        for a in [4, 6]:
            self.assertEqual(wrapped(a, 2), a / 2)
        compiler.assert_called_once()
        backend.side_effect = ZeroDivisionError("native error differs")
        with self.assertRaisesRegex(ZeroDivisionError, "division by zero"):
            wrapped(1, 0)
        self.assertEqual(wrapped.adaptive_stats()["native_errors"].get("ZeroDivisionError"), 1)
        compiler.assert_called_once()

    def test_source_mismatch_never_compiles_a_different_function(self):
        tampered = "def scalar_add(a, b):\n    return a - b\n"
        with mock.patch.object(adaptive.inspect, "getsource", return_value=tampered):
            wrapped, backend, compiler = self.specialize()
        for _ in range(4):
            self.assertEqual(wrapped(10, 3), 13)
        self.assertTrue(wrapped.adaptive_stats()["disabled_reason"])
        compiler.assert_not_called()
        backend.assert_not_called()

    def test_changed_constant_type_or_signed_zero_invalidates_source(self):
        for original, changed in [
            (negative_zero, "def negative_zero(a):\n    return 0.0\n"),
            (integer_constant, "def integer_constant(a):\n    return 1.0\n"),
            (integer_constant, "def integer_constant(a):\n    return True\n"),
        ]:
            with self.subTest(function=original.__name__, changed=changed):
                with mock.patch.object(adaptive.inspect, "getsource", return_value=changed):
                    wrapped, backend, compiler = self.specialize(original)
                for _ in range(3):
                    result = wrapped(1)
                    expected = original(1)
                    self.assertIs(type(result), type(expected))
                    self.assertEqual(result, expected)
                    if type(result) is float:
                        self.assertEqual(math.copysign(1, result), math.copysign(1, expected))
                self.assertTrue(wrapped.adaptive_stats()["disabled_reason"])
                compiler.assert_not_called()
                backend.assert_not_called()

    def test_unsupported_effectful_function_runs_once_per_call(self):
        wrapped, backend, compiler = self.specialize(side_effect)
        EFFECTS.clear()
        self.addCleanup(EFFECTS.clear)
        for value in range(4):
            self.assertEqual(wrapped(value), value + 1)
        self.assertEqual(EFFECTS, [0, 1, 2, 3])
        self.assertTrue(wrapped.adaptive_stats()["disabled_reason"])
        compiler.assert_not_called()
        backend.assert_not_called()

    def test_variant_budget_bounds_compilation_for_new_signatures(self):
        wrapped, backend, compiler = self.specialize(max_variants=1)
        self.prime(wrapped, compiler)
        before = backend.call_count
        for _ in range(5):
            self.assertEqual(wrapped(1.5, 2.5), 4.0)
        self.assertEqual(backend.call_count, before)
        self.assertEqual(wrapped.adaptive_stats()["variants"], ["int,int"])
        compiler.assert_called_once()

    def test_failed_compilation_is_attempted_once_and_consumes_budget(self):
        wrapped, backend, compiler = self.specialize(max_variants=1)
        compiler.side_effect = RuntimeError("fixture compiler failed")
        for _ in range(5):
            self.assertEqual(wrapped(1, 2), 3)
        for _ in range(5):
            self.assertEqual(wrapped(1.5, 2.5), 4.0)
        compiler.assert_called_once()
        backend.assert_not_called()
        self.assertEqual(wrapped.adaptive_stats()["compile_failures"], 1)
        self.assertEqual(wrapped.adaptive_stats()["variants"], [])

    def test_rare_early_signatures_do_not_pin_the_profile_table(self):
        wrapped, _backend, compiler = self.specialize(max_variants=1, max_profiles=2)
        self.assertEqual(wrapped(1, 2.0), 3.0)
        self.assertEqual(wrapped(1.0, 2), 3.0)
        compiler.assert_not_called()
        for a, b in [(1, 2), (2, 3), (3, 4)]:
            self.assertEqual(wrapped(a, b), a + b)
        stats = wrapped.adaptive_stats()
        compiler.assert_called_once()
        self.assertEqual(stats["variants"], ["int,int"])
        self.assertEqual(stats["profile_limit"], 2)
        self.assertEqual(len(stats["signatures"]), 2)
        self.assertEqual(stats["profile_evictions"], 1)
        self.assertEqual(len(wrapped._warmups), 2)

    def test_profile_eviction_cannot_replenish_failed_compilation_budget(self):
        wrapped, _backend, compiler = self.specialize(max_variants=1, max_profiles=1)
        compiler.side_effect = RuntimeError("fixture compiler failed")
        for _ in range(3):
            wrapped(1, 2)
        for args in [(1.0, 2.0), (1, 2.0), (1, 2)]:
            for _ in range(3):
                wrapped(*args)
        compiler.assert_called_once()
        self.assertEqual(wrapped.adaptive_stats()["attempted"], ["int,int"])
        self.assertEqual(len(wrapped._profiles), 1)
        self.assertEqual(len(wrapped._warmups), 1)

    def region(self):
        # Each member retains its own globals dict: guards must consult the
        # namespace used by that caller, including transitive helper bindings.
        step = types.FunctionType(region_step.__code__, dict(region_step.__globals__), "region_step")
        adjust_globals = dict(region_adjust.__globals__, region_step=step)
        adjust = types.FunctionType(region_adjust.__code__, adjust_globals, "region_adjust")
        batch_globals = dict(region_batch.__globals__, region_adjust=adjust)
        batch = types.FunctionType(region_batch.__code__, batch_globals, "region_batch")
        helpers = {"region_step": step, "region_adjust": adjust}
        return batch, helpers

    def test_region_clones_private_helpers_and_compiles_one_native_entry(self):
        original, helpers = self.region()
        wrapped, backend, compiler = self.specialize(original, helpers=helpers)
        for _ in range(3):
            self.assertEqual(wrapped(2, 10), original(2, 10))
        compiler.assert_called_once()
        self.assertEqual(backend.call_count, 1)
        stats = wrapped.adaptive_stats()
        self.assertEqual(stats["region_functions"], 3)
        source = stats["sources"]["int,int"]
        self.assertIn("def kernel(a: int, n: int) -> int:", source)
        self.assertEqual(source.count("@export"), 1)
        self.assertEqual(source.count("def _adaptive_helper_"), 2)
        self.assertNotIn("region_step(", source)
        self.assertNotIn("region_adjust(", source)
        self.assertEqual(stats["source_bytes"]["int,int"], len(source.encode()))
        json.dumps(stats)

    def test_transitive_region_binding_and_code_changes_fall_back(self):
        for mutation in ["entry_binding", "helper_binding", "helper_code", "entry_range", "helper_range"]:
            with self.subTest(mutation=mutation):
                original, helpers = self.region()
                if mutation == "helper_range":
                    helper = types.FunctionType(range_sum.__code__, dict(range_sum.__globals__), "range_sum")
                    # A caller with a helper that itself uses range exercises a
                    # binding absent from the entry's own namespace.
                    source = "def region_entry(a, b):\n    return range_sum(a) + b\n"
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / "caller.py"
                        path.write_text(source)
                        namespace = {"range_sum": helper}
                        exec(compile(source, str(path), "exec"), namespace)
                        original = namespace["region_entry"]
                        wrapped, backend, compiler = self.specialize(original, helpers={"range_sum": helper})
                        for _ in range(3):
                            self.assertEqual(wrapped(2, 10), original(2, 10))
                    helper.__globals__["range"] = lambda _n: [40, 2]
                else:
                    wrapped, backend, compiler = self.specialize(original, helpers=helpers)
                    for _ in range(3):
                        self.assertEqual(wrapped(2, 10), original(2, 10))
                    if mutation == "entry_binding":
                        original.__globals__["region_adjust"] = lambda a, b: 7
                    elif mutation == "helper_binding":
                        helpers["region_adjust"].__globals__["region_step"] = lambda a, b: 7
                    elif mutation == "helper_code":
                        helpers["region_step"].__code__ = scalar_subtract.__code__
                    elif mutation == "entry_range":
                        original.__globals__["range"] = lambda _n: [2, 3]
                before = backend.call_count
                self.assertEqual(wrapped(2, 10), original(2, 10))
                self.assertEqual(backend.call_count, before)
                compiler.assert_called_once()

    def test_region_rejects_recursion_callbacks_shadowing_and_effects(self):
        for function, helpers in [
            (recursive_helper, {"recursive_helper": recursive_helper}),
            (helper_value, {"region_step": region_step}),
            (helper_keyword, {"region_step": region_step}),
            (helper_shadowed, {"region_step": region_step}),
            (effectful_caller, {"side_effect": side_effect}),
        ]:
            with self.subTest(function=function.__name__):
                wrapped, _backend, compiler = self.specialize(function, helpers=helpers)
                self.assertTrue(wrapped.adaptive_stats()["disabled_reason"])
                compiler.assert_not_called()

    def test_region_rejects_an_unlisted_or_mismatched_helper(self):
        for helpers in [{}, {"region_adjust": region_step}]:
            with self.subTest(helpers=helpers):
                wrapped, _backend, compiler = self.specialize(region_batch, helpers=helpers)
                for _ in range(3):
                    self.assertEqual(wrapped(2, 10), region_batch(2, 10))
                self.assertTrue(wrapped.adaptive_stats()["disabled_reason"])
                compiler.assert_not_called()

    def test_native_error_replay_remains_safe_across_the_pure_region(self):
        original, helpers = self.region()
        wrapped, backend, compiler = self.specialize(original, helpers=helpers)
        for _ in range(3):
            wrapped(2, 10)
        backend.side_effect = OverflowError("helper overflowed")
        self.assertEqual(wrapped(2, 10), original(2, 10))
        self.assertEqual(wrapped.adaptive_stats()["native_errors"], {"OverflowError": 1})
        compiler.assert_called_once()

    def test_non_owner_thread_uses_python_without_entering_native_code(self):
        wrapped, backend, compiler = self.specialize()
        self.prime(wrapped, compiler)
        before = backend.call_count
        results = []
        errors = []

        def worker():
            try:
                results.append(wrapped(10, 20))
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(results, [30])
        self.assertEqual(backend.call_count, before)
        compiler.assert_called_once()

    def test_instance_method_retains_binding_and_effectful_python_fallback(self):
        with mock.patch.object(adaptive, "_compile_variant") as compiler:
            class Receiver:
                def __init__(self):
                    self.values = []

                @adaptive.specialize(warmup=1)
                def record(self, value):
                    self.values.append(value)
                    return value + 1

            receiver = Receiver()
            self.assertIs(receiver.record.__self__, receiver)
            self.assertEqual(receiver.record(3), 4)
            self.assertEqual(receiver.record(5), 6)
            self.assertEqual(Receiver.record(receiver, 7), 8)
            self.assertEqual(receiver.values, [3, 5, 7])
            self.assertTrue(Receiver.record.adaptive_stats()["disabled_reason"])
            compiler.assert_not_called()

    def test_active_tracing_and_profiling_preserve_original_function_events(self):
        wrapped, backend, compiler = self.specialize()
        self.prime(wrapped, compiler)
        for setter, getter in [(sys.settrace, sys.gettrace), (sys.setprofile, sys.getprofile)]:
            with self.subTest(hook=setter.__name__):
                events = []
                before = backend.call_count

                def hook(frame, event, _arg, events=events):
                    if frame.f_code is scalar_add.__code__:
                        events.append(event)
                    return hook

                previous = getter()
                try:
                    setter(hook)
                    result = wrapped(10, 20)
                finally:
                    setter(previous)
                self.assertEqual(result, 30)
                self.assertIn("call", events)
                self.assertIn("return", events)
                self.assertEqual(backend.call_count, before)
        compiler.assert_called_once()

    def test_future_annotations_source_remains_eligible(self):
        source = "from __future__ import annotations\n\ndef future_add(a, b):\n    return a + b\n"
        with tempfile.TemporaryDirectory(prefix="pystachy-adaptive-source-") as directory:
            path = Path(directory) / "future_fixture.py"
            path.write_text(source)
            namespace = {}
            exec(compile(source, str(path), "exec"), namespace)
            wrapped, _backend, compiler = self.specialize(namespace["future_add"])
            self.prime(wrapped, compiler)
            self.assertEqual(wrapped(10, 20), 30)
            self.assertFalse(wrapped.adaptive_stats()["disabled_reason"])


class NativeTests(unittest.TestCase):
    @classmethod
    def unavailable(cls, reason):
        if os.environ.get("PYSTACHY_ADAPTIVE_REQUIRE_NATIVE") == "1":
            raise RuntimeError(reason)
        raise unittest.SkipTest(reason)

    @classmethod
    def setUpClass(cls):
        if sys.implementation.name != "cpython":
            cls.unavailable("native extensions require CPython")
        if sys.version_info < (3, 12):
            cls.unavailable("native extensions require CPython 3.12+")
        if sysconfig.get_config_var("Py_GIL_DISABLED"):
            cls.unavailable("native extensions require a conventional GIL build")
        if sys.platform != "linux" or platform.machine() not in ("x86_64", "AMD64"):
            cls.unavailable("native extensions are currently tested on Linux x86-64")
        discovery = subprocess.run(
            [sys.executable, "-c", "import pystachy; print(pystachy.llvm_dir())"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        if discovery.returncode:
            raise RuntimeError(discovery.stderr)
        llvm = discovery.stdout.strip()
        for tool in ("clang", "opt", "llvm-link", "llvm-as"):
            path = str(Path(llvm) / tool) if llvm else shutil.which(tool)
            if not path or not os.access(path, os.X_OK):
                cls.unavailable("LLVM toolchain unavailable: " + tool)

    def test_native_int_float_dispatch_and_intermediate_overflow_replay(self):
        # Isolation catches extension-loader and ABI errors; the fixture lives in a
        # real source file so inspection exercises the same path as a user module.
        source = textwrap.dedent("""\
            from __future__ import annotations
            import json
            import sys
            sys.path.insert(0, sys.argv[1])
            from tools.adaptive import specialize

            @specialize(warmup=2, max_variants=2)
            def polynomial(a, b):
                result = a * a
                return result + b

            @specialize(warmup=2)
            def overflow_branch(a):
                value = a * 2
                if value < 0:
                    return 1
                return 0

            @specialize(warmup=2)
            def mixed_branch(a):
                if a > 0:
                    return 1
                return 0.5

            @specialize(warmup=2)
            def mixed_or(a):
                return a or 0.5

            @specialize(warmup=2)
            def mixed_if_expression(a):
                return a if a else 0.5

            @specialize(warmup=2, max_variants=2)
            def compare_numbers(a, b):
                if a == b:
                    return 0
                if a > b:
                    return 1
                return -1

            def region_step(a, b):
                return (a + b + 1) % 97

            def region_adjust(a, b):
                return region_step(a, b) + 1

            @specialize(warmup=2, helpers={'region_adjust': region_adjust,
                                         'region_step': region_step})
            def region_batch(a, n):
                total = a
                for i in range(n):
                    total = region_adjust(total, i)
                return total

            values = []
            for a, b in [(2, 3), (3, 4), (4, 5), (5, 6),
                         (2.0, 0.5), (3.0, 0.5), (4.0, 0.5), (5.0, 0.5)]:
                values.append(polynomial(a, b))
            for a in [1, 2, 3]:
                assert overflow_branch(a) == 0
            assert overflow_branch(1 << 62) == 0
            assert polynomial(1 << 80, 1) == (1 << 160) + 1
            assert polynomial(True, False) == 1
            mixed_reports = []
            for function in [mixed_branch, mixed_or, mixed_if_expression]:
                for value in [1, 2, 3, 0, -1]:
                    expected = function.__wrapped__(value)
                    actual = function(value)
                    assert type(actual) is type(expected), (function.__name__, value, actual, expected)
                    assert actual == expected, (function.__name__, value, actual, expected)
                mixed_reports.append(function.adaptive_stats())
            comparisons = [(1, 0.5), (2, 0.5), (3, 0.5),
                           (0.5, 1), (0.5, 2), (0.5, 3),
                           ((1 << 53) + 1, float(1 << 53)),
                           (float(1 << 53), (1 << 53) + 1),
                           (-(1 << 53) - 1, float(-(1 << 53))),
                           ((1 << 63) - 1, float(1 << 63)),
                           (float(1 << 63), (1 << 63) - 1),
                           (-(1 << 63), float(-(1 << 63)))]
            for a, b in comparisons:
                expected = compare_numbers.__wrapped__(a, b)
                actual = compare_numbers(a, b)
                assert type(actual) is type(expected)
                assert actual == expected, (a, b, actual, expected)
            for a, n in [(2, 10), (3, 10), (4, 10),
                         (2.5, 10), (3.5, 10), (4.5, 10), (7.5, 30)]:
                expected = region_batch.__wrapped__(a, n)
                actual = region_batch(a, n)
                assert type(actual) is type(expected)
                assert actual == expected, (a, n, actual, expected)
            expected = region_batch.__wrapped__((1 << 63) - 1, 3)
            assert region_batch((1 << 63) - 1, 3) == expected
            before_rebind = region_batch.adaptive_stats()['native_hits']
            region_step = lambda a, b: 7
            assert region_batch(2, 10) == 8
            assert region_batch.adaptive_stats()['native_hits'] == before_rebind
            print(json.dumps({'values': values, 'poly': polynomial.adaptive_stats(),
                              'overflow': overflow_branch.adaptive_stats(),
                              'mixed': mixed_reports,
                              'region': region_batch.adaptive_stats(),
                              'comparisons': compare_numbers.adaptive_stats()}))
            """)
        with tempfile.TemporaryDirectory(prefix="pystachy-adaptive-test-") as directory:
            fixture = Path(directory) / "native_fixture.py"
            fixture.write_text(source)
            environment = dict(os.environ, PYSTACHY_HOME=str(ROOT),
                               PYSTACHY_CACHE=str(Path(directory) / "cache"))
            result = subprocess.run([sys.executable, "-W", "error::ResourceWarning", str(fixture), str(ROOT)], cwd=ROOT,
                                    env=environment, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["values"], [7, 13, 21, 31, 4.5, 9.5, 16.5, 25.5])
        self.assertEqual(set(report["poly"]["variants"]), {"int,int", "float,float"})
        self.assertGreaterEqual(report["poly"]["native_hits"], 4)
        self.assertEqual(report["poly"]["compile_failures"], 0, report["poly"])
        self.assertIn("int", report["overflow"]["variants"])
        self.assertGreater(report["overflow"]["native_hits"], 0)
        self.assertEqual(report["overflow"]["native_errors"].get("OverflowError"), 1)
        self.assertEqual(report["overflow"]["compile_failures"], 0, report["overflow"])
        for mixed in report["mixed"]:
            if mixed["variants"]:
                self.assertGreater(mixed["native_hits"], 0)
        self.assertEqual(set(report["comparisons"]["variants"]), {"int,float", "float,int"})
        self.assertEqual(report["comparisons"]["compile_failures"], 0, report["comparisons"])
        self.assertGreaterEqual(report["comparisons"]["native_hits"], 6)
        region = report["region"]
        self.assertEqual(set(region["variants"]), {"int,int", "float,int"})
        self.assertEqual(region["region_functions"], 3)
        self.assertEqual(region["compile_failures"], 0, region)
        self.assertGreaterEqual(region["native_hits"], 3)
        self.assertEqual(region["native_errors"].get("OverflowError"), 1)
        self.assertTrue(all(size > 0 for size in region["native_bytes"].values()))


if __name__ == "__main__":
    unittest.main()
