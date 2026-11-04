"""Turn the unittest methods of a CPython test file into standalone differential programs.

usage: python3 tools/cpython_test_methods.py extract TESTFILE OUTDIR
       python3 tools/cpython_test_methods.py combine TESTFILE OUT.py CLASS.METHOD...
       python3 tools/cpython_test_methods.py triage [--compiler CMD] [-j N] OUT.json WORKDIR TESTFILE...

Native execution of CPython's Lib/test files needs unittest and test.support before any
library gap matters, so the corpus grows through adapted methods (tests/upstream/core-sweep.md).
This tool makes those adaptations mechanically, by rules that keep each test's inputs and
assertions; nothing is edited by hand:

- Module-level code is kept, less imports of unittest, test and doctest, the statements that
  use the names those imports bind, load_tests/setUpModule/tearDownModule/test_main and the
  `if __name__ == "__main__":` block.
- `X = import_helper.import_fresh_module('mod', blocked=[...])` becomes `import mod as X`
  (the pure-Python module). A `fresh=[...]` C-accelerator variant is dropped with the test
  classes that use it, and a class attribute `module = X` is inlined: `self.module.f` -> `X.f`.
- Test classes lose their unittest base (a mixin base of the file stays, so single
  inheritance stays single). Methods with a recognized skip decorator on the method or a test
  class are left out. unittest and test.support decorators are dropped.
- `setUp()` becomes `__init__()`, as unittest makes one instance per test and calls setUp()
  before it (`super().setUp()` becomes `super().__init__()`; --no-setup-init keeps setUp).
- `self.assertX(...)` statements become `assert` statements of the same condition (also
  through an alias such as `eq = self.assertEqual`); assertRaises (call and `with` forms,
  `cm.exception` included) becomes try/except/else; `with self.subTest(...)` keeps its body;
  `self.fail(m)` raises AssertionError(m); a reached `self.skipTest()` raises instead of
  qualifying the test. Unsupported unittest features (assertWarns, addCleanup, ...) raise
  NotImplementedError.
- Each program keeps only the module-level definitions it uses and, in its test classes, only
  its own test method (a method that takes only self is compiled whether or not it is called,
  so another rejected test would reject the whole class). It runs the test on a fresh
  instance and tearDown(), then prints `ok CLASS.METHOD`. A program that uses random calls
  random.seed(0) before each test, so every run draws the same inputs.

`triage` extracts each file's methods into WORKDIR, runs every program under the running
CPython and under the compiler's `run`, and writes one record per method: cpython-fail (the
mechanical extraction fails or exits before its success marker; left out of the denominator), match,
match-python-int (matches once `# pystachy: python-int` is prepended, for a 64-bit-overflow
or wide-literal failure), compile-error, differs (compiled, other output or exit status:
check for wrong results first) or timeout. Record expectations for corpus programs with the
CPython of .python-version (tests/record.sh), never from this tool's output.
"""
import argparse
import ast
import concurrent.futures
import copy
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DROP_MODULES = ("unittest", "test", "doctest")
SKIP_DECORATORS = ("cpython_only", "skip", "skipIf", "skipUnless", "expectedFailure", "requires_resource",
                   "bigmemtest", "bigaddrspacetest", "requires_subprocess", "requires_fork", "run_with_locale",
                   "refcount_test", "impl_detail", "no_tracing", "requires_debug_ranges", "requires_IEEE_754",
                   "requires_docstrings", "thread_unsafe", "requires_working_socket")
DROP_FUNCTIONS = ("load_tests", "setUpModule", "tearDownModule", "test_main")


class Unsupported(Exception):
    """A test needs a unittest feature that has no mechanical replacement."""


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        d = dotted(node.value)
        return d + "." + node.attr if d else None
    if isinstance(node, ast.Call):
        return dotted(node.func)
    return None


def skip_decorated(node):
    return any((dotted(d) or "").split(".")[-1] in SKIP_DECORATORS for d in node.decorator_list)


def self_call(node, names):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "self"
            and node.func.attr in names)


def eq(a):
    return ast.Compare(a[0], [ast.Eq()], [a[1]])


ASSERTS = {
    "assertEqual": eq, "assertEquals": eq, "assertListEqual": eq, "assertTupleEqual": eq,
    "assertDictEqual": eq, "assertSetEqual": eq, "assertSequenceEqual": eq, "assertMultiLineEqual": eq,
    "assertNotEqual": lambda a: ast.Compare(a[0], [ast.NotEq()], [a[1]]),
    "assertTrue": lambda a: a[0],
    "assertFalse": lambda a: ast.UnaryOp(ast.Not(), a[0]),
    "assertIs": lambda a: ast.Compare(a[0], [ast.Is()], [a[1]]),
    "assertIsNot": lambda a: ast.Compare(a[0], [ast.IsNot()], [a[1]]),
    "assertIsNone": lambda a: ast.Compare(a[0], [ast.Is()], [ast.Constant(None)]),
    "assertIsNotNone": lambda a: ast.Compare(a[0], [ast.IsNot()], [ast.Constant(None)]),
    "assertIn": lambda a: ast.Compare(a[0], [ast.In()], [a[1]]),
    "assertNotIn": lambda a: ast.Compare(a[0], [ast.NotIn()], [a[1]]),
    "assertIsInstance": lambda a: ast.Call(ast.Name("isinstance", ast.Load()), [a[0], a[1]], []),
    "assertNotIsInstance": lambda a: ast.UnaryOp(ast.Not(), ast.Call(ast.Name("isinstance", ast.Load()), [a[0], a[1]], [])),
    "assertGreater": lambda a: ast.Compare(a[0], [ast.Gt()], [a[1]]),
    "assertGreaterEqual": lambda a: ast.Compare(a[0], [ast.GtE()], [a[1]]),
    "assertLess": lambda a: ast.Compare(a[0], [ast.Lt()], [a[1]]),
    "assertLessEqual": lambda a: ast.Compare(a[0], [ast.LtE()], [a[1]]),
}
ONE_OPERAND = ("assertTrue", "assertFalse", "assertIsNone", "assertIsNotNone")
OTHER_ASSERTS = ("assertAlmostEqual", "assertNotAlmostEqual", "assertRaises", "assertRaisesRegex",
                 "assertRegex", "assertNotRegex", "fail", "skipTest", "assertCountEqual")
UNSUPPORTED = ("assertWarns", "assertWarnsRegex", "assertLogs", "assertNoLogs")
EXPRESSION_ONLY = ("subTest", "assertRaises", "assertRaisesRegex", "addCleanup", "enterContext", "id",
                   "shortDescription") + UNSUPPORTED


def almost(args, kws, negate):
    if "delta" in kws:
        cond = ast.Compare(ast.Call(ast.Name("abs", ast.Load()), [ast.BinOp(args[0], ast.Sub(), args[1])], []),
                           [ast.LtE()], [kws["delta"]])
    else:
        diff = ast.Call(ast.Name("abs", ast.Load()), [ast.BinOp(args[1], ast.Sub(), args[0])], [])
        cond = ast.BoolOp(ast.Or(), [ast.Compare(args[0], [ast.Eq()], [args[1]]),
                                     ast.Compare(ast.Call(ast.Name("round", ast.Load()),
                                                          [diff, kws.get("places", ast.Constant(7))], []),
                                                 [ast.Eq()], [ast.Constant(0)])])
    return ast.UnaryOp(ast.Not(), cond) if negate else cond


def search(pattern, text):
    return ast.Call(ast.Attribute(ast.Name("re", ast.Load()), "search", ast.Load()), [pattern, text], [])


def raises(exc, body, name=None, regex=None):
    # try: body / except exc: (the message matches regex) / else: raise AssertionError
    handler = []
    if regex is not None:
        handler.append(ast.Assert(search(regex, ast.Call(ast.Name("str", ast.Load()), [ast.Name("_exc", ast.Load())], []))))
    if name:
        handler.append(ast.Assign([ast.Name(name + "_exception", ast.Store())], ast.Name("_exc", ast.Load())))
    bound = name is not None or regex is not None
    return ast.Try(body=body or [ast.Pass()],
                   handlers=[ast.ExceptHandler(type=exc, name="_exc" if bound else None, body=handler or [ast.Pass()])],
                   orelse=[ast.Raise(ast.Call(ast.Name("AssertionError", ast.Load()),
                                              [ast.Constant("did not raise")], []))],
                   finalbody=[])


def aliases(fn):
    """{NAME: assertX} for each `NAME = self.assertX` in fn, where NAME is assigned nothing else."""
    found, other = {}, set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    v = n.value
                    if (isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id == "self"
                            and v.attr in set(ASSERTS) | set(OTHER_ASSERTS)):
                        if found.get(t.id, v.attr) != v.attr:
                            other.add(t.id)
                        found[t.id] = v.attr
                    else:
                        other.add(t.id)
    return {k: v for k, v in found.items() if k not in other}


class Rewriter(ast.NodeTransformer):
    """Rewrites a method's unittest calls into plain statements."""

    def __init__(self, alias):
        self.alias = alias
        self.contexts = set()
        self.uses_re = False

    def statements(self, body):
        out = []
        for st in body:
            r = self.visit(st)
            if r is not None:
                out.extend(r if isinstance(r, list) else [r])
        return out

    def visit_Assign(self, node):
        if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in self.alias
                and isinstance(node.value, ast.Attribute)):
            return None
        return self.generic_visit(node)

    def visit_Expr(self, node):
        call = node.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in self.alias:
            call = ast.Call(ast.Attribute(ast.Name("self", ast.Load()), self.alias[call.func.id], ast.Load()),
                            call.args, call.keywords)
        if not self_call(call, set(ASSERTS) | set(OTHER_ASSERTS) | set(UNSUPPORTED)):
            return self.generic_visit(node)
        m = call.func.attr
        args = [self.visit(a) for a in call.args]
        kws = {k.arg: self.visit(k.value) for k in call.keywords}
        if m in ASSERTS:
            if len(args) < (1 if m in ONE_OPERAND else 2):
                raise Unsupported(f"{m} with keyword operands")
            new = ast.Assert(ASSERTS[m](args))
        elif m in ("assertAlmostEqual", "assertNotAlmostEqual"):
            new = ast.Assert(almost(args, kws, m == "assertNotAlmostEqual"))
        elif m in ("assertRaises", "assertRaisesRegex"):
            rest = args[2:] if m == "assertRaisesRegex" else args[1:]
            if not rest:
                raise Unsupported(f"{m} without a callable")
            keywords = [ast.keyword(k, v) for k, v in kws.items() if k != "msg"]
            regex = args[1] if m == "assertRaisesRegex" else None
            self.uses_re |= regex is not None
            new = raises(args[0], [ast.Expr(ast.Call(rest[0], rest[1:], keywords))], regex=regex)
        elif m in ("assertRegex", "assertNotRegex"):
            found = search(args[1], args[0])
            self.uses_re = True
            new = ast.Assert(found if m == "assertRegex" else ast.UnaryOp(ast.Not(), found))
        elif m == "fail":
            new = ast.Raise(ast.Call(ast.Name("AssertionError", ast.Load()), args[:1], []))
        elif m == "skipTest":
            new = ast.Raise(ast.Call(ast.Name("NotImplementedError", ast.Load()),
                                    [ast.Constant("test called skipTest")], []))
        elif m == "assertCountEqual":
            def counted(a):
                return ast.Call(ast.Name("sorted", ast.Load()), [ast.Call(ast.Name("map", ast.Load()),
                                                                          [ast.Name("repr", ast.Load()), a], [])], [])
            new = ast.Assert(ast.Compare(counted(args[0]), [ast.Eq()], [counted(args[1])]))
        else:
            raise Unsupported(m)
        return ast.copy_location(new, node)

    def visit_With(self, node):
        if len(node.items) == 1:
            item = node.items[0]
            ctx = item.context_expr
            if self_call(ctx, ("subTest",)):
                return self.statements(node.body) or [ast.Pass()]
            if self_call(ctx, ("assertRaises", "assertRaisesRegex")):
                name = None
                if item.optional_vars is not None:
                    if not isinstance(item.optional_vars, ast.Name):
                        raise Unsupported("an assertRaises target other than a name")
                    name = item.optional_vars.id
                    self.contexts.add(name)
                body = self.statements(node.body)
                out = []
                if name:
                    out.append(ast.Assign([ast.Name(name + "_exception", ast.Store())], ast.Constant(None)))
                regex = None
                if ctx.func.attr == "assertRaisesRegex":
                    if len(ctx.args) < 2:
                        raise Unsupported("assertRaisesRegex with a keyword regex")
                    regex = self.visit(ctx.args[1])
                    self.uses_re = True
                out.append(raises(self.visit(ctx.args[0]), body, name, regex))
                return out
            if self_call(ctx, UNSUPPORTED):
                raise Unsupported(ctx.func.attr)
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id in self.contexts and node.attr == "exception":
            return ast.copy_location(ast.Name(node.value.id + "_exception", ast.Load()), node)
        return self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id in self.alias:
            raise Unsupported(f"{node.func.id} (self.{self.alias[node.func.id]}) in an expression")
        if self_call(node, EXPRESSION_ONLY + tuple(ASSERTS)):
            raise Unsupported(f"self.{node.func.attr} in an expression")
        return self.generic_visit(node)


class ModuleAttribute(ast.NodeTransformer):
    """self.module.f -> X.f and self.module -> X, for class attributes module = X (a module)."""

    def __init__(self, table):
        self.table = table

    def visit_Attribute(self, node):
        if (isinstance(node.value, ast.Name) and node.value.id == "self" and node.attr in self.table
                and isinstance(node.ctx, ast.Load)):
            return ast.copy_location(ast.Name(self.table[node.attr], ast.Load()), node)
        return self.generic_visit(node)


def defines(st):
    if isinstance(st, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
        return {st.name}
    if isinstance(st, ast.ImportFrom) and st.module == "__future__":
        return set()  # (binds nothing a test uses, but changes how the module compiles: always kept)
    if isinstance(st, (ast.Import, ast.ImportFrom)):
        return {(a.asname or a.name).split(".")[0] for a in st.names}
    return ({n.id for n in ast.walk(st) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            | {n.name for n in ast.walk(st) if isinstance(n, (ast.FunctionDef, ast.ClassDef))})


def uses(st):
    return {n.id for n in ast.walk(st) if isinstance(n, ast.Name)}


def is_fresh_module(node):
    return (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call) and (dotted(node.value.func) or "").endswith("import_fresh_module")
            and bool(node.value.args) and isinstance(node.value.args[0], ast.Constant))


class TestFile:
    """The mechanically transformed module of one CPython test file."""

    def __init__(self, path, setup_init=True):
        self.path = path
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        self.dropped = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                self.dropped |= {(a.asname or a.name).split(".")[0] for a in node.names
                                 if a.name.split(".")[0] in DROP_MODULES}
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in DROP_MODULES:
                self.dropped |= {a.asname or a.name for a in node.names}
        self.local = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
        pure, cvariant = {}, set()
        for node in tree.body:
            if is_fresh_module(node):
                if any(k.arg == "fresh" for k in node.value.keywords):
                    cvariant.add(node.targets[0].id)
                else:
                    pure[node.targets[0].id] = node.value.args[0].value
        body, classes = [], {}
        for node in tree.body:
            if is_fresh_module(node):
                if node.targets[0].id in pure:
                    body.append(ast.Import([ast.alias(pure[node.targets[0].id], node.targets[0].id)]))
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = node.names[0].name if isinstance(node, ast.Import) else (node.module or "")
                if mod.split(".")[0] not in DROP_MODULES:
                    body.append(node)
            elif isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and dotted(node.test.left) == "__name__":
                continue
            elif isinstance(node, ast.FunctionDef) and node.name in DROP_FUNCTIONS:
                continue
            elif isinstance(node, ast.ClassDef):
                classes[node.name] = node
                body.append(node)
            elif not uses(node) & self.dropped:
                body.append(node)
        self.classes = classes

        def cvariant_class(c):
            return (any(isinstance(it, ast.Assign) and isinstance(it.value, ast.Name) and it.value.id in cvariant
                        for it in c.body) or any(uses(d) & cvariant for d in c.decorator_list))
        self.concrete = [c for c in classes.values() if self.testcase(c) and not cvariant_class(c)]
        excluded = {c.name for c in classes.values() if self.testcase(c) and cvariant_class(c)}
        # every class of the file that a test class derives from, directly or not
        self.mixins = set()
        todo = [b.id for c in self.concrete for b in c.bases if isinstance(b, ast.Name) and b.id in classes]
        while todo:
            name = todo.pop()
            if name not in self.mixins:
                self.mixins.add(name)
                todo += [b.id for b in classes[name].bases if isinstance(b, ast.Name) and b.id in classes]
        attrs = {}
        for c in classes.values():
            for it in c.body:
                if (isinstance(it, ast.Assign) and len(it.targets) == 1 and isinstance(it.targets[0], ast.Name)
                        and isinstance(it.value, ast.Name) and it.value.id in pure):
                    attrs.setdefault(c.name, {})[it.targets[0].id] = it.value.id
        inherited = {}
        for c in self.concrete:
            todo = [b.id for b in c.bases if isinstance(b, ast.Name) and b.id in classes]
            seen = set()
            while todo:
                name = todo.pop()
                if name not in seen:
                    seen.add(name)
                    inherited.setdefault(name, {}).update(self.table(c, attrs))
                    todo += [b.id for b in classes[name].bases if isinstance(b, ast.Name) and b.id in classes]
        # Save class-level exclusions before transform strips unittest decorators. unittest
        # also inherits class skips, so include bases declared in this test module.
        def skipped_class(c, seen=()):
            return skip_decorated(c) or any(
                skipped_class(classes[b.id], seen + (c.name,)) for b in c.bases
                if isinstance(b, ast.Name) and b.id in classes and b.id not in seen)

        self.skipped_classes = {c.name for c in self.concrete if skipped_class(c)}
        self.original = {name: self.methods(c) for name, c in classes.items()}
        self.needs_re = set()
        out = []
        for node in body:
            if isinstance(node, ast.ClassDef) and node.name in excluded:
                continue
            if isinstance(node, ast.ClassDef) and (node.name in {c.name for c in self.concrete} or node.name in self.mixins):
                node = self.transform(node, self.table(node, attrs) | inherited.get(node.name, {}), setup_init)
                classes[node.name] = node
            out.append(node)
        self.concrete = [classes[c.name] for c in self.concrete]
        self.body = out
        self.facts = {id(st): (defines(st), uses(st)) for st in out if not isinstance(st, ast.ClassDef)}

    def testcase(self, c, seen=()):
        for b in c.bases:
            d = dotted(b)
            if d is not None and d not in self.local and (d.split(".")[0] in self.dropped or d.endswith("TestCase")):
                return True
            if isinstance(b, ast.Name) and b.id in self.classes and b.id not in seen:
                if self.testcase(self.classes[b.id], seen + (c.name,)):
                    return True
        return False

    def table(self, c, attrs, seen=()):
        t = {}
        for b in c.bases:
            if isinstance(b, ast.Name) and b.id in self.classes and b.id not in seen:
                t.update(self.table(self.classes[b.id], attrs, seen + (c.name,)))
        t.update(attrs.get(c.name, {}))
        return t

    def methods(self, c, seen=()):
        out = {}
        for b in c.bases:
            if isinstance(b, ast.Name) and b.id in self.classes and b.id not in seen:
                out.update(self.methods(self.classes[b.id], seen + (c.name,)))
        out.update({it.name: it for it in c.body if isinstance(it, ast.FunctionDef)})
        return out

    def transform(self, node, table, setup_init):
        node = copy.deepcopy(node)
        node.bases = [b for b in node.bases if not (dotted(b) and dotted(b) not in self.local and (
            dotted(b).split(".")[0] in self.dropped or dotted(b).endswith("TestCase")))]
        node.keywords = []
        node.decorator_list = [d for d in node.decorator_list if (dotted(d) or "").split(".")[0] not in self.dropped]
        if table:
            node.body = [ModuleAttribute(table).visit(it) for it in node.body
                         if not (isinstance(it, ast.Assign) and len(it.targets) == 1
                                 and isinstance(it.targets[0], ast.Name) and it.targets[0].id in table)]
        has_init = any(isinstance(it, ast.FunctionDef) and it.name == "__init__" for it in node.body)
        body = []
        for it in node.body:
            if isinstance(it, ast.FunctionDef):
                if it.name == "setUp" and setup_init and not has_init:
                    it.name = "__init__"
                    for n in ast.walk(it):
                        if (isinstance(n, ast.Attribute) and n.attr == "setUp" and isinstance(n.value, ast.Call)
                                and isinstance(n.value.func, ast.Name) and n.value.func.id == "super"):
                            n.attr = "__init__"
                it.decorator_list = [d for d in it.decorator_list if (dotted(d) or "").split(".")[0] not in self.dropped]
                try:
                    rewriter = Rewriter(aliases(it))
                    it = ast.fix_missing_locations(rewriter.visit(it))
                    if rewriter.uses_re:
                        self.needs_re.add((node.name, it.name))
                except Unsupported as e:
                    message = ast.Constant(f"tools/cpython_test_methods.py: {e}")
                    it = ast.FunctionDef(it.name, it.args, [ast.Raise(ast.Call(ast.Name("NotImplementedError", ast.Load()),
                                                                               [message], []))],
                                         [], None, type_params=[])
            body.append(it)
        node.body = body or [ast.Pass()]
        return node

    def tests(self):
        """[(class, method)] of the test methods to extract, and [(class, method, reason)] left out."""
        out, left = [], []
        for c in self.concrete:
            original = self.methods_of_original(c)
            for name in sorted(self.methods(c)):
                if not name.startswith("test"):
                    continue
                if c.name in self.skipped_classes or skip_decorated(original[name]):
                    left.append((c.name, name, "skip decorator"))
                else:
                    out.append((c.name, name))
        return out, left

    def methods_of_original(self, c, seen=()):
        out = {}
        for b in c.bases:
            if isinstance(b, ast.Name) and b.id in self.original and b.id not in seen:
                out.update(self.methods_of_original(self.classes[b.id], seen + (c.name,)))
        out.update(self.original.get(c.name, {}))
        return out

    def program(self, selection):
        """The source of a program running the selected (class, method) tests in order."""
        # a selected test stays in its class and the classes of the file it derives from, and only
        # there: another class can have a test of the same name
        keep = {}
        for cname, name in selection:
            todo = [cname]
            while todo:
                k = todo.pop()
                if name not in keep.setdefault(k, set()):
                    keep[k].add(name)
                    todo += [b.id for b in self.classes[k].bases if isinstance(b, ast.Name) and b.id in self.classes]
        tests = {c.name for c in self.concrete} | self.mixins
        body = []
        for st in self.body:
            if isinstance(st, ast.ClassDef) and st.name in tests:
                st = copy.copy(st)
                st.body = [it for it in st.body if not (isinstance(it, ast.FunctionDef) and it.name.startswith("test")
                                                        and it.name not in keep.get(st.name, ()))] or [ast.Pass()]
            body.append(st)
        facts = [(st,) + (self.facts.get(id(st)) or (defines(st), uses(st))) for st in body]
        need = set()
        for cname, _ in selection:
            root = next(st for st in body if isinstance(st, ast.ClassDef) and st.name == cname)
            need |= uses(root) | {cname} | {b.id for b in root.bases if isinstance(b, ast.Name)}
        changed = True
        while changed:
            changed = False
            for st, d, u in facts:
                if d & need and not u <= need:
                    need |= u
                    changed = True
        kept = [st for st, d, _ in facts if d & need or not d]
        # the assertRegex/assertRaisesRegex rewrites call re.search(); bind re where the file does not
        def present(k, m):
            # helper methods always stay; a test only where it was selected
            return any(isinstance(st, ast.ClassDef) and st.name == k for st in kept) and (
                not m.startswith("test") or m in keep.get(k, ()))
        imports = [st for st in kept if isinstance(st, (ast.Import, ast.ImportFrom))]
        # (after the docstring and any `from __future__` import, which must come first)
        at = next((i for i, st in enumerate(kept) if not (
            (i == 0 and isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str))
            or (isinstance(st, ast.ImportFrom) and st.module == "__future__"))), len(kept))
        if any(present(k, m) for k, m in self.needs_re) and not any(
                isinstance(st, ast.Import) and any((a.asname or a.name) == "re" for a in st.names) for st in imports):
            kept.insert(at, ast.Import([ast.alias("re")]))
        # a program whose tests use random seeds it before each test, so that every run draws the same
        # inputs (lib/random is CPython's Mersenne Twister: native runs draw CPython's values too)
        rand = next((a.asname or a.name for st in imports if isinstance(st, ast.Import) for a in st.names
                     if a.name == "random"), None)
        if rand is None and any(isinstance(st, ast.ImportFrom) and st.module == "random" for st in imports):
            rand = "random"
            if not any("random" in defines(st) for st in kept):
                kept.insert(at, ast.Import([ast.alias("random")]))
        module = ast.Module(kept, [])
        lines = [ast.unparse(ast.fix_missing_locations(module)), "", ""]
        for cname, name in selection:
            ms = self.methods(next(c for c in self.concrete if c.name == cname))
            lines.append(f"def _{cname}__{name}():")
            if rand:
                lines.append(f"    {rand}.seed(0)")
            lines.append(f"    t = {cname}()")
            if "setUp" in ms:
                lines.append("    t.setUp()")
            lines.append(f"    t.{name}()")
            if "tearDown" in ms:
                lines.append("    t.tearDown()")
            lines += [f"    print('ok {cname}.{name}')", "", ""]
        lines += [f"_{cname}__{name}()" for cname, name in selection]
        return "\n".join(lines) + "\n"


def extract(path, outdir, setup_init=True):
    tf = TestFile(path, setup_init)
    tests, left = tf.tests()
    os.makedirs(outdir, exist_ok=True)
    for cname, name in tests:
        Path(outdir, f"{cname}__{name}.py").write_text(tf.program([(cname, name)]))
    return tests, left


def run(command, timeout, cwd=None, env=None):
    try:
        p = subprocess.run(command, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
    except subprocess.TimeoutExpired:
        return None, "", "timeout"
    return p.returncode, p.stdout, p.stderr


def first_error(err):
    for line in err.splitlines():
        if ": error: " in line:
            line = re.sub(r" \((compiling|specializing) .*$", "", line)
            return re.sub(r"^.*?/([^/]+\.py):\d+: ", r"\1: ", line)
    lines = [line for line in err.strip().splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""


def native(compiler, prog, expected, env):
    n = run(compiler + ["run", prog], 300, cwd=ROOT, env=env)
    if n[0] is None:
        return {"status": "timeout"}
    if n == expected:
        return {"status": "match"}
    if n[0] != 0 and not n[1] and ": error: " in n[2]:
        return {"status": "compile-error", "detail": first_error(n[2])}
    return {"status": "differs", "exit": n[0], "detail": (n[1][-300:] + " | " + n[2][-500:]).strip()}


def triage_one(compiler, prog, env, test):
    c = run([sys.executable, "-I", prog], 120, cwd=os.path.dirname(prog))
    if c[0] != 0:
        return {"status": "cpython-fail", "detail": first_error(c[2])}
    if c[1].splitlines()[-1:] != [f"ok {test}"]:
        return {"status": "cpython-fail", "detail": "success marker not reached"}
    r = native(compiler, prog, c, env)
    if r["status"] != "match" and "fit in 64 bits" in r.get("detail", ""):
        wide = prog[:-3] + "__python_int.py"
        Path(wide).write_text("# pystachy: python-int\n" + Path(prog).read_text())
        retry = native(compiler, wide, c, env)
        os.unlink(wide)
        r["python_int_retry"] = retry["status"]
        if retry["status"] == "match":
            r["status"] = "match-python-int"
    return r


def triage(compiler, jobs, out, workdir, files):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
    for k in ("PYSTACHY_CACHE", "PYSTACHY_LLVM", "PYSTACHY_HOME"):
        if k in os.environ:
            env[k] = os.environ[k]
    work = []
    left_out = {}
    errors = {}
    for f in files:
        name = Path(f).stem if f.endswith(".py") else Path(f).name
        d = os.path.join(os.path.abspath(workdir), Path(f).parent.name + "." + name if Path(f).parent.name != "test" else name)
        try:
            tests, left = extract(f, d)
        except (OSError, SyntaxError, UnicodeDecodeError, RecursionError) as e:
            # (a file that cannot be read or parsed is reported, not silently left out)
            errors[f] = f"{type(e).__name__}: {e}"
            print(f"{f}: not extracted: {errors[f]}", file=sys.stderr)
            continue
        left_out[f] = [list(x) for x in left]
        work += [(f, c, m, os.path.join(d, f"{c}__{m}.py")) for c, m in tests]
    records = []
    with concurrent.futures.ThreadPoolExecutor(jobs) as ex:
        for (f, c, m, prog), r in zip(work, ex.map(lambda w: triage_one(compiler, w[3], env, f"{w[1]}.{w[2]}"), work)):
            records.append({"file": f, "test": f"{c}.{m}", "program": prog} | r)
    with open(out, "w") as fh:
        json.dump({"python": sys.version, "compiler": compiler, "records": records, "left_out": left_out,
                   "errors": errors}, fh, indent=1)
    totals = {}
    for r in records:
        totals[r["status"]] = totals.get(r["status"], 0) + 1
    print(json.dumps(totals, sort_keys=True))
    if errors:
        sys.exit(f"{len(errors)} file(s) not extracted")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("extract")
    e.add_argument("testfile")
    e.add_argument("outdir")
    e.add_argument("--no-setup-init", action="store_true")
    c = sub.add_parser("combine")
    c.add_argument("testfile")
    c.add_argument("out")
    c.add_argument("tests", nargs="+", help="CLASS.METHOD, in the order to run them")
    c.add_argument("--no-setup-init", action="store_true")
    t = sub.add_parser("triage")
    t.add_argument("--compiler", default=str(ROOT / "pystachy"), help="shell-split command")
    t.add_argument("-j", type=int, default=2)
    t.add_argument("out")
    t.add_argument("workdir")
    t.add_argument("testfiles", nargs="+")
    args = parser.parse_args(argv)
    if args.command == "extract":
        tests, left = extract(args.testfile, args.outdir, not args.no_setup_init)
        print(f"{len(tests)} extracted, {len(left)} left out by decorators")
    elif args.command == "combine":
        tf = TestFile(args.testfile, not args.no_setup_init)
        known = set(tf.tests()[0])
        selection = [tuple(x.split(".", 1)) for x in args.tests]
        missing = [".".join(x) for x in selection if x not in known]
        if missing:
            parser.error("not extracted from this file: " + ", ".join(missing))
        Path(args.out).write_text(tf.program(selection))
    else:
        triage(shlex.split(args.compiler), args.j, args.out, args.workdir, args.testfiles)


if __name__ == "__main__":
    main()
