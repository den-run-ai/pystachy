"""Bound promoting-int inference to its function without changing emitted programs."""
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


class PythonIntRetryTests(unittest.TestCase):
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
                    # A negative control: run the same compiler with only local retry removed.
                    stack.enter_context(patch.object(Gen, "int_again", return_value=False))
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

    def pair(self, source, modules=None, retry_error=False):
        source = textwrap.dedent(source).lstrip()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "main.py"
            path.write_text(source, encoding="utf-8")
            for name, code in (modules or {}).items():
                (path.parent / name).write_text(textwrap.dedent(code).lstrip(), encoding="utf-8")
            without = self.compile(path, source, False)
            with_retry = self.compile(path, source, True, retry_error)
        return without, with_retry

    def test_local_accumulator_retries_only_its_function(self):
        without, with_retry = self.pair("""
            # pystachy: python-int
            def untouched(n: int) -> int:
                return n

            def target(n: int) -> int:
                total = 0
                for i in range(n):
                    total += i
                return total
            print(untouched(3), target(4))
        """)
        self.assertEqual((without[1], with_retry[1]), (2, 1))
        self.assertEqual((without[2]["untouched"], with_retry[2]["untouched"]), (2, 1))
        self.assertEqual(with_retry[2]["target"], 2)
        self.assertEqual(without[0], with_retry[0])

    def test_multiple_locals_share_one_retry(self):
        without, with_retry = self.pair("""
            # pystachy: python-int
            def target(n: int) -> int:
                a = 0
                b = 0
                for i in range(n):
                    b += a
                    a += i
                return a + b
            print(target(4))
        """)
        self.assertEqual((without[1], with_retry[1]), (2, 1))
        self.assertEqual(with_retry[2]["target"], 2)
        self.assertEqual(without[0], with_retry[0])

    def test_callable_result_widens_an_unopted_module_local(self):
        without, with_retry = self.pair("""
            # pystachy: python-int
            from fixed import target
            print(target())
        """, {"fixed.py": """
            from typing import Callable
            def value() -> int:
                return 1
            f: Callable[[], int] = value
            def target():
                total = 0
                for i in range(3):
                    total += f()
                return total
        """})
        self.assertEqual((without[1], with_retry[1]), (2, 1))
        self.assertEqual((without[2]["value"], with_retry[2]["value"]), (2, 1))
        self.assertEqual(with_retry[2]["target"], 2)
        self.assertEqual(without[0], with_retry[0])

    def test_generic_result_widens_an_unopted_module_local(self):
        without, with_retry = self.pair("""
            # pystachy: python-int
            from fixed import target
            print(target())
        """, {"fixed.py": """
            from typing import Generic, TypeVar
            T = TypeVar('T')
            class Box(Generic[T]):
                def __init__(self, value: T) -> None:
                    self.value = value
                def get(self) -> T:
                    return self.value
            box = Box(1)
            first = box.get()
            def target():
                total = 0
                for i in range(3):
                    total += box.get()
                return total
        """})
        self.assertEqual((without[1], with_retry[1]), (2, 1))
        self.assertEqual((without[2]["get"], with_retry[2]["get"]), (2, 1))
        self.assertEqual(with_retry[2]["target"], 2)
        self.assertEqual(without[0], with_retry[0])

    def test_first_attempt_dependency_keeps_whole_program_retry(self):
        without, with_retry = self.pair("""
            # pystachy: python-int
            def echo(x):
                return x
            def target(n: int) -> int:
                total = 0
                for i in range(n):
                    echo(total)
                    total += i
                return total
            print(target(3))
        """)
        self.assertEqual((without[1], with_retry[1]), (2, 2))
        self.assertEqual(without, with_retry)

    def test_retry_dependency_falls_back_with_its_hint(self):
        without, with_retry = self.pair("""
            # pystachy: python-int
            def echo(x):
                return x
            print(echo(0))
            def target(n: int) -> int:
                total = 0
                for i in range(n):
                    echo(total)
                    total += i
                return total
            print(target(3))
        """)
        # echo(int) already exists on the first attempt. Retrying target needs a new
        # echo(BIG), so its inference must finish in a fresh program instead.
        self.assertEqual((without[1], with_retry[1]), (2, 2))
        self.assertEqual((without[2]["target"], with_retry[2]["target"]), (2, 3))
        self.assertEqual(without[0], with_retry[0])

    def test_retry_error_keeps_the_hint_for_whole_program_fallback(self):
        without, with_retry = self.pair("""
            # pystachy: python-int
            def target(n: int) -> int:
                total = 0
                for i in range(n):
                    total += i
                return total
            print(target(3))
        """, retry_error=True)
        # Fault injection exercises the normal diagnostic path while the replacement
        # body is provisional. Dropping its hint too early turns this into a rejection.
        self.assertEqual((without[1], with_retry[1]), (2, 2))
        self.assertEqual((without[2]["target"], with_retry[2]["target"]), (2, 3))
        self.assertEqual(without[0], with_retry[0])

    def test_literal_set_root_keeps_whole_program_retry(self):
        without, with_retry = self.pair("""
            # pystachy: python-int
            def target(n: int) -> int:
                total = 0
                for i in range(n):
                    total += i
                items = {1, 2, 3}
                return total + len(items)
            print(target(3))
        """)
        # This three-item literal creates a cached frozenset and its GC root.
        # Discarding only its function body would retain an unused extra cache.
        self.assertEqual((without[1], with_retry[1]), (2, 2))
        self.assertEqual(without, with_retry)

    def test_indirect_capture_keeps_whole_program_retry(self):
        without, with_retry = self.pair("""
            # pystachy: python-int
            def target(n: int) -> int:
                total = 0
                initial = total
                def read():
                    return initial
                for i in range(n):
                    total += i
                return total + read()
            print(target(3))
        """)
        self.assertEqual((without[1], with_retry[1]), (2, 2))
        self.assertEqual(without, with_retry)

    def test_global_and_generator_storage_keep_whole_program_retry(self):
        programs = ["""
            # pystachy: python-int
            total = 0
            for i in range(3):
                total += i
            print(total)
        """, """
            # pystachy: python-int
            from typing import Iterator
            def target(n: int) -> Iterator[int]:
                total = 0
                for i in range(n):
                    total += i
                    yield total
            print(list(target(3)))
        """]
        for source in programs:
            with self.subTest(source=source):
                without, with_retry = self.pair(source)
                self.assertEqual((without[1], with_retry[1]), (2, 2))
                self.assertEqual(without, with_retry)

    def test_recursive_inferred_result_keeps_whole_program_retry(self):
        without, with_retry = self.pair("""
            # pystachy: python-int
            def target(n: int):
                if n == 0:
                    return 0
                total = 0
                total += target(n - 1) + n
                return total
            print(target(3))
        """)
        self.assertEqual((without[1], with_retry[1]), (3, 3))
        self.assertEqual(without, with_retry)

    def test_captured_and_annotated_storage_stays_unchanged(self):
        programs = ["""
            # pystachy: python-int
            def target(n: int) -> int:
                total = 0
                def read():
                    return total
                for i in range(n):
                    total += i
                return read()
            print(target(3))
        """, """
            # pystachy: python-int
            def target(n: int) -> int:
                total: int = 0
                for i in range(n):
                    total += i
                return total
            print(target(3))
        """]
        for source in programs:
            with self.subTest(source=source):
                without, with_retry = self.pair(source)
                self.assertEqual((without[1], with_retry[1]), (1, 1))
                self.assertEqual(without, with_retry)

    def test_default_integer_policy_does_not_retry_or_change_ir(self):
        without, with_retry = self.pair("""
            def target(n: int) -> int:
                total = 0
                for i in range(n):
                    total += i
                return total
            print(target(3))
        """)
        self.assertEqual((without[1], with_retry[1]), (1, 1))
        self.assertEqual(without, with_retry)


if __name__ == "__main__":
    unittest.main()
