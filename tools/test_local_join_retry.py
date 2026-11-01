"""Retry only a function whose own unannotated locals widen, without changing emitted programs.

Each case compiles the same source twice: once with Gen.local_again disabled (the
whole-program Rejoin pass that every join took before) and once as the compiler does.
The emitted LLVM must be identical; the counts show which work the retry skipped.
"""
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import driver  # noqa: E402
from src.pystachy_compiler.gen import Gen  # noqa: E402


class LocalJoinRetryTests(unittest.TestCase):
    def compile(self, path, source, enabled, retry_error=False):
        loads = []
        bodies = Counter()
        load = driver.Loader.program
        body = Gen.function_body
        saved = {name: getattr(driver, name).copy()
                 for name in ("LAMBDAS", "RENAMED", "LIBS", "LINKDL")}

        def observed_load(loader, filename, code):
            loads.append(filename)
            return load(loader, filename, code)

        def observed_body(generator, function, statements):
            name = function.name.rsplit("$", 1)[-1]
            bodies[name] += 1
            result = body(generator, function, statements)
            if retry_error and name == "target" and bodies[name] == 2:
                generator.err("injected error in the discarded retry")
            return result

        try:
            with ExitStack() as stack:
                stack.enter_context(patch.object(driver.Loader, "program", observed_load))
                stack.enter_context(patch.object(Gen, "function_body", observed_body))
                if not enabled:
                    # The negative control: the same compiler with only the local retry removed.
                    stack.enter_context(patch.object(Gen, "local_again", return_value=False))
                ir = driver.compile_program(str(path), source,
                                            [str(path.parent), str(ROOT / "lib")], "")
        finally:
            for name, value in saved.items():
                current = getattr(driver, name)
                if isinstance(current, list):
                    current[:] = value
                else:
                    current.clear()
                    current.update(value)
        return ir, len(loads), bodies

    def pair(self, source, retry_error=False):
        source = textwrap.dedent(source).lstrip()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "main.py"
            path.write_text(source, encoding="utf-8")
            without = self.compile(path, source, False)
            with_retry = self.compile(path, source, True, retry_error)
        return without, with_retry

    def assert_function_retry(self, source):
        # One program load instead of two; target's body compiled twice either way.
        without, with_retry = self.pair(source)
        self.assertEqual((without[1], with_retry[1]), (2, 1))
        self.assertEqual(with_retry[2]["target"], 2)
        self.assertEqual(without[0], with_retry[0])
        return without, with_retry

    def assert_program_retry(self, source):
        without, with_retry = self.pair(source)
        self.assertEqual((without[1], with_retry[1]), (2, 2))
        self.assertEqual(without[0], with_retry[0])

    def test_float_accumulator_retries_only_its_function(self):
        without, with_retry = self.assert_function_retry("""
            def untouched(n: int) -> int:
                return n + 1

            def target(xs: list[float]) -> float:
                total = 0
                for x in xs:
                    total += x
                return total / len(xs)
            print(untouched(3), target([1.5, 2.5]))
        """)
        self.assertEqual((without[2]["untouched"], with_retry[2]["untouched"]), (2, 1))

    def test_several_locals_share_one_retry(self):
        self.assert_function_retry("""
            def target(n: int) -> str:
                a = 0
                c = 0
                label = None
                for i in range(n):
                    a += 0.5
                    c = c + i * 0.25
                    label = "x" * i
                return f"{a} {c} {label}"
            print(target(3))
        """)

    def test_method_local_retries_only_its_method(self):
        self.assert_function_retry("""
            class Stats:
                def __init__(self, xs: list[float]) -> None:
                    self.xs = xs

                def target(self) -> float:
                    total = 0
                    for x in self.xs:
                        total += x
                    return total / len(self.xs)
            print(Stats([1.5, 2.5]).target())
        """)

    def test_runtime_declarations_keep_the_whole_program_order(self):
        # The discarded body divides an int total before the retry boxes the union: without
        # rewinding the declarations it made, the retry would reorder the module's declares.
        self.assert_function_retry("""
            def target(xs: list[float]) -> float:
                total = 0
                for x in xs:
                    total += x
                return total / 2

            def boxed(v: int | float) -> int | float:
                return v
            print(target([1.0, 2.0]), boxed(3))
        """)

    def test_retry_error_keeps_the_hint_for_whole_program_fallback(self):
        without, with_retry = self.pair("""
            def target(xs: list[float]) -> float:
                total = 0
                for x in xs:
                    total += x
                return total / len(xs)
            print(target([1.5]))
        """, retry_error=True)
        # An error while the replacement body is provisional takes the ordinary Rejoin path.
        self.assertEqual((without[1], with_retry[1]), (2, 2))
        self.assertEqual((without[2]["target"], with_retry[2]["target"]), (2, 3))
        self.assertEqual(without[0], with_retry[0])

    def test_global_join_keeps_program_retry(self):
        self.assert_program_retry("""
            total = 0
            def add(x: float) -> None:
                global total
                total += x
            add(1.5)
            print(total)
        """)

    def test_return_join_keeps_program_retry(self):
        self.assert_program_retry("""
            def half(n: int):
                if n % 2 == 0:
                    return n // 2
                return n / 2
            print(half(3), half(4))
        """)

    def test_field_and_other_pending_joins_keep_program_retry(self):
        programs = ["""
            class Box:
                def __init__(self) -> None:
                    self.v = 0
            b = Box()
            b.v = 2.5
            print(b.v)
        """, """
            def target(xs: list[float]) -> float:
                total = 0
                for x in xs:
                    total += x
                return total / len(xs)
            count = 0
            count = count + 0.5
            print(target([1.5]), count)
        """]
        for source in programs:
            with self.subTest(source=source):
                self.assert_program_retry(source)

    def test_captured_local_keeps_program_retry(self):
        self.assert_program_retry("""
            def outer(xs: list[float]) -> None:
                total = 0
                def get():
                    return total
                for x in xs:
                    total += x
                print(get())
            outer([1.5, 2.5])
        """)

    def test_nested_function_and_lambda_keep_program_retry(self):
        programs = ["""
            def outer(xs: list[float]) -> float:
                def target(ys: list[float]) -> float:
                    total = 0
                    for y in ys:
                        total += y
                    return total / len(ys)
                return target(xs)
            print(outer([1.5, 2.5]))
        """, """
            def target(xs: list[float]) -> str:
                total = 0
                f = lambda v: v * 2
                for x in xs:
                    total += f(x)
                return str(total)
            print(target([1.5]))
        """]
        for source in programs:
            with self.subTest(source=source):
                self.assert_program_retry(source)

    def test_generator_keeps_program_retry(self):
        self.assert_program_retry("""
            def running(xs: list[float]):
                total = 0
                for x in xs:
                    total += x
                    yield total
            print(list(running([1.5, 2.5])))
        """)

    def test_new_dependency_keeps_program_retry(self):
        # The discarded body specializes show() for an int, which the retry must not inherit.
        self.assert_program_retry("""
            def show(v):
                return str(v)

            def target(xs: list[float]) -> str:
                total = 0
                out = show(total)
                for x in xs:
                    total += x
                return out + show(total)
            print(target([1.5]))
        """)

    def test_program_without_joins_is_unchanged(self):
        without, with_retry = self.pair("""
            def target(xs: list[float]) -> float:
                total = 0.0
                for x in xs:
                    total += x
                return total
            print(target([1.5]))
        """)
        self.assertEqual((without[1], with_retry[1]), (1, 1))
        self.assertEqual(without, with_retry)


if __name__ == "__main__":
    unittest.main()
