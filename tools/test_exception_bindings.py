"""Exception binding queries retain their scope semantics with bounded syntax work."""
from collections import Counter
from contextlib import ExitStack, redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pystachy_compiler import analysis, diagnostics, driver, exceptions  # noqa: E402
from src.pystachy_compiler.gen import Gen  # noqa: E402
from src.pystachy_compiler.lexer import Lexer  # noqa: E402
from src.pystachy_compiler.parser import Parser  # noqa: E402
from src.pystachy_compiler.syntax import mk  # noqa: E402
from tools.scaling import handlers, samehandlers  # noqa: E402


def parsed(source):
    source = textwrap.dedent(source).lstrip().encode("utf-8").decode("latin1")
    return Parser(Lexer(source, 1).file()).module().kids


class BindingIndexTests(unittest.TestCase):
    def setUp(self):
        state = patch.multiple(diagnostics, SRC="bindings.py", FILES=[], CAPTURE=False)
        state.start()
        self.addCleanup(state.stop)

    def check(self, source, expected):
        self.check_body(parsed(source), expected)

    def check_body(self, body, expected):
        found = {}
        analysis.other_bindings(body, found)
        self.assertEqual(set(found), set(expected))
        # Keep the old per-name query as a second, independent traversal oracle.
        names = {"missing", *expected}
        pending = list(body)
        while pending:
            node = pending.pop()
            names.add(node.s)
            pending.extend(node.kids)
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(name in found, analysis.binds_other(body, name))

    def test_assignment_loop_with_import_and_expression_bindings(self):
        self.check("""
            plain = chain = 1
            a, (b, *tail) = values
            annotated: int
            augmented += 1
            object.field = 2
            mapping[(index := 1)] = 3
            for left, right in pairs:
                inside = left
            with first() as one, second() as (two, three):
                pass
            import math as maths
            from sys import argv as arguments
            result = (named := 1)
            comp = [(item := x) for x in values]
            func = lambda p=(default := 2): (private := p)
        """, {"plain", "chain", "a", "b", "tail", "annotated", "augmented", "index", "left", "right",
              "inside", "one", "two", "three", "maths", "arguments", "result", "named", "comp",
              "item", "func", "default"})

    def test_nested_definitions_bind_only_their_headers_in_this_scope(self):
        self.check("""
            @decorate(decorator := 1)
            def inner(p=(default := 2)):
                hidden = 3
                try:
                    pass
                except ValueError as nested_handler:
                    hidden_handler = 4
            class Plain:
                hidden_class = 5
            class Child(base := Plain):
                hidden_subclass = 6
        """, {"inner", "decorator", "default", "Plain", "Child", "base"})

    def test_control_flow_includes_dead_blocks_but_excludes_handler_targets(self):
        self.check("""
            if False:
                unreachable = 1
            while condition:
                try:
                    tried = 2
                except ValueError as target:
                    handler = 3
                    try:
                        pass
                    except TypeError as nested_target:
                        nested = 4
                else:
                    alternate = 5
                finally:
                    final = 6
        """, {"unreachable", "tried", "handler", "nested", "alternate", "final"})

    def test_target_rebound_in_another_handler_is_an_ordinary_binding(self):
        self.check("""
            try:
                pass
            except ValueError as first:
                pass
            except TypeError as second:
                first = 1
            try:
                pass
            except RuntimeError as second:
                pass
        """, {"first"})

    def test_declarations_deletes_and_comprehension_targets_keep_existing_policy(self):
        self.check("""
            global declared
            del removed
            ignored = [private for private in values]
        """, {"ignored"})
        body = parsed("""
            def outer():
                captured = 1
                def inner():
                    nonlocal captured
                    global declared
                    ignored = [private for private in values]
        """)[0].kids[2].kids[1].kids[2].kids
        self.check_body(body, {"ignored"})
        node = mk("compfor", "", 1, [mk("name", "private", 1, []),
                                      mk("walrus", "outer", 1, [mk("int", "1", 1, [])])])
        found = {}
        analysis.other_bindings([node], found)
        self.assertEqual(found, {"outer": True})
        self.assertFalse(analysis.binds_other([node], "private"))

    def test_async_wrappers_keep_the_original_scanner_policy(self):
        # An "async" wrapper node (async with/for that no async def holds, which the parser
        # rejects, so built here): match binds_other's existing traversal rather than
        # extending its binding rules.
        loop = parsed("""
            for private in (iterable := stream):
                hidden_loop = 1
        """)[0]
        manager = parsed("""
            with (manager := context) as alias:
                hidden_with = 2
        """)[0]
        self.check_body([mk("async", "", 1, [loop]), mk("async", "", 3, [manager])], {"iterable", "manager"})

    def test_async_statements_bind_as_their_pep492_statements(self):
        # An async def's async with and async for become ordinary statements after parsing
        # (coroutines.desugar_async): their targets, their bodies' bindings and the locals
        # that hold the manager, the iterator and their state are the function's
        body = parsed("""
            async def owner():
                async for private in (iterable := stream):
                    hidden_loop = 1
                async with (manager := context) as alias:
                    hidden_with = 2
        """)[0].kids[2].kids
        self.check_body(body, {"iterable", "manager", "private", "alias", "hidden_loop", "hidden_with",
                               "__pys_aw0.it", "__pys_aw0.run", "__pys_aw0.val",
                               "__pys_aw1.mgr", "__pys_aw1.val", "__pys_aw1.hit"})


class BindingCompileTests(unittest.TestCase):
    def compile(self, path, source, legacy=False):
        original_enter, original_bind = Gen.enter, Gen.bind_as
        original_index, original_stmt = analysis.other_bindings, analysis.stmt_binds
        index_depth = scan_depth = 0
        current = []
        stats = {"builds": Counter(), "visits": 0, "legacy_visits": 0, "frames": [], "queries": []}
        saved = {name: getattr(driver, name).copy() for name in ("LAMBDAS", "RENAMED", "LIBS", "LINKDL")}

        class FullScan(dict):
            # Test-only negative control: the old per-name traversal, at the same query point.
            def __init__(self, body):
                self.body = body

            def __contains__(self, name):
                nonlocal scan_depth
                scan_depth += 1
                try:
                    return analysis.binds_other(self.body, name)
                finally:
                    scan_depth -= 1

        def enter(generator, function, body):
            original_enter(generator, function, body)
            stats["frames"].append(generator.fn)  # retain identities across local retries
            if legacy:
                node = function.node
                generator.fn.otherbinds = FullScan(node.kids if node.kind == "block" else node.kids[2].kids)

        def index(body, out):
            nonlocal index_depth
            if index_depth == 0:
                stats["builds"][current[-1].f.name] += 1
            stats["visits"] += len(body)
            index_depth += 1
            try:
                return original_index(body, out)
            finally:
                index_depth -= 1

        def stmt(node, name):
            if scan_depth:
                stats["legacy_visits"] += 1
            return original_stmt(node, name)

        def bind(generator, name, value, kind):
            current.append(generator.fn)
            try:
                original_bind(generator, name, value, kind)
                stats["queries"].append((generator.fn, generator.fn.otherbinds))
            finally:
                current.pop()

        output, ir, status = StringIO(), "", 0
        try:
            with ExitStack() as stack, redirect_stderr(output):
                stack.enter_context(patch.object(Gen, "enter", enter))
                stack.enter_context(patch.object(Gen, "bind_as", bind))
                stack.enter_context(patch.object(analysis, "other_bindings", index))
                stack.enter_context(patch.object(exceptions, "other_bindings", index))
                stack.enter_context(patch.object(analysis, "stmt_binds", stmt))
                try:
                    ir = driver.compile_program(str(path), source, [str(path.parent), str(ROOT / "lib")], "")
                except SystemExit as failure:
                    status = failure.code
        finally:
            for name, value in saved.items():
                destination = getattr(driver, name)
                if isinstance(destination, list):
                    destination[:] = value
                else:
                    destination.clear()
                    destination.update(value)
        return (status, output.getvalue(), ir), stats

    def pair(self, source):
        source = textwrap.dedent(source).lstrip()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "main.py"
            path.write_text(source, encoding="utf-8")
            baseline, old = self.compile(path, source, True)
            candidate, new = self.compile(path, source)
        self.assertEqual(candidate, baseline)
        return candidate, old, new

    def test_distinct_handler_work_is_linear_and_same_target_is_a_control(self):
        for count in (8, 16, 32):
            for shape, distinct in ((handlers, True), (samehandlers, False)):
                with self.subTest(count=count, distinct=distinct):
                    result, old, new = self.pair("\n".join(shape(count)["main.py"]))
                    self.assertEqual(result[0], 0, result[1])
                    visits = 3 * count + 1
                    self.assertEqual(old["legacy_visits"], visits * (count if distinct else 1))
                    self.assertEqual(new["visits"], visits)
                    self.assertEqual(sum(new["builds"].values()), 1)
                    # The empty index is complete, not a signal to scan again.
                    self.assertEqual(new["queries"][0][1], {})
                    self.assertTrue(all(index is new["queries"][0][1] for _, index in new["queries"]))
                    self.assertTrue(all(frame.otherbinds is None for frame in new["frames"]))

    def test_nested_template_compilation_keeps_the_outer_index(self):
        result, _, new = self.pair("""
            def nested(value):
                try:
                    raise ValueError("nested")
                except ValueError as inner:
                    print(inner)
                inner = value
                return inner

            def outer() -> int:
                try:
                    raise ValueError("outer")
                except ValueError as first:
                    print(first)
                value = nested(4)
                try:
                    raise KeyError("again")
                except KeyError as second:
                    print(second)
                return value
            print(outer())
        """)
        self.assertEqual(result[0], 0, result[1])
        self.assertEqual(sorted(new["builds"].values()), [1, 1])
        outer = [index for frame, index in new["queries"] if frame.f.name.endswith("outer")]
        inner = [index for frame, index in new["queries"] if frame.f.name.endswith("nested")]
        self.assertEqual(len(outer), 2)
        self.assertEqual(len(inner), 1)
        self.assertIs(outer[0], outer[1])
        self.assertIsNot(outer[0], inner[0])
        self.assertTrue(all(frame.otherbinds is None for frame in new["frames"]))

    def test_local_retry_rebuilds_the_index_and_plain_functions_stay_lazy(self):
        result, _, new = self.pair("""
            def plain(x: int) -> int:
                return x + 1

            def target(xs: list[float]) -> float:
                try:
                    raise ValueError("retry")
                except ValueError as error:
                    pass
                total = 0
                for x in xs:
                    total += x
                return total / len(xs)
            print(plain(2), target([1.5, 2.5]))
        """)
        self.assertEqual(result[0], 0, result[1])
        self.assertEqual(list(new["builds"].values()), [2])
        self.assertEqual(len(new["queries"]), 2)
        self.assertIsNot(new["queries"][0][0], new["queries"][1][0])
        self.assertIsNot(new["queries"][0][1], new["queries"][1][1])

    def test_global_reader_and_global_declaration_rejections_stay_exact(self):
        for name in ("except_as_global_read", "except_as_global"):
            with self.subTest(name=name):
                source = (ROOT / "tests" / "errors" / "exceptions" / f"{name}.py").read_text()
                result, _, _ = self.pair(source)
                self.assertEqual(result[0], 1)
                self.assertIn("except ... as", result[1])
                self.assertEqual(result[2], "")

    def test_module_initialization_releases_its_index(self):
        result, _, new = self.pair("""
            try:
                raise ValueError("first")
            except ValueError as first:
                print(first)
            try:
                raise KeyError("second")
            except KeyError as second:
                print(second)
        """)
        self.assertEqual(result[0], 0, result[1])
        self.assertEqual(new["builds"], {"<module>": 1})
        self.assertIs(new["queries"][0][1], new["queries"][1][1])
        self.assertTrue(all(frame.otherbinds is None for frame in new["frames"]))

    def test_existing_shadowing_and_cleanup_cases_keep_exact_ir(self):
        for name in ("exc_as_rebind", "exc_as_unbound", "exc_nested", "exc_finally_break",
                     "exc_binding_index_cleanup", "exc_binding_index_scopes"):
            with self.subTest(name=name):
                source = (ROOT / "tests" / "programs" / "exceptions" / f"{name}.py").read_text()
                result, _, _ = self.pair(source)
                self.assertEqual(result[0], 0, result[1])


if __name__ == "__main__":
    unittest.main()
