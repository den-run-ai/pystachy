"""Checks for tools/trace_annotate.py on small programs; CPython only, no LLVM.

usage: python3 -m unittest discover -s tools -p test_trace_annotate.py
"""
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

from trace_annotate import join

TOOL = Path(__file__).resolve().parent / "trace_annotate.py"


class TraceAnnotateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="trace-annotate-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def annotate(self, source):
        """Run the tool; return the annotated module's AST, its report and both programs' outputs."""
        program = self.directory / "program.py"
        output = self.directory / "annotated.py"
        report = self.directory / "report.json"
        program.write_text(textwrap.dedent(source), encoding="utf-8")
        traced = subprocess.run([sys.executable, "-I", str(TOOL), str(program), "-o", str(output), "--report", str(report)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(traced.returncode, 0, traced.stderr)
        original = subprocess.run([sys.executable, "-I", str(program)], capture_output=True, text=True, timeout=60)
        annotated = subprocess.run([sys.executable, "-I", str(output)], capture_output=True, text=True, timeout=60)
        self.assertEqual(annotated.returncode, 0, annotated.stderr)
        # Annotations change no behaviour, and recording runs the program exactly once.
        self.assertEqual(annotated.stdout, original.stdout)
        self.assertEqual(traced.stdout, original.stdout)
        return ast.parse(output.read_text(encoding="utf-8")), json.loads(report.read_text(encoding="utf-8")), original.stdout

    @staticmethod
    def signature(tree, qualified):
        """'name(p: T, ...) -> R' of a function or Class.method, as unparsed annotations."""
        owner, _, name = qualified.rpartition(".")
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == owner or (not owner and isinstance(node, ast.Module)):
                for f in node.body:
                    if isinstance(f, ast.FunctionDef) and f.name == name:
                        params = [a.arg + (": " + ast.unparse(a.annotation) if a.annotation else "") for a in f.args.args]
                        return f"{name}({', '.join(params)})" + (" -> " + ast.unparse(f.returns) if f.returns else "")
        raise AssertionError(f"{qualified} not found")

    @staticmethod
    def fields(tree, cls):
        """The annotated first assignments of a class's __init__, as 'name: T'."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == cls:
                for f in node.body:
                    if isinstance(f, ast.FunctionDef) and f.name == "__init__":
                        return sorted(f"{ast.unparse(st.target)[5:]}: {ast.unparse(st.annotation)}"
                                      for st in ast.walk(f) if isinstance(st, ast.AnnAssign))
        raise AssertionError(f"{cls} not found")

    def test_optional_values_common_bases_and_fields(self):
        tree, report, out = self.annotate("""
            \"\"\"Docstring stays first.\"\"\"
            class Shape:
                def __init__(self, size):
                    self.size = size
            class Square(Shape):
                pass
            class Circle(Shape):
                pass
            def pick(shape, flag):
                return shape if flag else None
            total = 0
            for s in [Square(2), Circle(3)]:
                if pick(s, s.size > 2) is None:
                    total += 1
            print(total)
        """)
        self.assertEqual(out, "1\n")
        # Both shapes arrive; only the Circle is returned (2 > 2 is false): returns join what ran.
        self.assertEqual(self.signature(tree, "pick"), "pick(shape: Shape, flag: bool) -> Circle | None")
        self.assertEqual(self.signature(tree, "Shape.__init__"), "__init__(self, size: int) -> None")
        self.assertEqual(self.fields(tree, "Shape"), ["size: int"])
        # Recorded classes may be forward references; the docstring keeps its place.
        self.assertIsInstance(tree.body[0], ast.Expr)
        self.assertEqual(ast.unparse(tree.body[1]), "from __future__ import annotations")
        self.assertEqual(report["unannotated"], [])

    def test_overrides_share_one_joined_signature(self):
        tree, report, _ = self.annotate("""
            class Item:
                def __init__(self, value):
                    self.value = value
            class Big(Item):
                pass
            class Small(Item):
                pass
            class Task:
                def run(self, item):
                    raise NotImplementedError
            class Copy(Task):
                def run(self, item):
                    return item.value
            class Drop(Task):
                def run(self, item):
                    return None
            tasks = [Copy(), Drop()]
            print(tasks[0].run(Big(1)), tasks[1].run(Small(2)))
        """)
        # A call through a Task receiver must accept every override, including the base's own,
        # which never ran: each one gets the join of all of them.
        for method in ["Task.run", "Copy.run", "Drop.run"]:
            self.assertEqual(self.signature(tree, method), "run(self, item: Item) -> int | None")
        self.assertEqual(report["unannotated"], [])

    def test_constructors_keep_their_own_parameter_types(self):
        tree, report, out = self.annotate("""
            class Packet:
                pass
            class Task:
                def __init__(self, w):
                    self.input = w
            class Worker(Task):
                def __init__(self, w):
                    Task.__init__(self, w)
            class Device(Task):
                def __init__(self, w):
                    Task.__init__(self, w)
            class Idle(Task):
                def __init__(self, w):
                    Task.__init__(self, None)
            tasks = [Worker(Packet()), Device(None), Idle(10000)]
            print(sum(t.input is None for t in tasks))
        """)
        self.assertEqual(out, "2\n")
        # Idle ignores its argument, as Richards' IdleTask does: its int must not reach the base or
        # its siblings. Device saw only None, so it borrows the base constructor's observations.
        self.assertEqual(self.signature(tree, "Task.__init__"), "__init__(self, w: Packet | None) -> None")
        self.assertEqual(self.signature(tree, "Worker.__init__"), "__init__(self, w: Packet) -> None")
        self.assertEqual(self.signature(tree, "Device.__init__"), "__init__(self, w: Packet | None) -> None")
        self.assertEqual(self.signature(tree, "Idle.__init__"), "__init__(self, w: int) -> None")
        self.assertEqual(self.fields(tree, "Task"), ["input: Packet | None"])
        self.assertEqual(report["unannotated"], [])

    def test_fields_written_through_arguments_and_globals(self):
        tree, report, out = self.annotate("""
            class Node:
                pass
            class Leaf(Node):
                pass
            class Holder:
                def __init__(self):
                    self.slot = None
            class Area:
                def __init__(self):
                    self.table = [None] * 4
                    self.head = None
            area = Area()
            def fill(h, n):
                h.slot = n
            def register(n, i):
                area.table[i] = n
                area.head = n
            h = Holder()
            fill(h, Leaf())
            fill(h, h.slot)
            register(Leaf(), 1)
            register(Node(), 2)
            print(type(h.slot).__name__, type(area.head).__name__)
        """)
        self.assertEqual(out, "Leaf Node\n")
        # Holder has no methods but __init__: its field is seen on the object passed to fill.
        self.assertEqual(self.fields(tree, "Holder"), ["slot: Leaf | None"])
        # Area changes only through the global; [None] * 4 joins the items stored later.
        self.assertEqual(self.fields(tree, "Area"), ["head: Node | None", "table: list[Node | None]"])
        self.assertEqual(report["unannotated"], [])

    def test_slots_and_chained_stores_are_declared_in_the_class(self):
        tree, report, out = self.annotate("""
            from math import sin
            class Point:
                __slots__ = ("x", "y")
                def __init__(self, i):
                    self.x = x = sin(i)
                    self.y = x * 2
            p = Point(1)
            print(round(p.x + p.y, 6))
        """)
        self.assertEqual(out, "2.524413\n")
        point = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        # Slots have no instance dictionary; `self.x = x = ...` cannot carry an annotation.
        self.assertEqual(ast.unparse(point.body[0]), "x: float")
        self.assertEqual(self.fields(tree, "Point"), ["y: float"])
        self.assertEqual(report["unannotated"], [])

    def test_mixed_and_none_only_positions_are_reported_with_counts(self):
        tree, report, _ = self.annotate("""
            def scale(v):
                return v * 2
            def ignore(x):
                return 0
            for i in range(5):
                scale(1.5)
            scale(3)
            ignore(None)
            print("ok")
        """)
        self.assertEqual(self.signature(tree, "scale"), "scale(v)")
        self.assertEqual(self.signature(tree, "ignore"), "ignore(x) -> int")
        rows = {row["where"]: row for row in report["unannotated"]}
        self.assertEqual(rows["scale:v"]["samples"], {"float": 5, "int": 1})
        self.assertEqual(rows["scale:v"]["reason"], "mixed")
        self.assertEqual(rows["scale:return"]["samples"], {"float": 5, "int": 1})
        self.assertEqual(rows["ignore:x"]["reason"], "only None observed")

    def test_recording_runs_no_program_hooks(self):
        _, _, out = self.annotate("""
            calls = []
            class Slots:
                __slots__ = ("x",)
                def __init__(self):
                    self.x = 1
                def __getattr__(self, name):
                    calls.append(("getattr", name))
                    raise AttributeError(name)
                def __eq__(self, other):
                    calls.append("eq")
                    return True
                def __hash__(self):
                    calls.append("hash")
                    return 0
            class Plain:
                def __init__(self):
                    self.inner = Slots()
                def __getattr__(self, name):
                    calls.append(("getattr", name))
                    raise AttributeError(name)
            def use(a, b, c):
                return a
            use(Plain(), [Slots(), Slots()], {"k": Slots()})
            print(calls)
        """)
        self.assertEqual(out, "[]\n")

    def test_join(self):
        self.assertEqual(join({"list[None]", "list[Leaf | None]"}, {}), "list[Leaf | None]")
        self.assertEqual(join({"list[?]", "list[int]"}, {}), "list[int]")
        self.assertEqual(join({"int", "None"}, {}), "int | None")
        self.assertIsNone(join({"int", "bool"}, {}))
        self.assertIsNone(join({"int", "float"}, {}))
        self.assertIsNone(join({"MIXED"}, {}))


if __name__ == "__main__":
    unittest.main()
