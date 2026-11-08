"""Call-binding, conversion and aliasing controls for the CPython FFI twin."""

import importlib.util
import inspect
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ffi_twin_under_test", ROOT / "tools/rt_cpython/ffi.py")
ffi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ffi)


class FFITwinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shlex.split(os.environ.get("CC", "cc"))
        if not compiler or not shutil.which(compiler[0]):
            raise unittest.SkipTest("a C compiler is required for actual FFI calls")
        cls.temporary = tempfile.TemporaryDirectory(prefix="ffi-twin-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.library = str(Path(cls.temporary.name) / "libffitest.so")
        subprocess.run([*compiler, "-shared", "-fPIC", str(ROOT / "tests/ffi/ffitest.c"),
                        "-o", cls.library], check=True, capture_output=True, timeout=30)

    def declare(self, symbol, function):
        return ffi.extern(self.library, symbol)(function)

    def test_positional_and_keyword_calls_match(self):
        def echo(value: ffi.c_int = 17) -> ffi.c_int: ...
        call = self.declare("ffi_echo_int", echo)
        self.assertEqual(call(23), 23)
        self.assertEqual(call(value=23), 23)
        self.assertEqual(call(), 17)

    def test_complete_positional_call_avoids_signature_binding(self):
        def echo(value: ffi.c_int) -> ffi.c_int: ...
        call = self.declare("ffi_echo_int", echo)
        with patch.object(inspect.Signature, "bind", side_effect=AssertionError("rebound positional call")):
            self.assertEqual(call(23), 23)

    def test_zero_arguments(self):
        def version() -> ffi.c_uint: ...
        call = self.declare("ZSTD_versionNumber", version)
        self.assertEqual(call(), 42)
        with self.assertRaises(TypeError):
            call(1)

    def test_binding_failures_precede_conversion(self):
        def echo(value: ffi.c_int) -> ffi.c_int: ...
        call = self.declare("ffi_echo_int", echo)
        for args, kwargs in [((), {}), ((1, 2), {}), ((2**80,), {"value": 1}), ((), {"other": 1})]:
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(TypeError) as expected:
                    inspect.signature(echo).bind(*args, **kwargs)
                with self.assertRaises(TypeError) as actual:
                    call(*args, **kwargs)
                self.assertEqual(str(actual.exception), str(expected.exception))

    def test_keyword_only_does_not_use_positional_shortcut(self):
        def echo(*, value: ffi.c_int = 7) -> ffi.c_int: ...
        call = self.declare("ffi_echo_int", echo)
        self.assertEqual(call(), 7)
        self.assertEqual(call(value=9), 9)
        with self.assertRaises(TypeError):
            call(9)

    def test_positional_only_still_rejects_keywords(self):
        def echo(value: ffi.c_int, /) -> ffi.c_int: ...
        call = self.declare("ffi_echo_int", echo)
        self.assertEqual(call(9), 9)
        with self.assertRaises(TypeError):
            call(value=9)

    def test_integer_range_checks_on_both_bindings(self):
        def signed(value: ffi.c_int) -> ffi.c_int: ...
        def unsigned(value: ffi.c_uint) -> ffi.c_uint: ...
        def wide(value: ffi.c_int64) -> ffi.c_int64: ...
        for symbol, declaration, good, bad in [
            ("ffi_echo_int", signed, [-2**31, 2**31 - 1], [-2**31 - 1, 2**31]),
            ("ffi_echo_uint", unsigned, [0, 2**32 - 1], [-1, 2**32]),
            ("ffi_echo_int64", wide, [-2**63, 2**63 - 1], [-2**63 - 1, 2**63]),
        ]:
            call = self.declare(symbol, declaration)
            for value in good:
                self.assertEqual(call(value), value)
                self.assertEqual(call(value=value), value)
            for value in bad:
                with self.assertRaises(OverflowError) as positional:
                    call(value)
                with self.assertRaises(OverflowError) as keyword:
                    call(value=value)
                self.assertEqual(str(positional.exception), str(keyword.exception))

    def test_binary_data_and_string_checks(self):
        def binary(value: bytes, size: ffi.c_size_t) -> ffi.c_uint: ...
        def string(value: str, size: ffi.c_size_t) -> ffi.c_uint: ...
        raw = self.declare("ffi_bytes_sum", binary)
        text = self.declare("ffi_bytes_sum", string)
        value = b"\x00\xff\x80A"
        self.assertEqual(raw(value, len(value)), sum(value))
        self.assertEqual(raw(size=len(value), value=value), sum(value))
        self.assertEqual(text("hi", 2), ord("h") + ord("i"))
        with self.assertRaisesRegex(ValueError, "embedded null character"):
            text("a\0b", 3)

    def test_null_pointer_and_return_checks(self):
        def pointer(value: ffi.c_void_p) -> ffi.c_void_p: ...
        call = self.declare("ffi_pointer_echo", pointer)
        self.assertEqual(call(0), 0)
        self.assertEqual(call(value=0), 0)
        def required(present: ffi.c_int) -> bytes: ...
        result = self.declare("ffi_bytes_result", required)
        self.assertEqual(result(1), b"\xff\x80")
        with self.assertRaisesRegex(ValueError, "returned NULL"):
            result(0)

    def test_aliases_and_offsets_keep_one_array(self):
        def reverse(source: list[float], target: list[float], size: ffi.c_size_t) -> None: ...
        call = self.declare("ffi_reverse", reverse)
        for keyword in [False, True]:
            values = [1.0, 2.0, 3.0, 4.0]
            if keyword:
                call(source=values, target=ffi.at(values, 1), size=3)
            else:
                call(values, ffi.at(values, 1), 3)
            self.assertEqual(values, [1.0, 3.0, 3.0, 1.0])

    def test_list_writes_and_integer_bounds(self):
        def iota(values: list[ffi.c_int64], size: ffi.c_size_t, start: ffi.c_int64 = -2) -> None: ...
        call = self.declare("ffi_iota", iota)
        values = [0, 0, 0]
        call(values, 3)
        self.assertEqual(values, [-2, -1, 0])
        call(values, 3, 4)
        self.assertEqual(values, [4, 5, 6])
        for value in [-2**63 - 1, 2**63]:
            with self.assertRaises(OverflowError):
                call([value], 1, 0)
        with self.assertRaises(TypeError):
            call([1.5], 1, 0)

    def test_offset_bounds_and_scalar_rejection(self):
        def sum_values(values: list[float], size: ffi.c_size_t) -> float: ...
        def echo(value: ffi.c_int) -> ffi.c_int: ...
        call = self.declare("ffi_sum", sum_values)
        values = [1.0, 2.0]
        self.assertEqual(call(ffi.at(values, 2), 0), 0.0)
        for offset in [-1, 3]:
            with self.assertRaises(IndexError):
                call(ffi.at(values, offset), 0)
        with self.assertRaises(TypeError):
            self.declare("ffi_echo_int", echo)(ffi.at(values, 0))


if __name__ == "__main__":
    unittest.main()
